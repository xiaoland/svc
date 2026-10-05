"""Typed public projections for Skills management and project adoption."""

from __future__ import annotations

from typing import Literal

from .common import BlockerOutput, FileStateOutput, project_blocker, project_file_state
from .model import MachineModel, MachineErrorBody, project_failure
from ..errors import Failure
from ..plans import PlannedFileMutation
from ..skill_adoption import AdoptionPlan
from ..skills import (
    SkillInspection,
    SkillPlan,
    SkillApplyResult,
    SkillTarget,
    SkillStatus,
)


class SkillOperationOutput(MachineModel):
    path: str
    action: str
    reason: str
    before: FileStateOutput
    after: FileStateOutput


class SkillUnitOutput(MachineModel):
    name: str
    status: str
    installation_status: SkillStatus
    path: str
    actual_version: str | None = None
    recorded_version: str | None = None
    revision: str | None = None
    message: str | None = None
    operations: tuple[SkillOperationOutput, ...] = ()
    changed: int = 0
    error: MachineErrorBody | None = None


class SkillsTargetOutput(MachineModel):
    agent: Literal["codex", "claude"]
    scope: Literal["project", "global"]
    skills_root: str
    status: str
    units: tuple[SkillUnitOutput, ...]


class SkillsOutput(MachineModel):
    schema_version: Literal[1] = 1
    command: Literal[
        "skills install",
        "skills status",
        "skills check",
        "skills update",
        "skills remove",
    ]
    mode: Literal["plan", "apply", "status", "check"]
    status: Literal[
        "ready",
        "blocked",
        "noop",
        "applied",
        "failed",
        "partial",
        "current",
        "attention",
        "available",
        "absent",
    ]
    targets: tuple[SkillsTargetOutput, ...]
    plan_digest: str | None = None
    target_version: str | None = None
    release_notes: str | None = None
    migration_guidance: str | None = None


class AdoptionOutput(MachineModel):
    schema_version: Literal[1] = 1
    command: Literal["skills adopt", "skills unadopt"]
    mode: Literal["plan", "apply"]
    status: Literal["ready", "blocked", "noop", "applied"]
    repo: str
    agent: str
    skills_root: str
    entries: tuple[str, ...]
    plan_digest: str
    operations: tuple[SkillOperationOutput, ...]
    blockers: tuple[BlockerOutput, ...]


def operation(value: PlannedFileMutation) -> SkillOperationOutput:
    return SkillOperationOutput(
        path=value.path,
        action=value.action,
        reason=value.reason,
        before=project_file_state(value.before),
        after=project_file_state(value.after),
    )


def installation(
    value: SkillInspection,
    *,
    status: str | None = None,
    message: str | None = None,
    operations: tuple[SkillOperationOutput, ...] = (),
    changed: int = 0,
    failure: Failure | None = None,
) -> SkillUnitOutput:
    return SkillUnitOutput(
        name=value.name,
        status=status or value.status,
        installation_status=value.status,
        path=value.path,
        actual_version=value.actual_version,
        recorded_version=value.version,
        revision=value.revision,
        message=message or value.message,
        operations=operations,
        changed=changed,
        error=project_failure(failure) if failure is not None else None,
    )


def target_output(
    target: SkillTarget, status: str, units: tuple[SkillUnitOutput, ...]
) -> SkillsTargetOutput:
    return SkillsTargetOutput(
        agent=target.host,
        scope=target.scope,
        skills_root=str(target.skills_root),
        status=status,
        units=units,
    )


def planned(plan: SkillPlan) -> SkillsTargetOutput:
    return target_output(
        plan.target,
        plan.status,
        tuple(
            installation(
                unit.inspection,
                message=unit.error or unit.reason,
                operations=tuple(
                    operation(mutation) for mutation in unit.local_plan.mutations
                )
                if unit.local_plan
                else (),
            )
            for unit in plan.units
        ),
    )


def applied(target: SkillTarget, result: SkillApplyResult) -> SkillsTargetOutput:
    return target_output(
        target,
        result.status,
        tuple(
            installation(
                unit.inspection,
                status=unit.status,
                message=unit.message,
                changed=unit.changed,
                failure=unit.failure,
            )
            for unit in result.units
        ),
    )


def adoption(
    plan: AdoptionPlan, *, applied_status: Literal["noop", "applied"] | None = None
) -> AdoptionOutput:
    return AdoptionOutput(
        command="skills unadopt" if plan.remove else "skills adopt",
        mode="apply" if applied_status else "plan",
        status=applied_status or plan.local.status,
        repo=str(plan.local.repo),
        agent=plan.agent,
        skills_root=str(plan.skills_root),
        entries=plan.entries,
        plan_digest=plan.local.digest,
        operations=tuple(operation(value) for value in plan.local.mutations),
        blockers=tuple(project_blocker(value) for value in plan.local.blockers),
    )
