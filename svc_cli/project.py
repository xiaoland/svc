"""Project-local SVC adoption state and bounded integration planning."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from semantic_version import Version  # type: ignore[import-untyped]

from .catalog import canonical_json, require_semver, sha256_bytes
from .config import (
    CONFIG_SCHEMA_VERSION,
    LOCAL_CONFIG_FILE,
    ConfigError,
    LegacyProjectConfig,
    ProjectConfig,
    ResolvedConfig,
    load_config,
    parse_legacy_project_config,
    parse_project_config,
)
from .errors import SvcError
from .integration import (
    DesiredIntegration,
    IntegrationInspection,
    IntegrationProblem,
    desired_local_config_ignore,
    desired_navigation,
    inspect_local_config_ignore,
    inspect_navigation,
    inspect_retired_skill,
)
from .plans import (
    Blocker,
    LocalPlan,
    PlannedFileMutation,
    apply_local_plan,
    make_delete,
    make_write,
)
from .release import catalog, installed_distribution_version
from .resources import resource_mode
from .workspace import resolve_workspace_identity


PROJECT_SCHEMA_VERSION = CONFIG_SCHEMA_VERSION
PROJECT_FILE = "svc.json"
CODEX_SKILL_FILE = ".agents/skills/svc/SKILL.md"
AGENTS_FILE = "AGENTS.md"
DOCS_INDEX_FILE = "docs/index.md"


@dataclass(frozen=True)
class InitPlan:
    local_plan: LocalPlan
    intent: str
    corpus_baseline: dict[str, object]

    @property
    def repo(self) -> Path:
        return self.local_plan.repo

    @property
    def corpus_version(self) -> str:
        return self.local_plan.target_version

    @property
    def target_version(self) -> str:
        return self.corpus_version

    @property
    def mutations(self) -> tuple[PlannedFileMutation, ...]:
        return self.local_plan.mutations

    @property
    def blockers(self) -> tuple[Blocker, ...]:
        return self.local_plan.blockers

    @property
    def status(self) -> str:
        return self.local_plan.status

    @property
    def digest(self) -> str | None:
        if self.blockers:
            return None
        return sha256_bytes(canonical_json(self.signature()))

    def signature(self) -> dict[str, object]:
        return {
            "schema_version": 2,
            "command": "init",
            "repo": str(self.repo),
            "intent": self.intent,
            "corpus_version": self.corpus_version,
            "corpus_baseline": self.corpus_baseline,
            "operations": [
                _init_operation(mutation, signature=True) for mutation in self.mutations
            ],
            "blockers": [
                {"code": blocker.code, "path": blocker.path}
                for blocker in self.blockers
            ],
        }

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "schema_version": 2,
            "command": "init",
            "mode": "plan",
            "status": self.status,
            "repo": str(self.repo),
            "intent": self.intent,
            "corpus_version": self.corpus_version,
            "corpus_baseline": self.corpus_baseline,
            "operations": []
            if self.blockers
            else [_init_operation(mutation) for mutation in self.mutations],
            "blockers": [blocker.as_dict() for blocker in self.blockers],
        }
        if self.digest is not None:
            result["plan_digest"] = self.digest
        return result


def render_project_state(corpus_version: str) -> bytes:
    require_semver(corpus_version, "project corpus_version")
    return (
        json.dumps(
            {
                "schema_version": PROJECT_SCHEMA_VERSION,
                "corpus_version": corpus_version,
            },
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def parse_project_state(
    content: bytes,
) -> LegacyProjectConfig | ProjectConfig:
    try:
        raw = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("svc.json must be valid UTF-8 JSON") from error
    if not isinstance(raw, dict):
        raise ValueError("svc.json must contain a JSON object")
    schema = raw.get("schema_version")
    if schema == 2:
        try:
            return parse_legacy_project_config(content)
        except ConfigError as error:
            raise ValueError(str(error)) from error
    if schema != PROJECT_SCHEMA_VERSION:
        raise ValueError(f"Unsupported svc.json schema: {schema!r}")
    try:
        return parse_project_config(content)
    except ConfigError as error:
        raise ValueError(str(error)) from error


def plan_init(repo: Path) -> InitPlan:
    root = _require_repo(repo)
    target_version = catalog().corpus_version
    blockers: list[Blocker] = []
    writes = []
    state_content = _read_project_content(root, blockers)
    intent = "establish" if state_content is None else "repair"
    baseline: dict[str, object] = {
        "disposition": "create" if state_content is None else "unchanged",
        "version": target_version if state_content is None else None,
    }
    if state_content is None and not any(
        blocker.path == PROJECT_FILE for blocker in blockers
    ):
        try:
            orphan_local = _read_optional(root, LOCAL_CONFIG_FILE)
        except SvcError as error:
            blockers.append(Blocker(error.code, LOCAL_CONFIG_FILE, error.message))
        else:
            if orphan_local is not None:
                blockers.append(
                    Blocker(
                        "orphan-local-configuration",
                        LOCAL_CONFIG_FILE,
                        f"{LOCAL_CONFIG_FILE} exists while {PROJECT_FILE} is absent.",
                    )
                )
            else:
                writes.append(
                    make_write(
                        root,
                        PROJECT_FILE,
                        "create",
                        "record initial Corpus baseline",
                        render_project_state(target_version),
                    )
                )
    elif state_content is not None:
        try:
            state = parse_project_state(state_content)
        except ValueError as error:
            blockers.append(Blocker("invalid-project-state", PROJECT_FILE, str(error)))
        else:
            _block_noncurrent_schema(state, blockers)
            baseline["version"] = _state_corpus_version(state)
            if not blockers:
                try:
                    load_config(root)
                except ConfigError as error:
                    blockers.append(
                        Blocker(
                            "invalid-project-configuration", PROJECT_FILE, str(error)
                        )
                    )
                if Version(_state_corpus_version(state)) > Version(target_version):
                    blockers.append(
                        Blocker(
                            "corpus-baseline-ahead",
                            PROJECT_FILE,
                            "The project Corpus baseline is newer than the installed Corpus; init will not project older integration.",
                        )
                    )

    writes.extend(
        _plan_surface(root, ".gitignore", desired_local_config_ignore, blockers)
    )

    writes.extend(_plan_retired_skill(root, blockers))
    writes.extend(
        _plan_surface(
            root,
            AGENTS_FILE,
            lambda content: desired_navigation(AGENTS_FILE, content),
            blockers,
        )
    )
    writes.extend(
        _plan_surface(
            root,
            DOCS_INDEX_FILE,
            lambda content: desired_navigation(DOCS_INDEX_FILE, content),
            blockers,
        )
    )
    return InitPlan(
        LocalPlan("init", root, target_version, tuple(writes), tuple(blockers)),
        intent,
        baseline,
    )


def apply_init(plan: InitPlan, approved_digest: str) -> dict[str, object]:
    if plan.digest is None:
        raise SvcError(
            "plan-blocked",
            "The init plan has unresolved blockers.",
            {
                "command": "init",
                "repo": str(plan.repo),
                "repository_effect": "none",
                "blockers": [blocker.as_dict() for blocker in plan.blockers],
            },
        )
    if approved_digest != plan.digest:
        raise SvcError(
            "plan-digest-mismatch",
            "The supplied digest no longer selects the current init plan.",
            {
                "command": "init",
                "repo": str(plan.repo),
                "selected_digest": approved_digest,
                "repository_effect": "none",
            },
        )
    try:
        result = apply_local_plan(plan.local_plan, plan.local_plan.digest)
    except SvcError as error:
        error.details = {
            "command": "init",
            "repo": str(plan.repo),
            "selected_digest": approved_digest,
            **error.details,
        }
        raise
    return {
        "schema_version": 2,
        "command": "init",
        "mode": "apply",
        "status": result["status"],
        "repo": str(plan.repo),
        "intent": plan.intent,
        "corpus_version": plan.corpus_version,
        "corpus_baseline": plan.corpus_baseline,
        "plan_digest": approved_digest,
        "operations": [_init_operation(mutation) for mutation in plan.mutations],
        "verification": {
            "scope": "planned-path-postconditions",
            "status": "passed",
        },
    }


def inspect_status(repo: Path) -> dict[str, object]:
    """Inspect one repository without probing or changing a dev capability."""

    root = _require_repo(repo)
    corpus = catalog()
    installed_cli_version = installed_distribution_version()
    runtime_status = "source-tree" if installed_cli_version is None else "installed"
    project = _inspect_project(root, corpus.corpus_version)
    configuration, resolved = _inspect_configuration(root, project)
    dev = _inspect_dev_declaration(resolved)
    run = _inspect_run_declaration(resolved)
    guidance = [
        _inspect_guidance(
            root,
            AGENTS_FILE,
            "agent-router",
            lambda content: inspect_navigation(content, AGENTS_FILE),
        ),
        _inspect_guidance(
            root,
            DOCS_INDEX_FILE,
            "docs-navigation",
            lambda content: inspect_navigation(content, DOCS_INDEX_FILE),
        ),
    ]
    retired_skill = _inspect_guidance(
        root,
        CODEX_SKILL_FILE,
        "legacy-cli-skill",
        inspect_retired_skill,
    )
    managed_ignore = _inspect_guidance(
        root, ".gitignore", "local-config-ignore", inspect_local_config_ignore
    )
    healthy = (
        project["status"] == "current"
        and configuration["status"] == "current"
        and managed_ignore["status"] == "current"
        and all(item["status"] == "current" for item in guidance)
        and retired_skill["status"] in {"missing", "unowned"}
    )
    status, next_action = _status_decision(
        root,
        project,
        configuration,
        guidance,
        managed_ignore,
        retired_skill,
    )
    corpus_status = _corpus_status(project, corpus.corpus_version)
    integration_status = _integration_status(guidance, managed_ignore, retired_skill)
    return {
        "schema_version": 2,
        "status": status,
        "next": next_action,
        "installed_cli_version": installed_cli_version,
        "available_corpus_version": corpus.corpus_version,
        "resource_mode": resource_mode(),
        "runtime": {"status": runtime_status},
        "workspace": resolve_workspace_identity(root).as_dict(),
        "project": project,
        "corpus": corpus_status,
        "configuration": configuration,
        "dev": dev,
        "run": run,
        "managed_ignore": managed_ignore,
        "guidance": guidance,
        "retired_skill": retired_skill,
        "integration": integration_status,
        "healthy": healthy,
    }


def _require_repo(repo: Path) -> Path:
    root = repo.resolve()
    if not root.is_dir():
        raise SvcError(
            "repo-not-directory",
            "Project root is not a directory.",
            {"repo": str(repo)},
        )
    return root


def _path(root: Path, relative: str) -> Path:
    return root.joinpath(*relative.split("/"))


def _read_optional(root: Path, relative: str) -> bytes | None:
    path = _path(root, relative)
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise SvcError(
            "path-not-file",
            "Integration target must be a regular file.",
            {"path": relative},
        )
    return path.read_bytes()


def _read_project_content(root: Path, blockers: list[Blocker]) -> bytes | None:
    try:
        return _read_optional(root, PROJECT_FILE)
    except SvcError as error:
        blockers.append(Blocker(error.code, PROJECT_FILE, error.message))
        return None


def _plan_surface(
    root: Path,
    relative: str,
    desired: Callable[[bytes | None], DesiredIntegration | None],
    blockers: list[Blocker],
) -> list[PlannedFileMutation]:
    try:
        current = _read_optional(root, relative)
        proposal = desired(current)
    except IntegrationProblem as error:
        blockers.append(Blocker(error.code, relative, error.message))
        return []
    except SvcError as error:
        blockers.append(Blocker(error.code, relative, error.message))
        return []
    if proposal is None:
        return []
    return [
        make_write(root, relative, proposal.action, proposal.reason, proposal.content)
    ]


def _plan_retired_skill(
    root: Path, blockers: list[Blocker]
) -> list[PlannedFileMutation]:
    try:
        current = _read_optional(root, CODEX_SKILL_FILE)
        inspection = inspect_retired_skill(current)
    except (IntegrationProblem, SvcError) as error:
        blockers.append(Blocker(error.code, CODEX_SKILL_FILE, str(error)))
        return []
    if inspection.status == "clean-generated":
        return [
            make_delete(
                root,
                CODEX_SKILL_FILE,
                "delete",
                "retire clean generated SVC CLI Skill",
            )
        ]
    if inspection.status == "modified":
        blockers.append(
            Blocker(
                "generated-skill-drift",
                CODEX_SKILL_FILE,
                "The recognizable SVC-generated Skill was modified and will not be deleted.",
            )
        )
    return []


def _init_operation(
    mutation: PlannedFileMutation, *, signature: bool = False
) -> dict[str, object]:
    surfaces = {
        PROJECT_FILE: ("project-state", "whole-file"),
        ".gitignore": ("local-config-ignore", "svc-managed-block"),
        AGENTS_FILE: ("agent-router", "svc-managed-block"),
        DOCS_INDEX_FILE: ("docs-navigation", "svc-managed-block"),
        CODEX_SKILL_FILE: ("legacy-cli-skill", "whole-file"),
    }
    surface, extent = surfaces[mutation.path]
    result: dict[str, object] = {
        "action": mutation.action,
        "path": mutation.path,
        "surface": surface,
        "extent": extent,
        "before": mutation.before.as_dict(),
        "after": mutation.after.as_dict(),
    }
    if signature:
        result["parent_preconditions"] = [
            list(item) for item in mutation.parent_preconditions
        ]
    return result


def _inspect_project(root: Path, available_version: str) -> dict[str, object]:
    try:
        content = _read_optional(root, PROJECT_FILE)
    except SvcError as error:
        return {"path": PROJECT_FILE, "status": "invalid", "message": error.message}
    if content is None:
        return {
            "path": PROJECT_FILE,
            "status": "missing",
            "corpus_version": None,
        }
    try:
        state = parse_project_state(content)
    except ValueError as error:
        return {"path": PROJECT_FILE, "status": "invalid", "message": str(error)}
    if state.schema_version != PROJECT_SCHEMA_VERSION:
        return {
            "path": PROJECT_FILE,
            "status": "schema-write-blocked",
            "schema_version": state.schema_version,
            "corpus_version": _state_corpus_version(state),
        }
    return {
        "path": PROJECT_FILE,
        "status": "current"
        if _state_corpus_version(state) == available_version
        else (
            "corpus-behind"
            if Version(_state_corpus_version(state)) < Version(available_version)
            else "corpus-ahead"
        ),
        "schema_version": state.schema_version,
        "corpus_version": _state_corpus_version(state),
    }


def _inspect_configuration(
    root: Path,
    project: dict[str, object],
) -> tuple[dict[str, object], ResolvedConfig | None]:
    project_status = str(project["status"])
    if project_status == "missing":
        try:
            local = _read_optional(root, LOCAL_CONFIG_FILE)
        except SvcError as error:
            return {"status": "invalid", "message": error.message}, None
        if local is None:
            return {"status": "not-configured"}, None
        return {
            "status": "invalid",
            "message": f"{LOCAL_CONFIG_FILE} exists while {PROJECT_FILE} is absent.",
        }, None
    if project_status not in {"current", "corpus-behind", "corpus-ahead"}:
        return {
            "status": "not-inspected",
            "reason": "project-state-not-current-schema",
        }, None
    try:
        resolved = load_config(root)
    except ConfigError as error:
        return {"status": "invalid", "message": str(error)}, None
    return (
        {
            "status": "current",
            "base": {
                "path": PROJECT_FILE,
                "status": "valid",
                "digest": resolved.base_digest,
            },
            "local": {
                "path": LOCAL_CONFIG_FILE,
                "status": "absent" if resolved.local is None else "valid",
                "digest": resolved.local_digest,
            },
            "effective": {"status": "valid", "digest": resolved.effective_digest},
        },
        resolved,
    )


def _inspect_dev_declaration(resolved: ResolvedConfig | None) -> dict[str, object]:
    result: dict[str, object] = {
        "observation": "declaration-only",
        "targets": [],
    }
    if resolved is None:
        return {"status": "unavailable", **result}
    dev = resolved.effective.dev
    if dev is None:
        return {"status": "not-declared", **result}
    return {
        "status": "declared",
        "observation": "declaration-only",
        "targets": sorted(dev.targets),
    }


def _inspect_run_declaration(resolved: ResolvedConfig | None) -> dict[str, object]:
    result: dict[str, object] = {"observation": "declaration-only", "entries": []}
    if resolved is None:
        return {"status": "unavailable", **result}
    entries = sorted(resolved.base.run)
    return {
        "status": "declared" if entries else "not-declared",
        "observation": "declaration-only",
        "entries": entries,
    }


def _status_decision(
    root: Path,
    project: dict[str, object],
    configuration: dict[str, object],
    guidance: list[dict[str, str]],
    managed_ignore: dict[str, str],
    retired_skill: dict[str, str],
) -> tuple[str, dict[str, object]]:
    project_status = str(project["status"])
    configuration_status = str(configuration["status"])
    if project_status == "missing":
        if configuration_status == "not-configured":
            return "unadopted", _next_action(
                "plan-integration-establishment",
                "Project SVC integration is absent; inspect the non-mutating init plan.",
                command=["svc", "init", str(root)],
            )
        return "malformed", _next_action(
            "repair-project-configuration",
            "SVC will not overwrite an orphaned or invalid local configuration.",
        )
    if project_status == "invalid" or configuration_status == "invalid":
        return "malformed", _next_action(
            "repair-project-configuration",
            "Project configuration is invalid; repair the Consumer-owned file before continuing.",
        )
    if project_status == "schema-write-blocked":
        if project.get("schema_version") == 2:
            return "actionable", _next_action(
                "plan-project-upgrade",
                "Project configuration schema has a supported exact migration.",
                command=["svc", "upgrade", str(root), "--target", "config"],
            )
        return "actionable", _next_action(
            "migrate-project-configuration",
            "Project configuration schema is outside the automatic migration range.",
        )
    integration = _integration_status(guidance, managed_ignore, retired_skill)
    if integration["status"] != "current":
        return "actionable", _next_action(
            "plan-integration-repair",
            "Managed SVC integration needs review; inspect the non-mutating init plan.",
            command=["svc", "init", str(root)],
        )
    if project_status == "corpus-behind":
        return "actionable", _next_action(
            "plan-project-upgrade",
            "The project Corpus baseline is behind the installed Corpus.",
            command=["svc", "upgrade", str(root), "--target", "corpus"],
        )
    if project_status == "corpus-ahead":
        return "actionable", _next_action(
            "install-compatible-corpus",
            "The project Corpus baseline is newer than the installed Corpus; use the package manager to install a compatible CLI distribution.",
        )
    return "healthy", _next_action(
        "continue",
        "Configuration, Corpus baseline, and managed integration are current.",
    )


def _next_action(
    action: str,
    reason: str,
    *,
    command: list[str] | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "action": action,
        "reason": reason,
    }
    if command is not None:
        result["command"] = command
    return result


def _corpus_status(
    project: dict[str, object], available_version: str
) -> dict[str, object]:
    project_status = str(project["status"])
    version = project.get("corpus_version")
    relation = {
        "missing": "absent",
        "corpus-behind": "behind",
        "current": "current",
        "corpus-ahead": "ahead",
    }.get(project_status, "unavailable")
    return {
        "status": relation,
        "project_version": version,
        "available_version": available_version,
    }


def _integration_status(
    guidance: list[dict[str, str]],
    managed_ignore: dict[str, str],
    retired_skill: dict[str, str],
) -> dict[str, object]:
    surfaces = [managed_ignore, *guidance, retired_skill]
    blocked = [item for item in surfaces if item["status"] == "modified"]
    repairable = [
        item
        for item in surfaces
        if item["status"] in {"missing", "unanchored", "outdated", "clean-generated"}
        and not (item["kind"] == "legacy-cli-skill" and item["status"] == "missing")
    ]
    if blocked:
        status = "blocked"
        anomalies = blocked + repairable
    elif repairable:
        status = "repairable"
        anomalies = repairable
    else:
        status = "current"
        anomalies = []
    return {
        "status": status,
        "anomalies": [
            {"path": item["path"], "kind": item["kind"], "status": item["status"]}
            for item in anomalies
        ],
    }


def _block_noncurrent_schema(
    state: LegacyProjectConfig | ProjectConfig,
    blockers: list[Blocker],
) -> None:
    if state.schema_version == PROJECT_SCHEMA_VERSION:
        return
    blockers.append(
        Blocker(
            "schema-write-blocked",
            PROJECT_FILE,
            f"Unsupported svc.json schema: {state.schema_version}.",
        )
    )


def _state_corpus_version(
    state: LegacyProjectConfig | ProjectConfig,
) -> str:
    if isinstance(state, ProjectConfig):
        return state.corpus_version
    if isinstance(state, LegacyProjectConfig):
        return state.svc_version
    raise AssertionError("unreachable project configuration type")


def replace_corpus_baseline(content: bytes, version: str, field: str) -> bytes:
    """Replace only one recognized root Corpus baseline JSON value."""

    require_semver(version, "project corpus_version")
    text = content.decode("utf-8")
    decoder = json.JSONDecoder()
    index = _skip_json_space(text, 0)
    if index >= len(text) or text[index] != "{":
        raise ValueError("svc.json must contain a JSON object")
    index += 1
    found: tuple[int, int] | None = None
    while True:
        index = _skip_json_space(text, index)
        if index < len(text) and text[index] == "}":
            break
        key, index = decoder.raw_decode(text, index)
        if not isinstance(key, str):
            raise ValueError("svc.json object keys must be strings")
        index = _skip_json_space(text, index)
        if index >= len(text) or text[index] != ":":
            raise ValueError("svc.json object entry is malformed")
        index = _skip_json_space(text, index + 1)
        value_start = index
        _, value_end = decoder.raw_decode(text, index)
        if key == field:
            if found is not None:
                raise ValueError(f"svc.json contains duplicate {field} entries")
            found = (value_start, value_end)
        index = _skip_json_space(text, value_end)
        if index < len(text) and text[index] == ",":
            index += 1
            continue
        if index < len(text) and text[index] == "}":
            break
        raise ValueError("svc.json object entry is malformed")
    if found is None:
        raise ValueError(f"svc.json has no {field} entry")
    start, end = found
    return (text[:start] + json.dumps(version) + text[end:]).encode("utf-8")


def _skip_json_space(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t\r\n":
        index += 1
    return index


def _inspect_guidance(
    root: Path,
    relative: str,
    kind: str,
    inspect: Callable[[bytes | None], IntegrationInspection],
) -> dict[str, str]:
    try:
        content = _read_optional(root, relative)
        inspection = inspect(content)
    except (IntegrationProblem, SvcError) as error:
        return {
            "path": relative,
            "kind": kind,
            "status": "modified",
            "message": str(error),
        }
    return {"path": relative, "kind": kind, "status": inspection.status}
