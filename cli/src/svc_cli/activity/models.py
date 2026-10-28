"""Observations shared by the Human and Agent activity entry points."""

from dataclasses import dataclass, field

from .._execution import ExecutionRecord


@dataclass(frozen=True)
class HostPressure:
    sampled_at: str
    sample_window_ms: int
    cpu_percent: float
    logical_cpus: int
    memory_total_bytes: int
    memory_available_bytes: int
    memory_pressure: str
    disk_read_bytes_per_second: float | None
    disk_write_bytes_per_second: float | None
    level: str
    recommendation: str
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProcessUsage:
    cpu_percent: float
    rss_bytes: int
    process_count: int
    scope: str = "verified-current-descendants"


@dataclass(frozen=True)
class ExecutionActivity:
    record: ExecutionRecord
    label: str
    source: str
    can_terminate: bool
    termination_requested: str | None
    group_state: str | None
    usage: ProcessUsage | None
    logs: tuple[str, ...]
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActivitySnapshot:
    pressure: HostPressure
    executions: tuple[ExecutionActivity, ...]
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class TerminationResult:
    execution_id: str
    status: str
    mode: str
    message: str


@dataclass(frozen=True)
class ManagedResult:
    record: ExecutionRecord
    label: str
    source: str
    stopped_by: str | None
    group_state: str
    logs: tuple[str, ...] = field(default_factory=tuple)
