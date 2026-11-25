"""Versioned public projections of resource-domain facts."""

from typing import Literal
from ..dev.models import ActionReceipt, CatalogResult
from ..workspace import WorkspaceIdentity
from .model import MachineModel


class DevIdentityOutput(MachineModel):
    schema_version: Literal[3] = 3
    command: Literal["dev identity"] = "dev identity"
    workspace: WorkspaceIdentity
    identities: Literal["entry-coordination-observed-instance"] = (
        "entry-coordination-observed-instance"
    )


class DevListOutput(CatalogResult, MachineModel):
    machine_exclude_none = True
    schema_version: Literal[1] = 1
    command: Literal["dev list"] = "dev list"


class DevStatusOutput(CatalogResult, MachineModel):
    machine_exclude_none = True
    schema_version: Literal[4] = 4
    command: Literal["dev status"] = "dev status"


class DevActOutput(ActionReceipt, MachineModel):
    machine_exclude_none = True
    schema_version: Literal[1] = 1
    command: Literal["dev act"] = "dev act"


class DevEnsureOutput(ActionReceipt, MachineModel):
    machine_exclude_none = True
    schema_version: Literal[3] = 3
    command: Literal["dev ensure"] = "dev ensure"


class DevStopOutput(ActionReceipt, MachineModel):
    machine_exclude_none = True
    schema_version: Literal[3] = 3
    command: Literal["dev stop"] = "dev stop"


class DevReconcileOutput(ActionReceipt, MachineModel):
    machine_exclude_none = True
    schema_version: Literal[1] = 1
    command: Literal["dev reconcile"] = "dev reconcile"


def project_dev_identity(value: WorkspaceIdentity) -> DevIdentityOutput:
    return DevIdentityOutput(workspace=value)


def project_catalog(
    value: CatalogResult, *, observe: bool
) -> DevStatusOutput | DevListOutput:
    model = DevStatusOutput if observe else DevListOutput
    return model(**value.model_dump())


def project_action(
    value: ActionReceipt, *, command: str
) -> DevActOutput | DevEnsureOutput | DevStopOutput | DevReconcileOutput:
    models = {
        "act": DevActOutput,
        "ensure": DevEnsureOutput,
        "stop": DevStopOutput,
        "reconcile": DevReconcileOutput,
    }
    return models[command](**value.model_dump())
