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
from .models import ActivitySnapshot, ExecutionActivity, HostPressure
from .managed import read_management, read_termination
from .darwin import DarwinMetrics, VMCounters
from .provenance import ExecutionOrigin, read as read_origin
from .usage import UsageSampler, projects


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
    metadata: dict[str, dict[str, object] | None] = {}
    origins: dict[str, ExecutionOrigin | None] = {}
    controls: dict[str, bool] = {}
    native = DarwinMetrics() if platform.system() == "Darwin" else None
    sampler = UsageSampler(native)
    # Historical display limits must not hide a still-running released server.
    # Active roots get priority within the accounting budget.
    for record in sorted(records, key=lambda item: item.state not in ACTIVE_STATES):
        try:
            info = read_management(authority, record)
            metadata[record.execution_id] = info
        except SvcError as error:
            metadata[record.execution_id] = None
            issues.append(f"{record.execution_id}: {error}")
        try:
            origins[record.execution_id] = read_origin(authority, record)
        except SvcError as error:
            origins[record.execution_id] = None
            issues.append(f"{record.execution_id}: {error}")
        info = metadata[record.execution_id]
        origin = origins[record.execution_id]
        controls[record.execution_id] = bool(
            info and record.state in ACTIVE_STATES and _owner_live(authority, record)
        )
        created = (
            info.get("process_created_at")
            if info is not None
            else (origin.process_created_at if origin else None)
        )
        sampler.prepare(
            record,
            origin,
            float(created) if isinstance(created, (int, float)) else None,
            managed_owner_live=controls[record.execution_id],
        )

    before_disk = _disk_counters()
    before_vm = _vm_counters(native, issues)
    start = time.monotonic()
    cpu = psutil.cpu_percent(interval=0.25)
    elapsed = time.monotonic() - start
    after_disk = _disk_counters()
    after_vm = _vm_counters(native, issues)
    usages = sampler.finish()
    current_ids = {
        item.execution_id
        for item in records
        if item.state in ACTIVE_STATES
        or (item.state == "owner-lost" and usages.get(item.execution_id) is not None)
    }
    selected = [item for item in records if item.execution_id in current_ids] + [
        item for item in records if item.execution_id not in current_ids
    ][:limit]
    resources = sampler.resources(usages)
    project_usages = projects(records, origins, resources, usages)
    issues.extend(sampler.issues)
    try:
        swap = psutil.swap_memory()
    except (OSError, psutil.Error) as error:
        swap = None
        issues.append(f"无法读取系统 swap 占用：{error}")
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
        swap_used_bytes=swap.used if swap is not None else None,
        swap_total_bytes=swap.total if swap is not None else None,
        compressed_bytes=after_vm.compressed_bytes if after_vm else None,
        page_size_bytes=after_vm.page_size if after_vm else None,
        pageins_per_second=_rate(before_vm, after_vm, "pageins", elapsed),
        pageouts_per_second=_rate(before_vm, after_vm, "pageouts", elapsed),
        swapins_per_second=_rate(before_vm, after_vm, "swapins", elapsed),
        swapouts_per_second=_rate(before_vm, after_vm, "swapouts", elapsed),
        compressions_per_second=_rate(before_vm, after_vm, "compressions", elapsed),
        decompressions_per_second=_rate(before_vm, after_vm, "decompressions", elapsed),
    )
    activities: list[ExecutionActivity] = []
    for record in selected:
        info = metadata.get(record.execution_id)
        usage = usages.get(record.execution_id)
        origin = origins.get(record.execution_id)
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
                can_terminate=controls[record.execution_id],
                termination_requested=requested,
                group_state=str(info["group_state"]) if info else None,
                usage=usage,
                logs=tuple(str(authority.log_path(record, name)) for name in logs),
                project_path=origin.project_path if origin else None,
                project_source=origin.project_source if origin else "unassigned",
            )
        )
    return ActivitySnapshot(
        pressure,
        tuple(activities),
        tuple(dict.fromkeys(issues)),
        project_usages,
        resources,
    )


def _owner_live(store: ExecutionStore, record: ExecutionRecord) -> bool:
    lock = store.coordination_lock(record.domain, record.coordination_key)
    try:
        lock.acquire(timeout=0)
    except Timeout:
        return True
    else:
        lock.release()
        return False


def _vm_counters(native: DarwinMetrics | None, issues: list[str]) -> VMCounters | None:
    if native is None:
        return None
    try:
        return native.virtual_memory()
    except OSError as error:
        issues.append(f"无法读取内存换页与压缩：{error}")
        return None


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
