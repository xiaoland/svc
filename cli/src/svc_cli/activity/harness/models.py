"""External execution facts, separate from SVC's mechanical records."""

from dataclasses import dataclass

from ..models import ProcessUsage


@dataclass(frozen=True)
class ExternalExecution:
    execution_id: str
    provider: str
    native_id: str
    instance_id: str
    label: str
    command: str
    cwd: str
    state: str
    scope: str
    started_at: str
    can_terminate: bool
    can_read_logs: bool
    stop_description: str
    process_id: int | None = None
    usage: ProcessUsage | None = None
    project_path: str | None = None
    issues: tuple[str, ...] = ()
    local_owner_pid: int | None = None


@dataclass(frozen=True)
class HarnessStatus:
    provider: str
    state: str
    message: str
    instances: int = 0


@dataclass(frozen=True)
class HarnessSnapshot:
    executions: tuple[ExternalExecution, ...]
    integrations: tuple[HarnessStatus, ...]


@dataclass(frozen=True)
class ExecutionLogs:
    execution_id: str
    text: str
    truncated: bool


@dataclass(frozen=True)
class IntegrationSetup:
    provider: str
    state: str
    message: str
