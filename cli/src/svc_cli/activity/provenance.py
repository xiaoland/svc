"""Launch-time observation facts; these never grant process control."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path

import psutil  # type: ignore[import-untyped]

from .._execution import ExecutionRecord, ExecutionStore, _atomic_json, _read_json
from ..errors import SvcError


@dataclass(frozen=True)
class ExecutionOrigin:
    project_path: str | None
    project_source: str
    process_created_at: float | None
    resource_entry_id: str | None = None
    resource_key: str | None = None


def project_for(cwd: Path, explicit: Path | None) -> tuple[Path | None, str]:
    if explicit is not None:
        root = explicit.expanduser().resolve()
        if not root.is_dir():
            raise SvcError("execution-project-invalid", "执行归属项目必须是现有目录。")
        return root, "explicit"
    for parent in (cwd, *cwd.parents):
        if (parent / "svc.json").is_file():
            return parent, "configuration-ancestor"
    return None, "unassigned"


def register(
    store: ExecutionStore,
    record: ExecutionRecord,
    project: Path | None,
    source: str,
    *,
    resource_entry_id: str | None = None,
    resource_key: str | None = None,
) -> None:
    created = None
    if record.process_id is not None and record.operation != "managed":
        try:
            created = psutil.Process(record.process_id).create_time()
        except psutil.Error:
            # A short command can finish before observation identity is captured.
            # Project attribution remains useful; PID-only observation is forbidden.
            pass
    try:
        fields = {
            "schema_version": 1,
            "execution_id": record.execution_id,
            "project_path": str(project) if project is not None else None,
            "project_source": source,
            "process_created_at": created,
            "resource_entry_id": resource_entry_id,
            "resource_key": resource_key,
        }
        _atomic_json(
            store.execution_dir(record.execution_id) / "observation.json",
            {key: value for key, value in fields.items() if value is not None},
        )
    except (SvcError, OSError) as error:
        # Optional accounting must not alter wait/release or terminate real work.
        logging.getLogger(__name__).warning("未能登记执行用量来源：%s", error)


def read(store: ExecutionStore, record: ExecutionRecord) -> ExecutionOrigin | None:
    path = store.execution_dir(record.execution_id) / "observation.json"
    if not path.exists():
        return None
    info = _read_json(path)
    required = {"schema_version", "execution_id", "project_source"}
    optional = {
        "project_path",
        "process_created_at",
        "resource_entry_id",
        "resource_key",
    }
    project = info.get("project_path")
    created = info.get("process_created_at")
    if (
        set(info) - required - optional
        or required - set(info)
        or type(info["schema_version"]) is not int
        or info["schema_version"] != 1
        or info["execution_id"] != record.execution_id
        or (
            project is not None
            and (not isinstance(project, str) or not Path(project).is_absolute())
        )
        or info["project_source"]
        not in {"declared", "explicit", "configuration-ancestor", "unassigned"}
        or ((project is None) != (info["project_source"] == "unassigned"))
        or (
            created is not None
            and (
                not isinstance(created, (int, float))
                or isinstance(created, bool)
                or not math.isfinite(created)
                or created <= 0
            )
        )
        or any(
            info.get(key) is not None
            and (not isinstance(info[key], str) or not info[key])
            for key in ("resource_entry_id", "resource_key")
        )
    ):
        raise SvcError(
            "execution-observation-invalid", "执行用量来源无效；未按历史 PID 补录。"
        )
    return ExecutionOrigin(
        str(project) if project is not None else None,
        str(info["project_source"]),
        float(created) if isinstance(created, (int, float)) else None,
        str(info["resource_entry_id"])
        if info.get("resource_entry_id") is not None
        else None,
        str(info["resource_key"]) if info.get("resource_key") is not None else None,
    )
