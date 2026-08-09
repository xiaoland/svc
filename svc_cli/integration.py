"""Generated, bounded project integration and legacy provenance inspection."""

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


def navigation_body(relative_path: str = "AGENTS.md") -> str:
    if relative_path == "AGENTS.md":
        return (
            "## SVC\n\n"
            "Use the installed `svc` CLI when SVC guidance or project integration is "
            "relevant. Discover the current interface through `svc --help` and "
            "`svc <command> --help`; `svc lookup` reads the SVC Corpus, not CLI help. "
            "Treat unmarked project instructions and documentation as Consumer-owned."
        )
    return (
        "## SVC Corpus\n\n"
        "Use `svc lookup` when packaged Sustainable Vibe Coding Corpus guidance is "
        "relevant, and discover its browse/search/read grammar through "
        "`svc lookup --help`. Project documentation outside this marked block remains "
        "Consumer-owned."
    )


def render_navigation_block(relative_path: str = "AGENTS.md") -> str:
    body = navigation_body(relative_path)
    digest = sha256_bytes(body.encode("utf-8"))
    return (
        f"<!-- svc:begin navigation sha256={digest} -->\n"
        f"{body}\n"
        "<!-- svc:end navigation -->\n"
    )


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
    line_ending = (
        "\r\n"
        if inspection.content is not None and "\r\n" in inspection.content
        else "\n"
    )
    block = render_local_config_ignore_block(line_ending)
    if inspection.status == "missing":
        return DesiredIntegration(
            "create", "create SVC local-config ignore section", block
        )
    assert inspection.content is not None
    separator = (
        b""
        if not inspection.content
        else line_ending.encode("utf-8")
        if inspection.content.endswith(("\n", "\r"))
        else (line_ending * 2).encode("utf-8")
    )
    return DesiredIntegration(
        "append",
        "append SVC local-config ignore section",
        inspection.content.encode("utf-8") + separator + block,
    )


def inspect_navigation(
    content: bytes | None, relative_path: str = "AGENTS.md"
) -> IntegrationInspection:
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
    if body == navigation_body(relative_path):
        return IntegrationInspection("current", text, match)
    return IntegrationInspection("outdated", text, match)


def inspect_retired_skill(content: bytes | None) -> IntegrationInspection:
    if content is None:
        return IntegrationInspection("missing", None)
    text = _decode(content)
    markers = list(SKILL_MARKER_RE.finditer(text))
    if not markers:
        return IntegrationInspection("unowned", text)
    if len(markers) != 1:
        return IntegrationInspection("modified", text)
    match = markers[0]
    if match.end() != len(text):
        return IntegrationInspection("modified", text, match)
    body = text[: match.start()]
    if sha256_bytes(body.encode("utf-8")) != match.group("digest"):
        return IntegrationInspection("modified", text, match)
    return IntegrationInspection("clean-generated", text, match)


def desired_navigation(
    relative_path: str, content: bytes | None
) -> DesiredIntegration | None:
    inspection = inspect_navigation(content, relative_path)
    block = render_navigation_block(relative_path)
    if inspection.status == "missing":
        heading = (
            "# Project Instructions\n\n"
            if relative_path == "AGENTS.md"
            else "# Documentation\n\n"
        )
        return DesiredIntegration(
            "create", "create SVC navigation anchor", (heading + block).encode("utf-8")
        )
    if inspection.status == "unanchored":
        assert inspection.content is not None
        separator = (
            ""
            if not inspection.content
            else "\n"
            if inspection.content.endswith("\n")
            else "\n\n"
        )
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
        return DesiredIntegration(
            "refresh",
            "refresh clean generated SVC navigation anchor",
            refreshed.encode("utf-8"),
        )
    raise IntegrationProblem(
        "generated-guidance-drift",
        "The existing SVC navigation block is modified or malformed and will not be replaced.",
    )


def _decode(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise IntegrationProblem(
            "non-text-guidance-file", "Generated guidance targets must be UTF-8 text."
        ) from error
