"""Public pressure, execution, and termination contracts."""

from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from .._execution import ExecutionState
from ..activity.models import ActivitySnapshot, ManagedResult, TerminationResult
from .model import MachineModel


class PressureOutput(MachineModel):
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
    issues: tuple[str, ...]


class ProcessUsageOutput(MachineModel):
    cpu_percent: float
    rss_bytes: int
    process_count: int
    scope: Literal["verified-current-descendants"]


class ExecutionActivityOutput(MachineModel):
    execution_id: str
    domain: str
    operation: str
    label: str
    source: str
    cwd: str
    argv: tuple[str, ...]
    state: ExecutionState
    started_at: str
    finished_at: str | None
    exit_code: int | None
    can_terminate: bool
    termination_requested: str | None
    group_state: str | None
    usage: ProcessUsageOutput | None
    logs: tuple[str, ...]
    issues: tuple[str, ...]


class MonitorOutput(MachineModel):
    schema_version: Literal[1] = 1
    command: Literal["dev monitor"] = "dev monitor"
    pressure: PressureOutput
    executions: tuple[ExecutionActivityOutput, ...]
    issues: tuple[str, ...]


class ManagedOutput(MachineModel):
    schema_version: Literal[1] = 1
    command: Literal["dev exec"] = "dev exec"
    execution_id: str
    label: str
    source: str
    state: ExecutionState
    exit_code: int | None
    stopped_by: str | None
    group_state: str
    logs: tuple[str, ...]
    retry_allowed: Literal[False] | None


class TerminationOutput(MachineModel):
    schema_version: Literal[1] = 1
    command: Literal["dev terminate"] = "dev terminate"
    execution_id: str
    status: str
    mode: str
    message: str


def project_monitor(snapshot: ActivitySnapshot) -> MonitorOutput:
    return MonitorOutput(
        pressure=PressureOutput(**asdict(snapshot.pressure)),
        executions=tuple(
            ExecutionActivityOutput(
                execution_id=item.record.execution_id,
                domain=item.record.domain,
                operation=item.record.operation,
                label=item.label,
                source=item.source,
                cwd=item.record.cwd,
                argv=item.record.argv,
                state=item.record.state,
                started_at=item.record.started_at,
                finished_at=item.record.finished_at,
                exit_code=item.record.exit_code,
                can_terminate=item.can_terminate,
                termination_requested=item.termination_requested,
                group_state=item.group_state,
                usage=ProcessUsageOutput(**asdict(item.usage)) if item.usage else None,
                logs=item.logs,
                issues=item.issues,
            )
            for item in snapshot.executions
        ),
        issues=snapshot.issues,
    )


def project_managed(result: ManagedResult) -> ManagedOutput:
    return ManagedOutput(
        execution_id=result.record.execution_id,
        label=result.label,
        source=result.source,
        state=result.record.state,
        exit_code=result.record.exit_code,
        stopped_by=result.stopped_by,
        group_state=result.group_state,
        logs=result.logs,
        retry_allowed=False if result.stopped_by else None,
    )


def project_termination(result: TerminationResult) -> TerminationOutput:
    return TerminationOutput(**asdict(result))
