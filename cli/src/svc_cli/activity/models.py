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
    swap_used_bytes: int | None = None
    swap_total_bytes: int | None = None
    compressed_bytes: int | None = None
    page_size_bytes: int | None = None
    pageins_per_second: float | None = None
    pageouts_per_second: float | None = None
    swapins_per_second: float | None = None
    swapouts_per_second: float | None = None
    compressions_per_second: float | None = None
    decompressions_per_second: float | None = None


@dataclass(frozen=True)
class ProcessUsage:
    cpu_percent: float
    rss_bytes: int
    process_count: int
    scope: str = "verified-current-descendants"
    memory_footprint_bytes: int | None = None
    disk_read_bytes_per_second: float | None = None
    disk_write_bytes_per_second: float | None = None
    pageins_per_second: float | None = None
    complete: bool = True
    issues: tuple[str, ...] = ()


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
    project_path: str | None = None
    project_source: str = "unassigned"


@dataclass(frozen=True)
class ResourceActivity:
    execution_id: str
    project_path: str | None
    entry_id: str
    resource: str
    usage: ProcessUsage | None


@dataclass(frozen=True)
class ProjectActivity:
    project_path: str | None
    execution_count: int
    resource_count: int
    usage: ProcessUsage | None
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActivitySnapshot:
    pressure: HostPressure
    executions: tuple[ExecutionActivity, ...]
    issues: tuple[str, ...] = ()
    projects: tuple[ProjectActivity, ...] = ()
    resources: tuple[ResourceActivity, ...] = ()


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
