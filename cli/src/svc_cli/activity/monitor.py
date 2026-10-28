"""Bounded host sampling and read-only execution projections."""

from __future__ import annotations

import platform
import subprocess
import time
from datetime import datetime, timezone
from typing import Literal

import psutil  # type: ignore[import-untyped]
from filelock import Timeout

from .._execution import (
    ACTIVE_STATES,
    ExecutionRecord,
    ExecutionStore,
    reconcile_owner_loss,
)
from ..errors import SvcError
from .models import ActivitySnapshot, ExecutionActivity, HostPressure, ProcessUsage
from .managed import read_management, read_termination


def monitor(
    *, limit: int = 20, store: ExecutionStore | None = None
) -> ActivitySnapshot:
    if not 1 <= limit <= 100:
        raise SvcError("invalid-activity-limit", "执行历史条数必须在 1 到 100 之间。")
    authority = store or ExecutionStore()
    records: list[ExecutionRecord] = []
    issues: list[str] = []
    # Each directory is read once. No project probes or command execution occur here.
    for path in authority.root.glob("*/execution.json"):
        try:
            record = authority.read(path.parent.name)
            records.append(reconcile_owner_loss(authority, record))
        except SvcError as error:
            issues.append(f"{path.parent.name}: {error}")
    records.sort(key=lambda item: item.started_at, reverse=True)
    active = [item for item in records if item.state in ACTIVE_STATES]
    selected = (
        active + [item for item in records if item.state not in ACTIVE_STATES][:limit]
    )
    processes: dict[str, list[object]] = {}
    metadata: dict[str, dict[str, object] | None] = {}
    for record in selected:
        try:
            info = read_management(authority, record)
            metadata[record.execution_id] = info
            if info and record.state in ACTIVE_STATES and record.process_id:
                process = psutil.Process(record.process_id)
                if process.create_time() == info.get("process_created_at"):
                    family = [process, *process.children(recursive=True)]
                    if len(family) > 256:
                        issues.append(
                            f"{record.execution_id}: 用量采样限于前 256 个当前后代，统计不完整。"
                        )
                        family = family[:256]
                    # CPU sampling is nonblocking; a single shared window follows.
                    for member in family:
                        member.cpu_percent(None)
                    processes[record.execution_id] = family
        except (SvcError, psutil.Error, OSError) as error:
            issues.append(f"{record.execution_id}: {error}")

    before_disk = _disk_counters()
    start = time.monotonic()
    cpu = psutil.cpu_percent(interval=0.25)
    elapsed = time.monotonic() - start
    after_disk = _disk_counters()
    memory = psutil.virtual_memory()
    memory_level, memory_issue = _memory_pressure()
    level = (
        "critical"
        if memory_level == "critical"
        else ("elevated" if memory_level == "warning" or cpu >= 85 else "normal")
    )
    if memory_level == "unknown" and cpu < 85:
        level = "unknown"
    recommendation = {
        "critical": "暂停启动重任务，检查并结束可中断的非必要执行；不要自动重试人为终止的任务。",
        "elevated": "将重任务串行执行，降低工具并发，并在启动下一项前重新采样。",
        "normal": "按需执行；启动重任务后继续观察，单次采样不保证后续容量。",
        "unknown": "内存压力未知；保守安排并发，并检查不可用的指标。",
    }[level]
    pressure = HostPressure(
        sampled_at=datetime.now(timezone.utc).isoformat(),
        sample_window_ms=round(elapsed * 1000),
        cpu_percent=cpu,
        logical_cpus=psutil.cpu_count() or 1,
        memory_total_bytes=memory.total,
        memory_available_bytes=memory.available,
        memory_pressure=memory_level,
        disk_read_bytes_per_second=_rate(
            before_disk, after_disk, "read_bytes", elapsed
        ),
        disk_write_bytes_per_second=_rate(
            before_disk, after_disk, "write_bytes", elapsed
        ),
        level=level,
        recommendation=recommendation,
        issues=tuple([memory_issue] if memory_issue else []),
    )
    activities: list[ExecutionActivity] = []
    for record in selected:
        info = metadata.get(record.execution_id)
        usage = _usage(processes.get(record.execution_id, []))
        controls = bool(
            info and record.state in ACTIVE_STATES and _owner_live(authority, record)
        )
        try:
            request = read_termination(authority, record.execution_id) if info else None
            requested = str(request["mode"]) if request else None
        except SvcError as error:
            issues.append(f"{record.execution_id}: {error}")
            requested = None
        logs: tuple[Literal["stdout", "stderr", "merged"], ...] = (
            ("stdout", "stderr") if record.capture == "split" else ("merged",)
        )
        activities.append(
            ExecutionActivity(
                record=record,
                label=str(info["label"]) if info else record.subject,
                source=str(info["source"]) if info else record.domain,
                can_terminate=controls,
                termination_requested=requested,
                group_state=str(info["group_state"]) if info else None,
                usage=usage,
                logs=tuple(str(authority.log_path(record, name)) for name in logs),
            )
        )
    return ActivitySnapshot(pressure, tuple(activities), tuple(issues))


def _owner_live(store: ExecutionStore, record: ExecutionRecord) -> bool:
    lock = store.coordination_lock(record.domain, record.coordination_key)
    try:
        lock.acquire(timeout=0)
    except Timeout:
        return True
    else:
        lock.release()
        return False


def _usage(processes: list[object]) -> ProcessUsage | None:
    if not processes:
        return None
    cpu = 0.0
    rss = 0
    count = 0
    for process in processes:
        try:
            # psutil Process guards identity across these reads.
            if not process.is_running():  # type: ignore[attr-defined]
                continue
            cpu += process.cpu_percent(None)  # type: ignore[attr-defined]
            rss += process.memory_info().rss  # type: ignore[attr-defined]
            count += 1
        except psutil.Error:
            continue
    return ProcessUsage(round(cpu, 1), rss, count) if count else None


def _memory_pressure() -> tuple[str, str | None]:
    if platform.system() != "Darwin":
        return "unknown", "当前平台未提供系统内存压力等级；可用内存不等于压力。"
    try:
        result = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "kern.memorystatus_vm_pressure_level"],
            capture_output=True,
            text=True,
            timeout=1,
            check=True,
        )
        level = {"1": "normal", "2": "warning", "4": "critical"}.get(
            result.stdout.strip()
        )
        if level:
            return level, None
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown", "无法读取系统内存压力等级。"


def _disk_counters() -> object:
    try:
        return psutil.disk_io_counters()
    except (OSError, psutil.Error):
        return None


def _rate(before: object, after: object, field: str, elapsed: float) -> float | None:
    if before is None or after is None:
        return None
    delta = getattr(after, field) - getattr(before, field)
    return round(delta / elapsed, 1) if delta >= 0 else None
