"""One project-upgrade interface over independent config and Corpus plans."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .catalog import Catalog, canonical_json, sha256_bytes
from .config import (
    CONFIG_SCHEMA_VERSION,
    LOCAL_CONFIG_FILE,
    ConfigError,
    LegacyProjectConfig,
    ProjectConfig,
    load_config,
    parse_json_document,
)
from .config_migration import ConfigMigrationError, migrate_v2_to_v3
from .errors import SvcError
from .plans import Blocker, LocalPlan, PlannedFileMutation, apply_local_plan, make_write
from .project import PROJECT_FILE, parse_project_state, replace_corpus_baseline
from .release import catalog
from .resources import read_config_migration_descriptor, read_document


UPGRADE_SCHEMA_VERSION = 1
UpgradeTarget = Literal["config", "corpus"]


@dataclass(frozen=True)
class ConfigGuide:
    identifier: str
    sha256: str
    text: str

    def reference(self) -> dict[str, object]:
        return {"id": self.identifier, "sha256": self.sha256}


@dataclass(frozen=True)
class UpgradePlan:
    repo: Path
    target: UpgradeTarget | None
    status: str
    mutations: tuple[PlannedFileMutation, ...]
    blockers: tuple[Blocker, ...]
    details: dict[str, object]
    remaining_targets: tuple[dict[str, object], ...] = ()
    automatic_changes: tuple[str, ...] = ()
    config_guides: tuple[ConfigGuide, ...] = ()
    local_plan: LocalPlan | None = None

    @property
    def digest(self) -> str | None:
        if self.status not in {"ready", "migration-required"}:
            return None
        return sha256_bytes(canonical_json(self.signature()))

    def signature(self) -> dict[str, object]:
        return {
            "schema_version": UPGRADE_SCHEMA_VERSION,
            "command": "upgrade",
            "repo": str(self.repo),
            "target": self.target,
            "status": self.status,
            "details": self.details,
            "remaining_targets": list(self.remaining_targets),
            "automatic_changes": list(self.automatic_changes),
            "local_plan": None
            if self.local_plan is None
            else self.local_plan.signature(),
        }

    def operations(self) -> list[dict[str, object]]:
        if self.target is None:
            return []
        surface = (
            "configuration" if self.target == "config" else "project-corpus-baseline"
        )
        extent = "whole-file" if self.target == "config" else "json-field"
        return [
            {
                **mutation.as_dict(),
                "surface": surface,
                "extent": extent,
            }
            for mutation in self.mutations
        ]

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "schema_version": UPGRADE_SCHEMA_VERSION,
            "command": "upgrade",
            "mode": "plan",
            "status": self.status,
            "repo": str(self.repo),
            "target": self.target,
            "operations": self.operations(),
            "remaining_targets": list(self.remaining_targets),
            **self.details,
        }
        if self.blockers:
            result["blockers"] = [blocker.as_dict() for blocker in self.blockers]
        if self.digest is not None:
            result["plan_digest"] = self.digest
        return result


def plan_upgrade(repo: Path, target: UpgradeTarget | None = None) -> UpgradePlan:
    root = repo.resolve()
    if not root.is_dir():
        raise SvcError(
            "repo-not-directory",
            "Project root is not a directory.",
            {"repo": str(repo)},
        )
    available = catalog()
    if target == "config":
        return _plan_config(root, available)
    if target == "corpus":
        return _plan_corpus(root, available)

    config_plan = _plan_config(root, available)
    if config_plan.status != "noop":
        return config_plan
    corpus_plan = _plan_corpus(root, available)
    if corpus_plan.status != "noop":
        return corpus_plan
    return UpgradePlan(
        root,
        None,
        "noop",
        (),
        (),
        {
            "configuration": {"schema": CONFIG_SCHEMA_VERSION, "status": "current"},
            "corpus": {
                "project_version": available.corpus_version,
                "available_version": available.corpus_version,
                "status": "current",
            },
        },
    )


def apply_upgrade(plan: UpgradePlan, approved_digest: str) -> dict[str, object]:
    if plan.digest is None or plan.local_plan is None or plan.target is None:
        raise SvcError(
            "upgrade-plan-not-applicable",
            "The selected upgrade plan cannot be applied.",
            {
                "repo": str(plan.repo),
                "target": plan.target,
                "status": plan.status,
                "repository_effect": "none",
            },
        )
    if approved_digest != plan.digest:
        raise SvcError(
            "plan-digest-mismatch",
            "The supplied digest does not select the current upgrade plan.",
            {
                "repo": str(plan.repo),
                "target": plan.target,
                "received": approved_digest,
                "repository_effect": "none",
            },
        )
    try:
        result = apply_local_plan(plan.local_plan, plan.local_plan.digest)
    except SvcError as error:
        error.details = {
            "repo": str(plan.repo),
            "target": plan.target,
            "plan_digest": approved_digest,
            **error.details,
        }
        raise

    disposition = (
        "caller-asserted" if plan.status == "migration-required" else "not-required"
    )
    guidance: list[dict[str, object]]
    if plan.target == "config":
        guidance = [guide.reference() for guide in plan.config_guides]
        verification_scope = "effective-schema-3-configuration"
    else:
        corpus_details = plan.details["corpus"]
        assert isinstance(corpus_details, dict)
        guidance = [
            guide
            for release in corpus_details["releases"]
            if isinstance(release, dict)
            for guide in release.get("guides", [])
            if isinstance(guide, dict)
        ]
        verification_scope = "project-corpus-baseline"
    return {
        "schema_version": UPGRADE_SCHEMA_VERSION,
        "command": "upgrade",
        "mode": "apply",
        "status": "applied",
        "repo": str(plan.repo),
        "target": plan.target,
        "plan_digest": approved_digest,
        "changed": result["changed"],
        "operations": plan.operations(),
        **plan.details,
        "migration": {
            "disposition": disposition,
            "guidance": guidance,
        },
        "verification": {"scope": verification_scope, "status": "passed"},
        "remaining_targets": list(plan.remaining_targets),
    }


def _plan_config(root: Path, available: Catalog) -> UpgradePlan:
    content, read_blocker = _read_regular(root, PROJECT_FILE)
    if read_blocker is not None:
        return _blocked(root, "config", read_blocker, available)
    if content is None:
        return _blocked(
            root,
            "config",
            Blocker(
                "project-not-initialized",
                PROJECT_FILE,
                "Project SVC integration is absent; run svc init first.",
            ),
            available,
        )
    try:
        state = parse_project_state(content)
    except ValueError as error:
        return _blocked(
            root,
            "config",
            Blocker("invalid-project-configuration", PROJECT_FILE, str(error)),
            available,
        )

    if isinstance(state, ProjectConfig):
        try:
            load_config(root)
        except ConfigError as error:
            return _blocked(
                root,
                "config",
                Blocker("invalid-project-configuration", PROJECT_FILE, str(error)),
                available,
                corpus_version=state.corpus_version,
            )
        return UpgradePlan(
            root,
            "config",
            "noop",
            (),
            (),
            {"configuration": {"schema": CONFIG_SCHEMA_VERSION, "status": "current"}},
            tuple(_corpus_remaining(state.corpus_version, available)),
        )
    if not isinstance(state, LegacyProjectConfig):
        return _blocked(
            root,
            "config",
            Blocker(
                "unsupported-config-schema",
                PROJECT_FILE,
                f"No automatic migration is available from schema {state.schema_version}.",
            ),
            available,
            corpus_version=state.corpus_version,
        )

    local_content, local_blocker = _read_regular(root, LOCAL_CONFIG_FILE)
    if local_blocker is not None:
        return _blocked(
            root,
            "config",
            local_blocker,
            available,
            corpus_version=state.svc_version,
        )
    try:
        descriptor = _config_descriptor(2, CONFIG_SCHEMA_VERSION)
        migration = migrate_v2_to_v3(content, local_content)
    except ConfigMigrationError as error:
        return _blocked(
            root,
            "config",
            Blocker(error.code, PROJECT_FILE, error.message),
            available,
            corpus_version=state.svc_version,
        )
    except ConfigError as error:
        return _blocked(
            root,
            "config",
            Blocker("invalid-project-configuration", PROJECT_FILE, str(error)),
            available,
            corpus_version=state.svc_version,
        )

    mutations = [
        make_write(
            root,
            PROJECT_FILE,
            "rewrite",
            "migrate configuration schema 2 -> 3",
            migration.base.content,
        )
    ]
    if migration.local is not None:
        mutations.append(
            make_write(
                root,
                LOCAL_CONFIG_FILE,
                "rewrite",
                "migrate local overlay to schema 3",
                migration.local.content,
            )
        )
    guides = (descriptor,)
    details: dict[str, object] = {
        "configuration": {
            "from_schema": 2,
            "to_schema": CONFIG_SCHEMA_VERSION,
            "guidance": [guide.reference() for guide in guides],
        }
    }
    automatic = ["svc_version -> corpus_version (value unchanged)"]
    if migration.source_profile is not None:
        automatic.extend(
            (
                f"dev.profiles.{migration.source_profile}.targets -> dev.targets",
                "remove dev.profile and the legacy profiles container",
            )
        )
    if migration.local is not None:
        automatic.append("migrate the present local overlay to schema 3")
    status = "migration-required" if guides else "ready"
    local_plan = LocalPlan(
        "upgrade-config",
        root,
        f"schema-{CONFIG_SCHEMA_VERSION}",
        tuple(mutations),
    )
    return UpgradePlan(
        root,
        "config",
        status,
        tuple(mutations),
        (),
        details,
        tuple(_corpus_remaining(state.svc_version, available)),
        tuple(automatic),
        guides,
        local_plan,
    )


def _plan_corpus(root: Path, available: Catalog) -> UpgradePlan:
    content, read_blocker = _read_regular(root, PROJECT_FILE)
    if read_blocker is not None:
        return _blocked(root, "corpus", read_blocker, available)
    if content is None:
        return _blocked(
            root,
            "corpus",
            Blocker(
                "project-not-initialized",
                PROJECT_FILE,
                "Project SVC integration is absent; run svc init first.",
            ),
            available,
        )
    try:
        state = parse_project_state(content)
    except ValueError as error:
        return _blocked(
            root,
            "corpus",
            Blocker("invalid-project-configuration", PROJECT_FILE, str(error)),
            available,
        )
    if not isinstance(state, (LegacyProjectConfig, ProjectConfig)):
        return _blocked(
            root,
            "corpus",
            Blocker(
                "unsupported-config-schema",
                PROJECT_FILE,
                f"Corpus baseline updates do not support schema {state.schema_version}.",
            ),
            available,
            corpus_version=state.corpus_version,
        )

    baseline = (
        state.svc_version
        if isinstance(state, LegacyProjectConfig)
        else state.corpus_version
    )
    selected, blocker = _select_corpus_releases(baseline, available)
    if blocker is not None:
        return _blocked(
            root,
            "corpus",
            blocker,
            available,
            corpus_version=baseline,
            config_schema=state.schema_version,
        )
    remaining = tuple(_config_remaining(state.schema_version))
    if not selected:
        return UpgradePlan(
            root,
            "corpus",
            "noop",
            (),
            (),
            {
                "corpus": {
                    "project_version": baseline,
                    "available_version": available.corpus_version,
                    "status": "current",
                    "releases": [],
                }
            },
            remaining,
        )

    entry_hashes = {entry.path: entry.sha256 for entry in available.entries}
    releases: list[dict[str, object]] = []
    guided = False
    for release in selected:
        item: dict[str, object] = {
            "version": release.version,
            "migration": release.migration.status,
        }
        if release.migration.status == "guide":
            guided = True
            guides = []
            for path in release.migration.paths:
                content_hash = sha256_bytes(read_document(path))
                if entry_hashes.get(path) != content_hash:
                    raise SvcError(
                        "invalid-corpus",
                        "Corpus guide content does not match the catalog.",
                        {"path": path},
                    )
                guides.append({"path": path, "sha256": content_hash})
            item["guides"] = guides
        releases.append(item)
    details: dict[str, object] = {
        "corpus": {
            "from_version": baseline,
            "to_version": available.corpus_version,
            "releases": releases,
        }
    }
    field = (
        "svc_version" if isinstance(state, LegacyProjectConfig) else "corpus_version"
    )
    updated = replace_corpus_baseline(content, available.corpus_version, field)
    mutation = make_write(
        root,
        PROJECT_FILE,
        "rewrite",
        f"record Corpus baseline {available.corpus_version}",
        updated,
    )
    local_plan = LocalPlan(
        "upgrade-corpus",
        root,
        available.corpus_version,
        (mutation,),
    )
    return UpgradePlan(
        root,
        "corpus",
        "migration-required" if guided else "ready",
        (mutation,),
        (),
        details,
        remaining,
        local_plan=local_plan,
    )


def _blocked(
    root: Path,
    target: UpgradeTarget,
    blocker: Blocker,
    available: Catalog,
    *,
    corpus_version: str | None = None,
    config_schema: int | None = None,
) -> UpgradePlan:
    remaining: list[dict[str, object]] = []
    if target == "config" and corpus_version is not None:
        remaining.extend(_corpus_remaining(corpus_version, available))
    if target == "corpus" and config_schema is not None:
        remaining.extend(_config_remaining(config_schema))
    return UpgradePlan(root, target, "blocked", (), (blocker,), {}, tuple(remaining))


def _read_regular(root: Path, relative: str) -> tuple[bytes | None, Blocker | None]:
    path = root / relative
    if not path.exists() and not path.is_symlink():
        return None, None
    if path.is_symlink() or not path.is_file():
        return None, Blocker(
            "path-not-file", relative, "Upgrade target must be a regular file."
        )
    try:
        return path.read_bytes(), None
    except OSError as error:
        return None, Blocker("path-unreadable", relative, str(error))


def _config_descriptor(from_schema: int, to_schema: int) -> ConfigGuide:
    content = read_config_migration_descriptor(from_schema, to_schema)
    try:
        raw = parse_json_document(content, "config migration descriptor")
    except ConfigError as error:
        raise SvcError("invalid-release", str(error)) from error
    required = {
        "schema_version",
        "from_schema",
        "to_schema",
        "transform",
        "change_ids",
        "guidance",
        "guidance_sha256",
    }
    if set(raw) != required or raw.get("schema_version") != 1:
        raise SvcError(
            "invalid-release", "Config migration descriptor has an unsupported shape."
        )
    if raw.get("from_schema") != from_schema or raw.get("to_schema") != to_schema:
        raise SvcError(
            "invalid-release",
            "Config migration descriptor names the wrong schema step.",
        )
    identifier = raw.get("transform")
    guidance = raw.get("guidance")
    expected_hash = raw.get("guidance_sha256")
    if (
        not isinstance(identifier, str)
        or not isinstance(guidance, list)
        or not guidance
    ):
        raise SvcError(
            "invalid-release", "Config migration descriptor has no guidance."
        )
    if sha256_bytes(canonical_json(guidance)) != expected_hash:
        raise SvcError(
            "invalid-release", "Config migration guidance digest is invalid."
        )
    texts: list[str] = []
    for item in guidance:
        if not isinstance(item, dict) or set(item) != {"change_id", "body", "guidance"}:
            raise SvcError(
                "invalid-release", "Config migration guidance entry is invalid."
            )
        text = item.get("guidance")
        if not isinstance(text, str) or not text.strip():
            raise SvcError(
                "invalid-release", "Config migration guidance text is empty."
            )
        texts.append(text.strip())
    if not isinstance(expected_hash, str):
        raise SvcError(
            "invalid-release", "Config migration guidance digest is invalid."
        )
    return ConfigGuide(identifier, expected_hash, "\n\n".join(texts))


def _select_corpus_releases(
    baseline: str, available: Catalog
) -> tuple[tuple[Any, ...], Blocker | None]:
    chain = available.version_index
    versions = [
        chain.supported_anchor,
        *(release.version for release in chain.releases),
    ]
    if baseline not in versions:
        return (), Blocker(
            "unsupported-corpus-baseline",
            PROJECT_FILE,
            f"Corpus baseline {baseline} is not on the retained release chain.",
        )
    start = versions.index(baseline)
    return chain.releases[start:], None


def _corpus_remaining(baseline: str, available: Catalog) -> list[dict[str, object]]:
    selected, blocker = _select_corpus_releases(baseline, available)
    if blocker is not None:
        return [
            {
                "target": "corpus",
                "status": "blocked",
                "from_version": baseline,
                "to_version": available.corpus_version,
                "code": blocker.code,
            }
        ]
    if not selected:
        return []
    return [
        {
            "target": "corpus",
            "status": "pending",
            "from_version": baseline,
            "to_version": available.corpus_version,
        }
    ]


def _config_remaining(schema: int) -> list[dict[str, object]]:
    if schema == CONFIG_SCHEMA_VERSION:
        return []
    return [
        {
            "target": "config",
            "status": "pending" if schema == 2 else "blocked",
            "from_schema": schema,
            "to_schema": CONFIG_SCHEMA_VERSION,
        }
    ]
