"""Packaged JSON Schema discovery for typed core CLI machine output."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Any, TypeAlias

from pydantic import JsonValue, TypeAdapter

from .cli_output.dev import (
    DevEnsureOutput,
    DevListOutput,
    DevActOutput,
    DevReconcileOutput,
    DevIdentityOutput,
    DevStatusOutput,
    DevStopOutput,
)
from .cli_output.double import (
    DoubleEmitRuntimeUnavailableOutput,
    DoubleEmitOutput,
    DoubleObserveRuntimeUnavailableOutput,
    DoubleObserveOutput,
    DoubleStartRuntimeUnavailableOutput,
    DoubleStartOutput,
    DoubleStopRuntimeUnavailableOutput,
    DoubleStopOutput,
    DoubleValidateRuntimeUnavailableOutput,
    DoubleValidateOutput,
)
from .cli_output.project import InitApplyOutput, InitPlanOutput, RootStatusOutput
from .cli_output.model import CliUsageOutput, MachineError
from .cli_output.run import RunReceipt
from .cli_output.activity import (
    MonitorOutput,
    ManagedOutput,
    TerminationOutput,
    ExecutionLogsOutput,
    IntegrationSetupOutput,
)
from .cli_output.skills import SkillsOutput, AdoptionOutput


InitMachineOutput: TypeAlias = (
    InitPlanOutput | InitApplyOutput | MachineError | CliUsageOutput
)
StatusMachineOutput: TypeAlias = RootStatusOutput | MachineError | CliUsageOutput
DevIdentityMachineOutput: TypeAlias = DevIdentityOutput | MachineError | CliUsageOutput
DevStatusMachineOutput: TypeAlias = DevStatusOutput | MachineError | CliUsageOutput
DevEnsureMachineOutput: TypeAlias = DevEnsureOutput | MachineError | CliUsageOutput
DevStopMachineOutput: TypeAlias = DevStopOutput | MachineError | CliUsageOutput
RunMachineOutput: TypeAlias = RunReceipt | MachineError | CliUsageOutput
DoubleValidateMachineOutput: TypeAlias = (
    DoubleValidateOutput
    | DoubleValidateRuntimeUnavailableOutput
    | MachineError
    | CliUsageOutput
)
DoubleStartMachineOutput: TypeAlias = (
    DoubleStartOutput
    | DoubleStartRuntimeUnavailableOutput
    | MachineError
    | CliUsageOutput
)
DoubleEmitMachineOutput: TypeAlias = (
    DoubleEmitOutput
    | DoubleEmitRuntimeUnavailableOutput
    | MachineError
    | CliUsageOutput
)
DoubleObserveMachineOutput: TypeAlias = (
    DoubleObserveOutput
    | DoubleObserveRuntimeUnavailableOutput
    | MachineError
    | CliUsageOutput
)
DoubleStopMachineOutput: TypeAlias = (
    DoubleStopOutput
    | DoubleStopRuntimeUnavailableOutput
    | MachineError
    | CliUsageOutput
)

RegisteredMachineOutput: TypeAlias = (
    MonitorOutput
    | ManagedOutput
    | TerminationOutput
    | SkillsOutput
    | AdoptionOutput
    | InitPlanOutput
    | InitApplyOutput
    | RootStatusOutput
    | DevIdentityOutput
    | DevListOutput
    | DevActOutput
    | DevReconcileOutput
    | DevStatusOutput
    | DevEnsureOutput
    | DevStopOutput
    | RunReceipt
    | DoubleValidateOutput
    | DoubleStartOutput
    | DoubleEmitOutput
    | DoubleObserveOutput
    | DoubleStopOutput
    | DoubleValidateRuntimeUnavailableOutput
    | DoubleStartRuntimeUnavailableOutput
    | DoubleEmitRuntimeUnavailableOutput
    | DoubleObserveRuntimeUnavailableOutput
    | DoubleStopRuntimeUnavailableOutput
    | MachineError
    | CliUsageOutput
)


@dataclass(frozen=True)
class OutputSchemaSpec:
    result_schema_version: int
    adapter: TypeAdapter[Any]


OUTPUT_SCHEMA_SPECS = {
    "dev-logs": OutputSchemaSpec(
        1, TypeAdapter(ExecutionLogsOutput | MachineError | CliUsageOutput)
    ),
    "dev-integrate": OutputSchemaSpec(
        1, TypeAdapter(IntegrationSetupOutput | MachineError | CliUsageOutput)
    ),
    "dev-monitor": OutputSchemaSpec(
        3, TypeAdapter(MonitorOutput | MachineError | CliUsageOutput)
    ),
    "dev-exec": OutputSchemaSpec(
        1, TypeAdapter(ManagedOutput | MachineError | CliUsageOutput)
    ),
    "dev-terminate": OutputSchemaSpec(
        1, TypeAdapter(TerminationOutput | MachineError | CliUsageOutput)
    ),
    "skills": OutputSchemaSpec(
        1, TypeAdapter(SkillsOutput | AdoptionOutput | MachineError | CliUsageOutput)
    ),
    "init": OutputSchemaSpec(4, TypeAdapter(InitMachineOutput)),
    "status": OutputSchemaSpec(4, TypeAdapter(StatusMachineOutput)),
    "dev-identity": OutputSchemaSpec(3, TypeAdapter(DevIdentityMachineOutput)),
    "dev-status": OutputSchemaSpec(4, TypeAdapter(DevStatusMachineOutput)),
    "dev-ensure": OutputSchemaSpec(3, TypeAdapter(DevEnsureMachineOutput)),
    "dev-stop": OutputSchemaSpec(3, TypeAdapter(DevStopMachineOutput)),
    "dev-list": OutputSchemaSpec(
        1, TypeAdapter(DevListOutput | MachineError | CliUsageOutput)
    ),
    "dev-act": OutputSchemaSpec(
        1, TypeAdapter(DevActOutput | MachineError | CliUsageOutput)
    ),
    "dev-reconcile": OutputSchemaSpec(
        1, TypeAdapter(DevReconcileOutput | MachineError | CliUsageOutput)
    ),
    "run": OutputSchemaSpec(2, TypeAdapter(RunMachineOutput)),
    "double-validate": OutputSchemaSpec(1, TypeAdapter(DoubleValidateMachineOutput)),
    "double-start": OutputSchemaSpec(1, TypeAdapter(DoubleStartMachineOutput)),
    "double-emit": OutputSchemaSpec(1, TypeAdapter(DoubleEmitMachineOutput)),
    "double-observe": OutputSchemaSpec(1, TypeAdapter(DoubleObserveMachineOutput)),
    "double-stop": OutputSchemaSpec(1, TypeAdapter(DoubleStopMachineOutput)),
}
OUTPUT_SCHEMA_KEYS = tuple(OUTPUT_SCHEMA_SPECS)


def generate_output_schema(key: str) -> dict[str, JsonValue]:
    """Generate one deterministic schema from the registered serialization model."""

    try:
        spec = OUTPUT_SCHEMA_SPECS[key]
    except KeyError as error:
        raise ValueError(f"Unknown output schema key: {key}") from error
    generated = spec.adapter.json_schema(mode="serialization")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"urn:svc:cli-output:{key}:v{spec.result_schema_version}",
        "title": f"SVC {key} machine output",
        "x-svc-result-schema-version": spec.result_schema_version,
        **generated,
    }


def read_output_schema(key: str) -> dict[str, JsonValue]:
    """Read the packaged projection returned to consumers by --json-schema."""

    if key not in OUTPUT_SCHEMA_SPECS:
        raise ValueError(f"Unknown output schema key: {key}")
    resource = resources.files("svc_cli").joinpath(
        "data", "output-schemas", f"{key}.json"
    )
    value = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Packaged output schema {key} is not a JSON object")
    return value
