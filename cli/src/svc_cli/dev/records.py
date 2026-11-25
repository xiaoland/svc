"""Dev settlement and recovery alongside unchanged mechanical execution records."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Self
from pydantic import model_validator, ValidationError
from filelock import Timeout
from .._execution import (
    ACTIVE_STATES,
    ExecutionRecord,
    ExecutionStore,
    _atomic_json,
    mark_owner_lost,
    require_execution_id,
)
from ..errors import SvcError
from ..model import ValueModel
from .models import ActionReceipt, ExecutionView, parse_json


class DevRecord(ValueModel):
    schema_version: Literal[1] = 1
    execution_id: str
    coordination_id: str
    entry_id: str
    action: str
    declaration_digest: str
    intent_digest: str
    phase: Literal["pending", "settled", "owner-lost"] = "pending"
    acknowledged: bool = False
    acknowledged_at: str | None = None
    requested_signal: str | None = None
    receipt: ActionReceipt | None = None

    @model_validator(mode="after")
    def validate_settlement(self) -> Self:
        require_execution_id(self.execution_id)
        if self.phase == "settled" and self.receipt is None:
            raise ValueError("settled dev records require the complete receipt")
        if self.acknowledged and (
            self.phase != "owner-lost" or not self.acknowledged_at
        ):
            raise ValueError("only an owner-lost outcome can be acknowledged")
        return self


def path(store: ExecutionStore, execution_id: str) -> Path:
    return store.execution_dir(execution_id) / "dev.json"


def write(store: ExecutionStore, record: DevRecord) -> None:
    _atomic_json(
        path(store, record.execution_id),
        record.model_dump(mode="json", exclude_none=True),
    )


def read(store: ExecutionStore, execution: ExecutionRecord) -> DevRecord:
    target = path(store, execution.execution_id)
    if not target.exists() and execution.operation in {"ensure", "stop"}:
        return DevRecord(
            execution_id=execution.execution_id,
            coordination_id=execution.coordination_key,
            entry_id="",
            action=execution.operation,
            declaration_digest="",
            intent_digest=execution.intent_digest,
            phase="owner-lost" if execution.state == "owner-lost" else "pending",
        )
    try:
        raw = read_regular(target, 4 * 1024 * 1024)
        record = DevRecord.model_validate_json(raw)
        if (
            record.execution_id != execution.execution_id
            or record.coordination_id != execution.coordination_key
            or record.intent_digest != execution.intent_digest
        ):
            raise ValueError("dev metadata does not match its execution")
        return record
    except (OSError, ValueError, ValidationError) as error:
        raise SvcError(
            "dev-record-invalid",
            "dev 执行记录缺失、损坏或不匹配；不能继续控制。",
            {"execution_id": execution.execution_id},
        ) from error


def read_regular(target: Path, limit: int) -> bytes:
    import os
    import stat

    descriptor = os.open(
        target,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
    )
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("result must be a regular file")
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("result exceeds size limit")

    parse_json(raw)
    return raw


def current(
    store: ExecutionStore, key: str, *, abandoned: bool = False
) -> tuple[ExecutionRecord, DevRecord] | None:
    execution_id = store.read_coordination("dev", key)
    if execution_id is None:
        return None
    execution = store.read(execution_id)
    record = read(store, execution)
    legacy = execution.operation in {"ensure", "stop"}
    # Completed legacy commands have no dev settlement protocol; only their active/unknown states block.
    lost = record.phase == "owner-lost" or (
        record.phase == "pending" and (not legacy or execution.state in ACTIVE_STATES)
    )
    if abandoned and lost:
        if execution.state in ACTIVE_STATES:
            execution = mark_owner_lost(store, execution)
        if record.phase != "owner-lost":
            record = record.model_copy(update={"phase": "owner-lost"})
            write(store, record)
    return execution, record


def inspect(store: ExecutionStore, key: str) -> ExecutionView | None:
    lock = store.coordination_lock("dev", key)
    try:
        lock.acquire(timeout=0)
    except Timeout:
        pair = current(store, key)
    else:
        try:
            pair = current(store, key, abandoned=True)
        finally:
            lock.release()
    return view(store, *pair) if pair else None


def view(
    store: ExecutionStore, execution: ExecutionRecord, record: DevRecord
) -> ExecutionView:
    phase = record.phase
    if (
        execution.operation in {"ensure", "stop"}
        and execution.state not in ACTIVE_STATES
        and execution.state != "owner-lost"
    ):
        phase = "settled"
    return ExecutionView(
        execution_id=execution.execution_id,
        state=execution.state,
        phase=phase,
        acknowledged=record.acknowledged,
        action=record.action,
        entry_id=record.entry_id or None,
        exit_code=execution.exit_code,
        log_path=str(store.log_path(execution, "merged")),
    )
