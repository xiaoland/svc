"""Project-local SVC adoption state and bounded integration planning."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .catalog import require_semver
from .config import CONFIG_SCHEMA_VERSION, ConfigError, LOCAL_CONFIG_FILE, ProjectConfig, load_config, parse_project_config
from .errors import SvcError
from .integration import (
    DesiredIntegration,
    IntegrationProblem,
    desired_local_config_ignore,
    desired_navigation,
    desired_skill,
    inspect_local_config_ignore,
    inspect_navigation,
    inspect_skill,
)
from .plans import Blocker, LocalPlan, PlannedWrite, make_write
from .release import catalog, installed_distribution_version
from .resources import resource_mode


PROJECT_SCHEMA_VERSION = CONFIG_SCHEMA_VERSION
PROJECT_FILE = "svc.json"
CODEX_SKILL_FILE = ".agents/skills/svc/SKILL.md"
AGENTS_FILE = "AGENTS.md"
DOCS_INDEX_FILE = "docs/index.md"


@dataclass(frozen=True)
class ProjectState:
    schema_version: int
    svc_version: str

    def as_dict(self) -> dict[str, object]:
        return {"schema_version": self.schema_version, "svc_version": self.svc_version}


def render_project_state(svc_version: str) -> bytes:
    require_semver(svc_version, "project svc_version")
    return (json.dumps({"schema_version": PROJECT_SCHEMA_VERSION, "svc_version": svc_version}, indent=2) + "\n").encode("utf-8")


def parse_project_state(content: bytes) -> ProjectState | ProjectConfig:
    try:
        raw = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("svc.json must be valid UTF-8 JSON") from error
    if not isinstance(raw, dict):
        raise ValueError("svc.json must contain a JSON object")
    schema = raw.get("schema_version")
    if schema == 1:
        if set(raw) != {"schema_version", "svc_version"}:
            raise ValueError("schema-v1 svc.json must contain only schema_version and svc_version")
        return ProjectState(1, require_semver(raw.get("svc_version"), "svc.json svc_version"))
    if schema != PROJECT_SCHEMA_VERSION:
        raise ValueError(f"Unsupported svc.json schema: {schema!r}")
    try:
        return parse_project_config(content)
    except ConfigError as error:
        raise ValueError(str(error)) from error


def plan_init(repo: Path, agent: str = "codex") -> LocalPlan:
    root = _require_repo(repo)
    target_version = catalog().svc_version
    blockers: list[Blocker] = []
    writes = []
    if agent != "codex":
        blockers.append(Blocker("unsupported-agent", "--agent", "Only the Codex skill provider is currently supported."))

    state_content = _read_project_content(root, blockers)
    if state_content is None and not any(blocker.path == PROJECT_FILE for blocker in blockers):
        writes.append(make_write(root, PROJECT_FILE, "create", "record initial SVC adoption", render_project_state(target_version)))
    elif state_content is not None:
        try:
            state = parse_project_state(state_content)
        except ValueError as error:
            blockers.append(Blocker("invalid-project-state", PROJECT_FILE, str(error)))
        else:
            _block_noncurrent_schema(state, blockers)
            if not blockers:
                try:
                    load_config(root)
                except ConfigError as error:
                    blockers.append(Blocker("invalid-project-configuration", PROJECT_FILE, str(error)))

    writes.extend(_plan_surface(root, ".gitignore", desired_local_config_ignore, blockers))

    writes.extend(
        _plan_surface(
            root,
            CODEX_SKILL_FILE,
            desired_skill,
            blockers,
        )
    )
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
    return LocalPlan("init", root, target_version, tuple(writes), tuple(blockers))


def plan_adopt(repo: Path, requested_version: str | None = None) -> LocalPlan:
    root = _require_repo(repo)
    available_version = catalog().svc_version
    target_version = requested_version or available_version
    blockers: list[Blocker] = []
    writes = []
    try:
        require_semver(target_version, "requested SVC version")
    except ValueError as error:
        blockers.append(Blocker("invalid-adoption-version", PROJECT_FILE, str(error)))
    else:
        if target_version != available_version:
            blockers.append(
                Blocker(
                    "corpus-version-unavailable",
                    PROJECT_FILE,
                    f"This installed CLI contains SVC {available_version}, not {target_version}.",
                )
            )

    existing = _read_project_content(root, blockers)
    if existing is None:
        if not any(blocker.path == PROJECT_FILE for blocker in blockers):
            blockers.append(Blocker("project-not-initialized", PROJECT_FILE, "Run svc init before recording a later adoption."))
    else:
        try:
            state = parse_project_state(existing)
        except ValueError as error:
            blockers.append(Blocker("invalid-project-state", PROJECT_FILE, str(error)))
        else:
            _block_noncurrent_schema(state, blockers)
            if not blockers and state.svc_version != target_version:
                writes.append(
                    make_write(
                        root,
                        PROJECT_FILE,
                        "adopt",
                        "record explicit project adoption",
                        _replace_svc_version_span(existing, target_version),
                    )
                )
    return LocalPlan("adopt", root, target_version, tuple(writes), tuple(blockers))


def inspect_status(repo: Path) -> dict[str, object]:
    root = _require_repo(repo)
    corpus = catalog()
    installed_cli_version = installed_distribution_version()
    runtime_status = (
        "source-tree"
        if installed_cli_version is None
        else "current"
        if installed_cli_version == corpus.svc_version
        else "mismatch"
    )
    project = _inspect_project(root, corpus.svc_version)
    configuration = _inspect_configuration(root)
    guidance = [
        _inspect_guidance(root, CODEX_SKILL_FILE, "codex-skill", inspect_skill),
        _inspect_guidance(root, AGENTS_FILE, "agents-navigation", inspect_navigation),
        _inspect_guidance(root, DOCS_INDEX_FILE, "docs-navigation", inspect_navigation),
    ]
    managed_ignore = _inspect_guidance(root, ".gitignore", "local-config-ignore", inspect_local_config_ignore)
    healthy = (
        runtime_status != "mismatch"
        and project["status"] == "adopted"
        and configuration["status"] == "current"
        and managed_ignore["status"] == "current"
        and all(item["status"] == "current" for item in guidance)
    )
    return {
        "schema_version": 1,
        "installed_cli_version": installed_cli_version,
        "packaged_svc_version": corpus.svc_version,
        "resource_mode": resource_mode(),
        "runtime": {"status": runtime_status},
        "project": project,
        "configuration": configuration,
        "managed_ignore": managed_ignore,
        "guidance": guidance,
        "healthy": healthy,
    }


def _require_repo(repo: Path) -> Path:
    root = repo.resolve()
    if not root.is_dir():
        raise SvcError("repo-not-directory", "Project root is not a directory.", {"repo": str(repo)})
    return root


def _path(root: Path, relative: str) -> Path:
    return root.joinpath(*relative.split("/"))


def _read_optional(root: Path, relative: str) -> bytes | None:
    path = _path(root, relative)
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise SvcError("path-not-file", "Integration target must be a regular file.", {"path": relative})
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
) -> list[PlannedWrite]:
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
    return [make_write(root, relative, proposal.action, proposal.reason, proposal.content)]


def _inspect_project(root: Path, available_version: str) -> dict[str, object]:
    try:
        content = _read_optional(root, PROJECT_FILE)
    except SvcError as error:
        return {"path": PROJECT_FILE, "status": "invalid", "message": error.message}
    if content is None:
        return {"path": PROJECT_FILE, "status": "missing", "svc_version": None}
    try:
        state = parse_project_state(content)
    except ValueError as error:
        return {"path": PROJECT_FILE, "status": "invalid", "message": str(error)}
    if state.schema_version != PROJECT_SCHEMA_VERSION:
        return {
            "path": PROJECT_FILE,
            "status": "schema-v1-write-blocked" if state.schema_version == 1 else "schema-write-blocked",
            "schema_version": state.schema_version,
            "svc_version": state.svc_version,
        }
    return {
        "path": PROJECT_FILE,
        "status": "adopted" if state.svc_version == available_version else "adoption-pending",
        "schema_version": state.schema_version,
        "svc_version": state.svc_version,
    }


def _inspect_configuration(root: Path) -> dict[str, object]:
    try:
        resolved = load_config(root)
    except ConfigError as error:
        return {"status": "invalid", "message": str(error)}
    return {
        "status": "current",
        "base": {"path": PROJECT_FILE, "status": "valid", "digest": resolved.base_digest},
        "local": {
            "path": LOCAL_CONFIG_FILE,
            "status": "absent" if resolved.local is None else "valid",
            "digest": resolved.local_digest,
        },
        "effective": {"status": "valid", "digest": resolved.effective_digest},
    }


def _block_noncurrent_schema(state: ProjectState | ProjectConfig, blockers: list[Blocker]) -> None:
    if state.schema_version == PROJECT_SCHEMA_VERSION:
        return
    if state.schema_version == 1:
        blockers.append(
            Blocker(
                "schema-v1-write-blocked",
                PROJECT_FILE,
                "SVC 10.0.1 does not automatically migrate schema-v1 projects; migrate the project configuration deliberately before writing.",
            )
        )
        return
    blockers.append(Blocker("schema-write-blocked", PROJECT_FILE, f"Unsupported svc.json schema: {state.schema_version}."))


def _replace_svc_version_span(content: bytes, version: str) -> bytes:
    """Replace only the root ``svc_version`` JSON value without reformatting JSON."""

    require_semver(version, "project svc_version")
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
        if key == "svc_version":
            if found is not None:
                raise ValueError("svc.json contains duplicate svc_version entries")
            found = (value_start, value_end)
        index = _skip_json_space(text, value_end)
        if index < len(text) and text[index] == ",":
            index += 1
            continue
        if index < len(text) and text[index] == "}":
            break
        raise ValueError("svc.json object entry is malformed")
    if found is None:
        raise ValueError("svc.json has no svc_version entry")
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
    inspect: Callable[[bytes | None], object],
) -> dict[str, str]:
    try:
        content = _read_optional(root, relative)
        inspection = inspect(content)
    except (IntegrationProblem, SvcError) as error:
        return {"path": relative, "kind": kind, "status": "modified", "message": str(error)}
    return {"path": relative, "kind": kind, "status": inspection.status}
