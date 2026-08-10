"""Runtime-neutral value models for BSL compilation and double runs."""

from __future__ import annotations

import math
from typing import Any, Literal, TypeAlias

from pydantic import JsonValue

from ..model import ValueModel


PathPart: TypeAlias = str | int
NodeKind: TypeAlias = Literal[
    "literal", "match", "capture", "example", "derived", "generated", "managed"
]


class SourceLocation(ValueModel):
    line: int
    column: int
    path: tuple[PathPart, ...]


class Snapshot(ValueModel):
    logical_path: str
    sha256: str
    bytes: int
    content_base64: str


class Provenance(ValueModel):
    kind: Literal[
        "consumer-requirement",
        "provider-contract",
        "provider-documentation",
        "provider-capture",
        "synthetic",
    ]
    source: str
    sanitized: bool | None = None
    snapshot_sha256: str | None = None


class Matcher(ValueModel):
    kind: Literal["exact", "enum", "range", "regex", "semantic"]
    value: JsonValue | None = None
    values: tuple[JsonValue, ...] | None = None
    minimum: int | float | None = None
    maximum: int | float | None = None
    pattern: str | None = None
    semantic: str | None = None
    using: str | None = None


class ValueNode(ValueModel):
    path: tuple[PathPart, ...]
    kind: NodeKind
    value: JsonValue | None = None
    matcher: Matcher | None = None
    name: str | None = None
    expression: str | None = None
    semantic: str | None = None
    using: str | None = None
    options: dict[str, JsonValue] | None = None
    bind: str | None = None
    validator: Matcher | None = None
    managed_snapshot: Snapshot | None = None
    media_type: str | None = None
    location: SourceLocation | None = None


class Body(ValueModel):
    kind: Literal["structured", "form-urlencoded", "raw"]
    template: JsonValue | None = None
    nodes: tuple[ValueNode, ...] = ()
    raw: Snapshot | None = None
    media_type: str | None = None


class Materializer(ValueModel):
    argv: tuple[str, ...]
    cwd: str
    env: dict[str, str]
    timeout_ms: int
    max_output_bytes: int


class Request(ValueModel):
    method: str
    path: str
    query: dict[str, JsonValue]
    query_nodes: tuple[ValueNode, ...] = ()
    headers: dict[str, JsonValue]
    header_nodes: tuple[ValueNode, ...] = ()
    body: Body | None = None
    materializer: Materializer | None = None


class Response(ValueModel):
    status: int
    headers: dict[str, JsonValue]
    header_nodes: tuple[ValueNode, ...] = ()
    body: Body | None = None
    materializer: Materializer | None = None


class Interaction(ValueModel):
    name: str
    provenance: Provenance
    request: Request
    response: Response


class Event(ValueModel):
    name: str
    target: str
    provenance: Provenance
    request: Request


class SchemaResource(ValueModel):
    uri: str
    document: JsonValue
    snapshot_sha256: str


class Contract(ValueModel):
    source: Snapshot
    method: str
    path: str
    request_schema: JsonValue | None = None
    response_schemas: dict[str, JsonValue]
    schema_resources: tuple[SchemaResource, ...]


class Scenario(ValueModel):
    language: Literal["svc.double/v0"] = "svc.double/v0"
    module_path: str
    workspace_root: str
    name: str
    claim: str
    boundary_name: str
    event_target_policy: Literal["loopback-only", "explicit-remote"]
    interactions: tuple[Interaction, ...]
    events: tuple[Event, ...]
    contract: Contract | None
    snapshots: tuple[Snapshot, ...]
    fidelity: tuple[str, ...]
    nonclaims: tuple[str, ...]
    scenario_digest: str
    uses_materializer: bool


class Replay(ValueModel):
    seed: int
    clock: str
    generators: tuple[str, ...]
    validators: tuple[str, ...]
    runtime: str


class TargetBinding(ValueModel):
    name: str
    origin: str
    remote: bool


class JournalEntry(ValueModel):
    sequence: int
    at: str
    kind: Literal["request", "event", "runtime"]
    status: str
    facts: dict[str, JsonValue]


class Journal(ValueModel):
    total: int
    retained: int
    omitted: int
    entries: tuple[JournalEntry, ...]


class RunObservation(ValueModel):
    run_id: str
    scenario_name: str
    status: Literal["bootstrapping", "ready", "stopping", "stopped", "failed"]
    sealed: bool
    responder_url: str | None
    scenario_digest: str
    run_context_digest: str
    replay: Replay
    targets: tuple[TargetBinding, ...]
    bindings: dict[str, JsonValue]
    journal: Journal
    nonclaims: tuple[str, ...]
    failure: str | None = None


class RunRecord(ValueModel):
    schema_version: Literal[1] = 1
    run_id: str
    workspace_root: str
    workspace_instance: str
    run_directory: str
    manifest_path: str
    scenario_digest: str
    run_context_digest: str
    replay: Replay
    targets: tuple[TargetBinding, ...]
    control_url: str
    control_capability: str
    observation_path: str
    created_at: str


class Diagnostic(ValueModel):
    code: str
    message: str
    path: str | None = None
    line: int | None = None
    column: int | None = None


class ValidateResult(ValueModel):
    command: Literal["double validate"] = "double validate"
    module: str
    scenario_name: str | None = None
    claim: str | None = None
    valid: bool
    scenario_digest: str | None = None
    fidelity: tuple[str, ...]
    nonclaims: tuple[str, ...]
    snapshots: tuple[Snapshot, ...]
    diagnostic: Diagnostic | None = None


class StartResult(ValueModel):
    command: Literal["double start"] = "double start"
    run_id: str
    module: str
    scenario_name: str
    responder_url: str
    scenario_digest: str
    run_context_digest: str
    replay: Replay
    targets: tuple[TargetBinding, ...]
    nonclaims: tuple[str, ...]


class EmitResult(ValueModel):
    command: Literal["double emit"] = "double emit"
    run_id: str
    event: str
    status: Literal[
        "acknowledged",
        "not-acknowledged",
        "transport-failed",
        "control-unavailable",
    ]
    target: str | None = None
    http_status: int | None = None
    reason: str | None = None


class ObserveResult(ValueModel):
    command: Literal["double observe"] = "double observe"
    observation: RunObservation
    authority: Literal["active-carrier", "sealed-snapshot", "unsealed-projection"]
    control_status: Literal["available", "not-required", "control-unavailable"]


class StopResult(ValueModel):
    command: Literal["double stop"] = "double stop"
    run_id: str
    status: Literal["stopped", "control-unavailable"]
    sealed: bool
    idempotent: bool
    observation: RunObservation | None = None


def strict_json_value(value: Any) -> JsonValue:
    """Narrow an already validated Python JSON value for model construction."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError("JSON numbers must be finite")
        return value
    if isinstance(value, list):
        return [strict_json_value(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("JSON object keys must be strings")
        return {key: strict_json_value(item) for key, item in value.items()}
    raise TypeError(f"value is not JSON-compatible: {type(value).__name__}")
