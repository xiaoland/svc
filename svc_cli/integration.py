"""Generated, bounded integration surfaces that point Codex back to `svc`."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .catalog import sha256_bytes
from .lookup import LIST_GUIDANCE_COMMAND, READ_GUIDANCE_COMMAND


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
        "- Run `svc status --json` as the first SVC command in a repository. If it reports "
        "`unadopted`, request Human authorization before running `svc init`; do not use init "
        "to discover state. If the installed corpus is newer than the adopted version in `svc.json`, "
        "read its migration guidance before `svc adopt`.\n"
        f"- Run `{LIST_GUIDANCE_COMMAND}` to list local canonical guidance, then "
        f"`{READ_GUIDANCE_COMMAND}` to read one exact document. Use "
        "`svc lookup --keyword \"<need>\" --json` only when the titles do not resolve the need.\n"
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
        "description: Use the local SVC CLI for SVC guidance, CLI troubleshooting, or project "
        "integration. It routes to the installed canonical corpus and does not replace "
        "consumer-owned project truth.\n"
        "---\n\n"
        "# Sustainable Vibe Coding\n\n"
        "Run `svc status --json` as the first SVC command in a repository. "
        "If it reports `unadopted`, request Human authorization before running `svc init`; do "
        "not use init to discover state.\n\n"
        "Use the installed local corpus before web search for SVC guidance or CLI troubleshooting. "
        "If no exact source-relative path is known:\n\n"
        f"1. `{LIST_GUIDANCE_COMMAND}`\n"
        f"2. `{READ_GUIDANCE_COMMAND}`\n\n"
        "Use `svc lookup --keyword \"<need>\" --json` only when the listed titles do not "
        "resolve the need. Use `svc <command> --help` to discover the current command contract.\n\n"
        "Read root and local `AGENTS.md` before changing governed files. Mutating commands require "
        "repository-scoped authorization; a returned plan is not approval, and only its exact digest "
        "may be applied. Consumer-owned instructions, product truth, technical decisions, task packets, "
        "and unmarked documentation remain authoritative.\n\n"
        "This Skill is a router, not a copy of SVC guidance.\n"
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
