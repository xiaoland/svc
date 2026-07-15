"""Generated, bounded integration surfaces that point Codex back to `svc`."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .catalog import sha256_bytes


NAVIGATION_BEGIN_RE = re.compile(
    r"<!-- svc:begin navigation sha256=(?P<digest>[0-9a-f]{64}) -->\n"
)
NAVIGATION_BLOCK_RE = re.compile(
    r"<!-- svc:begin navigation sha256=(?P<digest>[0-9a-f]{64}) -->\n"
    r"(?P<body>.*?)\n"
    r"<!-- svc:end navigation -->(?P<tail>\n?)",
    re.DOTALL,
)
LOCAL_CONFIG_IGNORE_RE = re.compile(
    r"(?ms)^# svc:begin local-config sha256=(?P<digest>[0-9a-f]{64})\r?\n"
    r"(?P<body>.*?)"
    r"^# svc:end local-config\r?\n?"
)
SKILL_MARKER_RE = re.compile(
    r"^<!-- svc:generated skill sha256=(?P<digest>[0-9a-f]{64}) -->\n?$",
    re.MULTILINE,
)


class IntegrationProblem(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class IntegrationInspection:
    status: str
    content: str | None
    match: re.Match[str] | None = None


@dataclass(frozen=True)
class DesiredIntegration:
    action: str
    reason: str
    content: bytes


def navigation_body() -> str:
    return (
        "## SVC\n\n"
        "This project uses the local Sustainable Vibe Coding CLI. Query framework guidance "
        "when it is needed instead of copying framework documents into this repository.\n\n"
        "- Use `svc lookup --keyword \"<need>\"` to find relevant guidance, then `svc lookup "
        "--name '<exact-path-regex>'` to read an authoritative document.\n"
        "- Use `svc status` before broad process changes. If the installed corpus is newer than "
        "the adopted version in `svc.json`, read its migration guidance before `svc adopt`.\n"
        "- Treat all unmarked project instructions and documentation as consumer-owned."
    )


def render_navigation_block() -> str:
    body = navigation_body()
    digest = sha256_bytes(body.encode("utf-8"))
    return (
        f"<!-- svc:begin navigation sha256={digest} -->\n"
        f"{body}\n"
        "<!-- svc:end navigation -->\n"
    )


def skill_body() -> str:
    return (
        "---\n"
        "name: svc\n"
        "description: Use the local Sustainable Vibe Coding CLI to bootstrap, inspect, and evolve "
        "a project without copying framework documents. Trigger for SVC guidance, project adoption, "
        "or safe SVC CLI use; do not use it to replace consumer-owned project truth.\n"
        "---\n\n"
        "# Sustainable Vibe Coding\n\n"
        "SVC is a versioned, local knowledge corpus plus a small development-collaboration CLI. "
        "Its canonical guidance stays inside the installed `svc` distribution. This project owns its "
        "own product truth, technical decisions, task packets, and unmarked documentation.\n\n"
        "## Start With Status\n\n"
        "Run `svc status --json` when beginning work that may depend on SVC. It distinguishes the "
        "installed CLI/corpus version from the version this project has adopted in `svc.json`, and "
        "reports invalid schema-v2 configuration, missing or user-modified generated guidance, and the "
        "managed local-config ignore block without claiming authority over project content.\n\n"
        "## Find Canonical Guidance\n\n"
        "Use `svc lookup --keyword \"<need>\" --json` to search locally and deterministically. "
        "Use the returned path with `svc lookup --name '<escaped-exact-path>' --json` to read the "
        "document. `--name` is a full-path regular expression over source-relative SVC paths; use "
        "`--all` only when several documents are intended. Prefer this two-step lookup over remembering "
        "or reproducing SVC rules from this skill.\n\n"
        "## Bootstrap or Repair Integration\n\n"
        "Use `svc init --agent codex <repo> --json` to inspect a non-mutating plan. Apply only the "
        "returned exact digest with `--apply <digest>`. Init may create `svc.json`, this skill, and "
        "bounded navigation blocks in root `AGENTS.md` and `docs/index.md`, plus a marked `.gitignore` "
        "entry for `svc.local.json`; it never silently overwrites unmarked consumer content or a modified "
        "generated surface. Schema-v1 projects are write-blocked: migrate the configuration deliberately.\n\n"
        "## Declare Development Capabilities\n\n"
        "`svc.json` schema v2 is a complete, committed configuration. Its optional `dev` section selects a "
        "profile and declares named targets. Each target has a scope (`worktree`, `repository`, or `host`), "
        "one readiness probe (`http`, `tcp`, or `exec`), and an `exec` or `manual` provisioner. Keep machine- "
        "or worktree-specific `dev` values in the optional ignored `svc.local.json` overlay. It merges object "
        "values into the base configuration, replaces scalar or array values, and cannot override the schema "
        "version, adopted SVC version, or any non-`dev` field. The effective result must pass the same strict "
        "schema.\n\n"
        "Use `svc dev identity --repo <repo> --json` to inspect the resolved workspace identity. Use `svc dev "
        "status [target] --repo <repo> --json` only to observe declared targets: it never starts or takes over "
        "a process. Use `svc dev ensure <target> --repo <repo> --json` to handle exactly one declared target. "
        "Ensure reuses a healthy endpoint, refuses an occupied but unhealthy endpoint, and reports the required "
        "consumer action for a manual provisioner. It coordinates executable provisioning only at the declared "
        "scope and relinquishes process authority after readiness succeeds.\n\n"
        "Worktree scope is the default and a worktree-scoped probe endpoint must prove the resolved instance; "
        "repository scope intentionally shares a capability, and host scope requires an explicit `host_key`. "
        "Only `${dev.instance}`, `${dev.worktree.id}`, `${dev.profile}`, and `${dev.target}` interpolate in "
        "declared dev values. Commands are argument arrays without a shell, and configured working directories "
        "must stay inside the workspace.\n\n"
        "## Add Optional Editor or Package Bridges\n\n"
        "Use `svc dev setup vscode [target] --repo <repo> --plan --json` or `svc dev setup npm [target] "
        "--repo <repo> --plan --json` to inspect one bounded bridge. Apply only its exact current digest with "
        "`--apply <digest>`. Setup owns only marked VS Code Tasks and exact reserved root package scripts that "
        "call `svc dev ensure <target>`; it never reads `launch.json`, chooses a package manager, creates package "
        "metadata, removes orphan entries, or overwrites a Consumer conflict.\n\n"
        "## Upgrade Deliberately\n\n"
        "`svc self-update` plans an update of the installed executable only. It never adopts guidance "
        "for this project. After an update, inspect `svc status`, look up the release migration guidance, "
        "apply necessary consumer-owned changes under this repository's mutation gate, then run `svc adopt "
        "<installed-version>` and explicitly apply its plan.\n\n"
        "## Work With the Project, Not Around It\n\n"
        "Read root and local `AGENTS.md` instructions before editing governed files. Keep active reasoning "
        "in the project's task packet. Use SVC as an on-demand upstream authority; do not create copied "
        "SVC protocol documents, a hidden SVC state directory, or an independent task tracker.\n"
    )


def render_skill() -> str:
    body = skill_body()
    digest = sha256_bytes(body.encode("utf-8"))
    return f"{body}<!-- svc:generated skill sha256={digest} -->\n"


def local_config_ignore_body() -> str:
    return "svc.local.json\n"


def render_local_config_ignore_block(line_ending: str = "\n") -> bytes:
    body = local_config_ignore_body().replace("\n", line_ending)
    digest = sha256_bytes(local_config_ignore_body().encode("utf-8"))
    return (
        f"# svc:begin local-config sha256={digest}{line_ending}".encode("utf-8")
        + body.encode("utf-8")
        + f"# svc:end local-config{line_ending}".encode("utf-8")
    )


def inspect_local_config_ignore(content: bytes | None) -> IntegrationInspection:
    if content is None:
        return IntegrationInspection("missing", None)
    text = _decode(content)
    begin_count = text.count("# svc:begin local-config")
    end_count = text.count("# svc:end local-config")
    if begin_count == 0 and end_count == 0:
        return IntegrationInspection("unanchored", text)
    if begin_count != 1 or end_count != 1:
        return IntegrationInspection("modified", text)
    match = LOCAL_CONFIG_IGNORE_RE.search(text)
    if match is None:
        return IntegrationInspection("modified", text)
    body = match.group("body").replace("\r\n", "\n")
    if sha256_bytes(body.encode("utf-8")) != match.group("digest"):
        return IntegrationInspection("modified", text, match)
    if body != local_config_ignore_body():
        return IntegrationInspection("modified", text, match)
    return IntegrationInspection("current", text, match)


def desired_local_config_ignore(content: bytes | None) -> DesiredIntegration | None:
    inspection = inspect_local_config_ignore(content)
    if inspection.status == "current":
        return None
    if inspection.status in {"modified"}:
        raise IntegrationProblem(
            "managed-ignore-drift",
            "The SVC-managed svc.local.json ignore section is modified or malformed and will not be replaced.",
        )
    line_ending = "\r\n" if inspection.content is not None and "\r\n" in inspection.content else "\n"
    block = render_local_config_ignore_block(line_ending)
    if inspection.status == "missing":
        return DesiredIntegration("create", "create SVC local-config ignore section", block)
    assert inspection.content is not None
    separator = b"" if not inspection.content else line_ending.encode("utf-8") if inspection.content.endswith(("\n", "\r")) else (line_ending * 2).encode("utf-8")
    return DesiredIntegration(
        "append",
        "append SVC local-config ignore section",
        inspection.content.encode("utf-8") + separator + block,
    )


def inspect_navigation(content: bytes | None) -> IntegrationInspection:
    if content is None:
        return IntegrationInspection("missing", None)
    text = _decode(content)
    begin_count = text.count("<!-- svc:begin navigation")
    end_count = text.count("<!-- svc:end navigation -->")
    if begin_count == 0 and end_count == 0:
        return IntegrationInspection("unanchored", text)
    if begin_count != 1 or end_count != 1:
        return IntegrationInspection("modified", text)
    match = NAVIGATION_BLOCK_RE.search(text)
    if match is None:
        return IntegrationInspection("modified", text)
    body = match.group("body")
    if sha256_bytes(body.encode("utf-8")) != match.group("digest"):
        return IntegrationInspection("modified", text, match)
    if body == navigation_body():
        return IntegrationInspection("current", text, match)
    return IntegrationInspection("outdated", text, match)


def inspect_skill(content: bytes | None) -> IntegrationInspection:
    if content is None:
        return IntegrationInspection("missing", None)
    text = _decode(content)
    markers = list(SKILL_MARKER_RE.finditer(text))
    if not markers:
        return IntegrationInspection("modified", text)
    if len(markers) != 1:
        return IntegrationInspection("modified", text)
    match = markers[0]
    if match.end() != len(text):
        return IntegrationInspection("modified", text, match)
    body = text[: match.start()]
    if sha256_bytes(body.encode("utf-8")) != match.group("digest"):
        return IntegrationInspection("modified", text, match)
    if body == skill_body():
        return IntegrationInspection("current", text, match)
    return IntegrationInspection("outdated", text, match)


def desired_navigation(relative_path: str, content: bytes | None) -> DesiredIntegration | None:
    inspection = inspect_navigation(content)
    block = render_navigation_block()
    if inspection.status == "missing":
        heading = "# Project Instructions\n\n" if relative_path == "AGENTS.md" else "# Documentation\n\n"
        return DesiredIntegration("create", "create SVC navigation anchor", (heading + block).encode("utf-8"))
    if inspection.status == "unanchored":
        assert inspection.content is not None
        separator = "" if not inspection.content else "\n" if inspection.content.endswith("\n") else "\n\n"
        return DesiredIntegration(
            "append",
            "add bounded SVC navigation anchor",
            (inspection.content + separator + block).encode("utf-8"),
        )
    if inspection.status == "current":
        return None
    if inspection.status == "outdated":
        assert inspection.content is not None and inspection.match is not None
        refreshed = (
            inspection.content[: inspection.match.start()]
            + block
            + inspection.content[inspection.match.end() :]
        )
        return DesiredIntegration("refresh", "refresh clean generated SVC navigation anchor", refreshed.encode("utf-8"))
    raise IntegrationProblem(
        "generated-guidance-drift",
        "The existing SVC navigation block is modified or malformed and will not be replaced.",
    )


def desired_skill(content: bytes | None) -> DesiredIntegration | None:
    inspection = inspect_skill(content)
    if inspection.status == "missing":
        return DesiredIntegration("create", "install Codex SVC skill", render_skill().encode("utf-8"))
    if inspection.status == "current":
        return None
    if inspection.status == "outdated":
        return DesiredIntegration("refresh", "refresh clean generated Codex SVC skill", render_skill().encode("utf-8"))
    raise IntegrationProblem(
        "generated-skill-drift",
        "The existing Codex SVC skill is modified or malformed and will not be replaced.",
    )


def _decode(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise IntegrationProblem("non-text-guidance-file", "Generated guidance targets must be UTF-8 text.") from error
