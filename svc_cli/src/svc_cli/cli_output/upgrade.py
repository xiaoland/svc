"""Public upgrade output and projections from upgrade services."""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import Field

from .model import MachineModel
from ..plans import PlanAction
from ..upgrade import (
    ConfigGuideReference as ServiceConfigGuideReference,
    ConfigRemainingTarget as ServiceConfigRemainingTarget,
    CorpusGuideReference as ServiceCorpusGuideReference,
    CorpusRelease as ServiceCorpusRelease,
    CorpusRemainingTarget as ServiceCorpusRemainingTarget,
    RemainingTarget as ServiceRemainingTarget,
    UpgradeApplyResult,
    UpgradeConfigurationDetails as ServiceUpgradeConfigurationDetails,
    UpgradeCorpusDetails as ServiceUpgradeCorpusDetails,
    UpgradeMigration as ServiceUpgradeMigration,
    UpgradeOperation,
    UpgradePlan,
    UpgradeTarget,
    UpgradeVerification as ServiceUpgradeVerification,
)
from .common import BlockerOutput, FileStateOutput, project_blocker, project_file_state


class ConfigGuideReference(MachineModel):
    id: str
    sha256: str


class CorpusGuideReference(MachineModel):
    path: str
    sha256: str


MigrationGuideReference: TypeAlias = ConfigGuideReference | CorpusGuideReference


class UpgradeConfigurationDetails(MachineModel):
    config_schema: int | None = Field(
        default=None,
        alias="schema",
        serialization_alias="schema",
        exclude_if=lambda value: value is None,
    )
    status: Literal["current"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    from_schema: int | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    to_schema: int | None = Field(default=None, exclude_if=lambda value: value is None)
    guidance: tuple[ConfigGuideReference, ...] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class CorpusReleaseOutput(MachineModel):
    version: str
    migration: Literal["guide", "not-required"]
    guides: tuple[CorpusGuideReference, ...] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class UpgradeCorpusDetails(MachineModel):
    project_version: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    available_version: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    status: Literal["current"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    from_version: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    to_version: str | None = Field(default=None, exclude_if=lambda value: value is None)
    releases: tuple[CorpusReleaseOutput, ...] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class UpgradeDetails(MachineModel):
    configuration: UpgradeConfigurationDetails | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    corpus: UpgradeCorpusDetails | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class CorpusRemainingTarget(MachineModel):
    target: Literal["corpus"] = "corpus"
    status: Literal["pending", "blocked"]
    from_version: str
    to_version: str
    code: str | None = Field(default=None, exclude_if=lambda value: value is None)


class ConfigRemainingTarget(MachineModel):
    target: Literal["config"] = "config"
    status: Literal["pending", "blocked"]
    from_schema: int
    to_schema: int


RemainingTarget: TypeAlias = CorpusRemainingTarget | ConfigRemainingTarget


class UpgradeOperationOutput(MachineModel):
    path: str
    action: PlanAction
    reason: str
    before: FileStateOutput
    after: FileStateOutput
    surface: Literal["configuration", "project-corpus-baseline"]
    extent: Literal["whole-file", "json-field"]


class UpgradePlanOutput(MachineModel):
    schema_version: Literal[1] = 1
    command: Literal["upgrade"] = "upgrade"
    mode: Literal["plan"] = "plan"
    status: Literal["noop", "blocked", "ready", "migration-required"]
    repo: str
    target: UpgradeTarget | None
    operations: tuple[UpgradeOperationOutput, ...]
    remaining_targets: tuple[RemainingTarget, ...]
    configuration: UpgradeConfigurationDetails | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    corpus: UpgradeCorpusDetails | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    blockers: tuple[BlockerOutput, ...] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    plan_digest: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class UpgradeMigrationOutput(MachineModel):
    disposition: Literal["caller-asserted", "not-required"]
    guidance: tuple[MigrationGuideReference, ...]


class UpgradeVerificationOutput(MachineModel):
    scope: Literal["effective-schema-3-configuration", "project-corpus-baseline"]
    status: Literal["passed"] = "passed"


class UpgradeApplyOutput(MachineModel):
    schema_version: Literal[1] = 1
    command: Literal["upgrade"] = "upgrade"
    mode: Literal["apply"] = "apply"
    status: Literal["applied"] = "applied"
    repo: str
    target: UpgradeTarget
    plan_digest: str
    changed: int
    operations: tuple[UpgradeOperationOutput, ...]
    configuration: UpgradeConfigurationDetails | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    corpus: UpgradeCorpusDetails | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    migration: UpgradeMigrationOutput
    verification: UpgradeVerificationOutput
    remaining_targets: tuple[RemainingTarget, ...]


def project_upgrade_plan(plan: UpgradePlan) -> UpgradePlanOutput:
    return UpgradePlanOutput(
        status=plan.status,
        repo=str(plan.repo),
        target=plan.target,
        operations=tuple(_operation(value) for value in plan.operations()),
        remaining_targets=tuple(_remaining(value) for value in plan.remaining_targets),
        configuration=_configuration(plan.details.configuration),
        corpus=_corpus(plan.details.corpus),
        blockers=(
            tuple(project_blocker(value) for value in plan.blockers)
            if plan.blockers
            else None
        ),
        plan_digest=plan.digest,
    )


def project_upgrade_apply(result: UpgradeApplyResult) -> UpgradeApplyOutput:
    return UpgradeApplyOutput(
        repo=result.repo,
        target=result.target,
        plan_digest=result.plan_digest,
        changed=result.changed,
        operations=tuple(_operation(value) for value in result.operations),
        configuration=_configuration(result.configuration),
        corpus=_corpus(result.corpus),
        migration=_migration(result.migration),
        verification=UpgradeVerificationOutput(
            scope=result.verification.scope,
            status=result.verification.status,
        ),
        remaining_targets=tuple(
            _remaining(value) for value in result.remaining_targets
        ),
    )


def _configuration(
    value: ServiceUpgradeConfigurationDetails | None,
) -> UpgradeConfigurationDetails | None:
    if value is None:
        return None
    return UpgradeConfigurationDetails(
        config_schema=value.config_schema,
        status=value.status,
        from_schema=value.from_schema,
        to_schema=value.to_schema,
        guidance=(
            None
            if value.guidance is None
            else tuple(_config_guide(guide) for guide in value.guidance)
        ),
    )


def _corpus(value: ServiceUpgradeCorpusDetails | None) -> UpgradeCorpusDetails | None:
    if value is None:
        return None
    return UpgradeCorpusDetails(
        project_version=value.project_version,
        available_version=value.available_version,
        status=value.status,
        from_version=value.from_version,
        to_version=value.to_version,
        releases=(
            None
            if value.releases is None
            else tuple(_release(release) for release in value.releases)
        ),
    )


def _release(value: ServiceCorpusRelease) -> CorpusReleaseOutput:
    return CorpusReleaseOutput(
        version=value.version,
        migration=value.migration,
        guides=(
            None
            if value.guides is None
            else tuple(_corpus_guide(guide) for guide in value.guides)
        ),
    )


def _operation(value: UpgradeOperation) -> UpgradeOperationOutput:
    return UpgradeOperationOutput(
        path=value.path,
        action=value.action,
        reason=value.reason,
        before=project_file_state(value.before),
        after=project_file_state(value.after),
        surface=value.surface,
        extent=value.extent,
    )


def _remaining(value: ServiceRemainingTarget) -> RemainingTarget:
    if isinstance(value, ServiceConfigRemainingTarget):
        return ConfigRemainingTarget(
            status=value.status,
            from_schema=value.from_schema,
            to_schema=value.to_schema,
        )
    assert isinstance(value, ServiceCorpusRemainingTarget)
    return CorpusRemainingTarget(
        status=value.status,
        from_version=value.from_version,
        to_version=value.to_version,
        code=value.code,
    )


def _migration(value: ServiceUpgradeMigration) -> UpgradeMigrationOutput:
    return UpgradeMigrationOutput(
        disposition=value.disposition,
        guidance=tuple(_guide(guide) for guide in value.guidance),
    )


def _guide(
    value: ServiceConfigGuideReference | ServiceCorpusGuideReference,
) -> MigrationGuideReference:
    if isinstance(value, ServiceConfigGuideReference):
        return _config_guide(value)
    return _corpus_guide(value)


def _config_guide(value: ServiceConfigGuideReference) -> ConfigGuideReference:
    return ConfigGuideReference(id=value.id, sha256=value.sha256)


def _corpus_guide(value: ServiceCorpusGuideReference) -> CorpusGuideReference:
    return CorpusGuideReference(path=value.path, sha256=value.sha256)
