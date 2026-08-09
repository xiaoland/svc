"""Packaged JSON Schema discovery for typed core CLI machine output."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any, TypeAlias

from pydantic import JsonValue, TypeAdapter

from .dev.runtime import (
    DevEnsureOutput,
    DevIdentityOutput,
    DevStatusOutput,
    DevStopOutput,
)
from .lookup import LookupOutput
from .machine import CliUsageOutput, MachineError
from .project import InitApplyOutput, InitPlanOutput, RootStatusOutput
from .run.runtime import RunReceipt
from .upgrade import UpgradeApplyOutput, UpgradePlanOutput


LookupMachineOutput: TypeAlias = LookupOutput | MachineError | CliUsageOutput
InitMachineOutput: TypeAlias = (
    InitPlanOutput | InitApplyOutput | MachineError | CliUsageOutput
)
StatusMachineOutput: TypeAlias = RootStatusOutput | MachineError | CliUsageOutput
UpgradeMachineOutput: TypeAlias = (
    UpgradePlanOutput | UpgradeApplyOutput | MachineError | CliUsageOutput
)
DevIdentityMachineOutput: TypeAlias = DevIdentityOutput | MachineError | CliUsageOutput
DevStatusMachineOutput: TypeAlias = DevStatusOutput | MachineError | CliUsageOutput
DevEnsureMachineOutput: TypeAlias = DevEnsureOutput | MachineError | CliUsageOutput
DevStopMachineOutput: TypeAlias = DevStopOutput | MachineError | CliUsageOutput
RunMachineOutput: TypeAlias = RunReceipt | MachineError | CliUsageOutput

RegisteredMachineOutput: TypeAlias = (
    LookupOutput
    | InitPlanOutput
    | InitApplyOutput
    | RootStatusOutput
    | UpgradePlanOutput
    | UpgradeApplyOutput
    | DevIdentityOutput
    | DevStatusOutput
    | DevEnsureOutput
    | DevStopOutput
    | RunReceipt
    | MachineError
    | CliUsageOutput
)


OUTPUT_SCHEMA_KEYS = (
    "lookup",
    "init",
    "status",
    "upgrade",
    "dev-identity",
    "dev-status",
    "dev-ensure",
    "dev-stop",
    "run",
)

_RESULT_SCHEMA_VERSIONS = {
    "lookup": 2,
    "init": 2,
    "status": 2,
    "upgrade": 1,
    "dev-identity": 2,
    "dev-status": 2,
    "dev-ensure": 2,
    "dev-stop": 2,
    "run": 2,
}

_ADAPTERS: dict[str, TypeAdapter[Any]] = {
    "lookup": TypeAdapter(LookupMachineOutput),
    "init": TypeAdapter(InitMachineOutput),
    "status": TypeAdapter(StatusMachineOutput),
    "upgrade": TypeAdapter(UpgradeMachineOutput),
    "dev-identity": TypeAdapter(DevIdentityMachineOutput),
    "dev-status": TypeAdapter(DevStatusMachineOutput),
    "dev-ensure": TypeAdapter(DevEnsureMachineOutput),
    "dev-stop": TypeAdapter(DevStopMachineOutput),
    "run": TypeAdapter(RunMachineOutput),
}


def generate_output_schema(key: str) -> dict[str, JsonValue]:
    """Generate one deterministic schema from the registered serialization model."""

    try:
        adapter = _ADAPTERS[key]
        version = _RESULT_SCHEMA_VERSIONS[key]
    except KeyError as error:
        raise ValueError(f"Unknown output schema key: {key}") from error
    generated = adapter.json_schema(mode="serialization")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"urn:svc:cli-output:{key}:v{version}",
        "title": f"SVC {key} machine output",
        "x-svc-result-schema-version": version,
        **generated,
    }


def read_output_schema(key: str) -> dict[str, JsonValue]:
    """Read the packaged projection returned to consumers by --json-schema."""

    if key not in _ADAPTERS:
        raise ValueError(f"Unknown output schema key: {key}")
    resource = resources.files("svc_cli").joinpath(
        "data", "output-schemas", f"{key}.json"
    )
    value = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Packaged output schema {key} is not a JSON object")
    return value
