"""One-off runs controlled by requests to their actual foreground owner."""

from __future__ import annotations

import hashlib
import os
import signal
import subprocess
import time
import uuid
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

import psutil  # type: ignore[import-untyped]
from filelock import FileLock

from .._execution import (
    ACTIVE_STATES,
    ExecutionRecord,
    ExecutionStore,
    _atomic_json,
    _read_json,
    _settle,
    require_execution_id,
    reconcile_owner_loss,
)
from ..errors import SvcError
from .models import ManagedResult, TerminationResult
from .process_group import ProcessGroup


def read_management(
    store: ExecutionStore, record: ExecutionRecord
) -> dict[str, object] | None:
    if record.domain != "run" or record.operation != "managed":
        return None
    path = store.execution_dir(record.execution_id) / "management.json"
    info = _read_json(path)
    if (
        set(info)
        != {
            "schema_version",
            "execution_id",
            "label",
            "source",
            "process_created_at",
            "group_state",
        }
        or type(info.get("schema_version")) is not int
        or info["schema_version"] != 1
        or info.get("execution_id") != record.execution_id
        or not all(
            isinstance(info.get(key), str) and info[key] for key in ("label", "source")
        )
        or info.get("group_state")
        not in {
            "starting",
            "running",
            "descendants-running",
            "scope-complete",
            "unknown",
        }
        or (
            info.get("process_created_at") is not None
            and type(info["process_created_at"]) not in (int, float)
        )
    ):
        raise SvcError("managed-metadata-invalid", "受管执行元数据无效；控制已禁用。")
    return info


def read_termination(
    store: ExecutionStore, execution_id: str
) -> dict[str, object] | None:
    path = store.execution_dir(execution_id) / "termination.json"
    if not path.exists():
        return None
    info = _read_json(path)
    if (
        set(info)
        != {"schema_version", "execution_id", "mode", "requested_at", "requested_by"}
        or type(info.get("schema_version")) is not int
        or info["schema_version"] != 1
        or info.get("execution_id") != execution_id
        or info.get("mode") not in {"terminate", "kill"}
        or info.get("requested_by") not in {"human", "agent", "terminal"}
        or not isinstance(info.get("requested_at"), str)
    ):
        raise SvcError("managed-request-invalid", "终止请求损坏，不能执行。")
    return info


def request_termination(
    execution_id: str,
    *,
    force: bool = False,
    by: str = "terminal",
    store: ExecutionStore | None = None,
) -> TerminationResult:
    if by not in {"human", "agent", "terminal"}:
        raise SvcError("invalid-termination-source", "终止来源无效。")
    authority = store or ExecutionStore()
    record = reconcile_owner_loss(
        authority, authority.read(require_execution_id(execution_id))
    )
    if not read_management(authority, record):
        raise SvcError(
            "execution-not-controllable", "该执行未接入终止通道；没有按历史 PID 接管。"
        )
    mode = "kill" if force else "terminate"
    if record.state not in ACTIVE_STATES:
        return TerminationResult(
            execution_id, "not-running", mode, "执行已结束或失去执行者；没有发送信号。"
        )
    directory = authority.execution_dir(execution_id)
    with FileLock(str(directory / "termination.lock"), mode=0o600):
        previous = read_termination(authority, execution_id)
        # Concurrent normal requests must never downgrade an emergency request.
        if not previous or (force and previous["mode"] != "kill"):
            _atomic_json(
                directory / "termination.json",
                {
                    "schema_version": 1,
                    "execution_id": execution_id,
                    "mode": mode,
                    "requested_at": _now(),
                    "requested_by": by,
                },
            )
        elif previous:
            mode = str(previous["mode"])
    return TerminationResult(
        execution_id,
        "requested",
        mode,
        "已请求实际执行者终止；请继续查询实际退出结果。",
    )


def execute(
    argv: tuple[str, ...],
    cwd: Path,
    *,
    label: str | None = None,
    source: str = "terminal",
    store: ExecutionStore | None = None,
    on_started: Callable[[ExecutionRecord], None] | None = None,
) -> ManagedResult:
    if not argv or not argv[0] or any("\0" in value for value in argv):
        raise SvcError("invalid-managed-command", "请在 -- 后提供有效的命令及参数。")
    directory = cwd.expanduser().resolve()
    if not directory.is_dir():
        raise SvcError("managed-cwd-not-directory", "执行目录不存在。")
    title = (label or Path(argv[0]).name).strip()
    if not title or len(title) > 200 or not source.strip() or len(source) > 200:
        raise SvcError("invalid-managed-label", "名称和来源必须为 1 到 200 个字符。")
    group = ProcessGroup()
    authority = store or ExecutionStore()
    key = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    with authority.coordination_lock("run", key):
        published = authority.publish(
            domain="run",
            operation="managed",
            subject=title,
            workspace_instance=hashlib.sha256(str(directory).encode()).hexdigest(),
            intent_digest=hashlib.sha256("\0".join(argv).encode()).hexdigest(),
            coordination_key=key,
            argv=argv,
            cwd=directory,
            capture="split",
        )
        record = published.record
        metadata: dict[str, object] = {
            "schema_version": 1,
            "execution_id": record.execution_id,
            "label": title,
            "source": source.strip(),
            "process_created_at": None,
            "group_state": "starting",
        }
        metadata_path = authority.execution_dir(record.execution_id) / "management.json"
        _atomic_json(metadata_path, metadata)
        if on_started:
            on_started(record)
        with _signals() as signals:
            if signals:
                final = _settle(
                    authority, record, "interrupted", requested_signal="SIGTERM"
                )
                metadata["group_state"] = "scope-complete"
                _atomic_json(metadata_path, metadata)
                return _result(authority, final, metadata, "terminal")
            with (
                authority.log_path(record, "stdout").open("ab", buffering=0) as stdout,
                authority.log_path(record, "stderr").open("ab", buffering=0) as stderr,
            ):
                try:
                    process = subprocess.Popen(
                        argv,
                        cwd=directory,
                        env=os.environ.copy(),
                        stdin=subprocess.DEVNULL,
                        stdout=stdout,
                        stderr=stderr,
                        start_new_session=True,
                        close_fds=True,
                    )
                except OSError as error:
                    final = _settle(
                        authority, record, "start-failed", failure_reason=str(error)
                    )
                    metadata["group_state"] = "scope-complete"
                    _atomic_json(metadata_path, metadata)
                    return _result(authority, final, metadata, None)
            record = replace(record, state="running", process_id=process.pid)
            try:
                metadata["process_created_at"] = psutil.Process(
                    process.pid
                ).create_time()
                metadata["group_state"] = "running"
                authority.write(record)
                _atomic_json(metadata_path, metadata)
            except BaseException:
                # The child is still owned and unreaped here; contain a failed publication.
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise
            stopped_by: str | None = None
            sent: str | None = None
            while True:
                if signals:
                    request_termination(
                        record.execution_id, by="terminal", store=authority
                    )
                    signals.clear()
                request = read_termination(authority, record.execution_id)
                if request and request["mode"] != sent:
                    number = (
                        signal.SIGKILL if request["mode"] == "kill" else signal.SIGTERM
                    )
                    # Never poll()/wait() before the group is empty: the unreaped
                    # leader reserves its PID/PGID even after it becomes a zombie.
                    try:
                        os.killpg(process.pid, number)
                    except ProcessLookupError:
                        pass
                    sent = str(request["mode"])
                    stopped_by = str(request["requested_by"])
                try:
                    if group.complete(process.pid):
                        break
                    state = (
                        "descendants-running"
                        if psutil.Process(process.pid).status() == psutil.STATUS_ZOMBIE
                        else "running"
                    )
                except SvcError as error:
                    state = "unknown"
                    # Preserve ownership and control when observation is unavailable.
                    _atomic_json(
                        authority.execution_dir(record.execution_id)
                        / "group-error.json",
                        {"message": str(error), "checked_at": _now()},
                    )
                if metadata["group_state"] != state:
                    metadata["group_state"] = state
                    _atomic_json(metadata_path, metadata)
                time.sleep(1)
            return_code = process.wait()
            metadata["group_state"] = "scope-complete"
            _atomic_json(metadata_path, metadata)
            if sent or return_code < 0:
                final = _settle(
                    authority,
                    record,
                    "interrupted",
                    requested_signal=("SIGKILL" if sent == "kill" else "SIGTERM")
                    if sent
                    else None,
                    termination_signal=signal.Signals(-return_code).name
                    if return_code < 0
                    else None,
                )
            else:
                final = _settle(authority, record, "exited", exit_code=return_code)
            return _result(authority, final, metadata, stopped_by)


@contextmanager
def _signals() -> Iterator[list[int]]:
    received: list[int] = []
    previous = {
        number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        for number in previous:
            signal.signal(number, lambda value, _frame: received.append(value))
        yield received
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def _result(
    store: ExecutionStore,
    record: ExecutionRecord,
    metadata: dict[str, object],
    stopped_by: str | None,
) -> ManagedResult:
    return ManagedResult(
        record,
        str(metadata["label"]),
        str(metadata["source"]),
        stopped_by,
        str(metadata["group_state"]),
        tuple(str(store.log_path(record, stream)) for stream in ("stdout", "stderr")),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
