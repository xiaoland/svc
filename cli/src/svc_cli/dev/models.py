"""Resource-domain facts shared by CLI projections and execution records."""

from __future__ import annotations

import json
import math
from typing import Literal, Any
from pydantic import Field, JsonValue
from ..model import ValueModel
from ..errors import Failure
from ..workspace import WorkspaceIdentity
from ..config import ControlTrait


class Observation(ValueModel):
    key: str
    label: str
    state: Literal["satisfied", "unsatisfied", "unknown"]
    source: str
    checked_at: str
    data_at: str | None = None
    expires_at: str | None = None
    stale: bool = False
    value: JsonValue = None
    message: str | None = None
    instance: str | None = None
    error: Failure | None = None


class ActionDescription(ValueModel):
    key: str
    kind: Literal["manual", "exec"]
    intent: str
    traits: tuple[ControlTrait, ...]
    effect_scope: str
    data_effect: Literal["unchanged", "modify", "delete", "unknown"]
    completion: Literal["exit", "ready", "submitted"] | None = None
    interruption: Literal["wait", "terminate"] | None = None
    convergent: bool = False
    steps: tuple[str, ...] = ()


class Coordination(ValueModel):
    coordination_id: str
    scope: Literal["worktree", "repository", "host"]
    scope_id: str
    workspace_instance: str
    owner_repo: str
    owner_resource: str


class ExecutionView(ValueModel):
    execution_id: str
    state: str
    phase: Literal["pending", "settled", "owner-lost"]
    acknowledged: bool = False
    action: str | None = None
    entry_id: str | None = None
    exit_code: int | None = None
    log_path: str


class ObservationDescription(ValueModel):
    key: str
    label: str
    automatic: bool
    purpose: str
    provider: str


class ResourceView(ValueModel):
    resource: str
    label: str
    entry_id: str
    source: str
    declaration_digest: str
    coordination: Coordination | None
    controller: str | None = None
    access: tuple[str, ...] = ()
    relations: tuple[str, ...] = ()
    actions: tuple[ActionDescription, ...] = ()
    observations: tuple[Observation, ...] = ()
    facets: tuple[ObservationDescription, ...] = ()
    execution: ExecutionView | None = None
    error: Failure | None = None


class CatalogResult(ValueModel):
    workspace: WorkspaceIdentity
    status: Literal["ok", "partial", "not-configured"]
    resources: tuple[ResourceView, ...]


class OperationReference(ValueModel):
    id: str = Field(min_length=1, max_length=512)
    url: str | None = Field(default=None, max_length=2048)


class Submission(ValueModel):
    schema_version: Literal[1]
    operation: OperationReference


class ActionReceipt(ValueModel):
    resource: str
    entry_id: str
    action: str
    declaration_digest: str
    coordination: Coordination | None
    status: Literal[
        "completed",
        "ready",
        "accepted",
        "reused",
        "busy",
        "manual",
        "absent",
        "stale",
        "condition-unmet",
        "owner-lost",
        "failed",
        "interrupted",
        "acknowledged",
        "nothing-to-reconcile",
    ]
    message: str
    execution: ExecutionView | None = None
    observations: tuple[Observation, ...] = ()
    operation: OperationReference | None = None
    steps: tuple[str, ...] = ()
    error: Failure | None = None
    requested_signal: str | None = None
    joined: bool = False

    @property
    def exit_code(self) -> int:
        if self.status == "interrupted":
            return 130
        if self.status == "failed":
            return 4
        if self.status in {
            "completed",
            "ready",
            "accepted",
            "reused",
            "acknowledged",
            "nothing-to-reconcile",
        }:
            return 0
        return 3


def parse_json(raw: str | bytes) -> Any:
    """Reject ambiguous provider and receipt JSON before model validation."""

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON field")
            value[key] = item
        return value

    def nonfinite(value: str) -> object:
        raise ValueError(f"non-finite JSON value: {value}")

    def finite(value: str) -> float:
        number = float(value)
        if not math.isfinite(number):
            nonfinite(value)
        return number

    return json.loads(
        raw, object_pairs_hook=unique, parse_constant=nonfinite, parse_float=finite
    )
