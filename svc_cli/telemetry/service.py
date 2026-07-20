"""Public service functions for explicit local agent-thread telemetry."""

from __future__ import annotations

from pathlib import Path

from ..errors import SvcError
from .agent_threads import ProviderContext, ThreadSelection
from .archive import write_agent_thread_archive
from .providers import provider as local_provider


TELEMETRY_SCHEMA_VERSION = 1


def _context(codex_home: Path | None) -> ProviderContext:
    return ProviderContext(home=Path(codex_home).expanduser() if codex_home is not None else None)


def list_agent_threads(codex_home: Path | None, limit: int) -> dict[str, object]:
    """List safe Codex thread selection metadata without reading thread bodies."""

    provider = local_provider()
    try:
        listing = provider.list_metadata(_context(codex_home), limit)
    except SvcError as error:
        # A list command is deliberately metadata-only.  Provider diagnostics
        # can contain a local rollout path or SQLite implementation detail, so
        # preserve its stable code/message but not those private details.
        raise SvcError(error.code, error.message) from error
    payload: dict[str, object] = {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "command": "telemetry agent-thread list",
        "status": "listed",
        "provider": provider.provider_id,
        "threads": [descriptor.as_dict() for descriptor in listing.descriptors],
    }
    if listing.omitted_sources:
        payload["warnings"] = [{"code": "thread-source-omitted", "count": listing.omitted_sources}]
    return payload


def export_agent_thread(
    *,
    codex_home: Path | None,
    thread_id: str | None,
    source: Path | None,
    repository: Path,
    output: Path,
    include_sensitive: bool,
) -> dict[str, object]:
    """Create one explicit, local, sensitive Codex evidence archive."""

    if not include_sensitive:
        raise SvcError(
            "sensitive-export-not-acknowledged",
            "Exporting a full agent thread requires --include-sensitive.",
        )
    try:
        selection = ThreadSelection(thread_id=thread_id, source=source)
    except ValueError as error:
        raise SvcError("invalid-thread-selector", str(error)) from error

    provider = local_provider()
    try:
        manifest = write_agent_thread_archive(
            provider,
            _context(codex_home),
            selection,
            Path(repository),
            Path(output),
        )
    except SvcError:
        raise
    except FileExistsError as error:
        raise SvcError("output-exists", "Archive output already exists and was not replaced.", {"output": str(output)}) from error
    except ValueError as error:
        raise SvcError("invalid-export-request", str(error)) from error
    except OSError as error:
        raise SvcError("output-write-failed", f"Could not write agent-thread archive: {error}", {"output": str(output)}) from error

    return {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "command": "telemetry agent-thread export",
        "status": "exported",
        "archive": {
            "path": str(output),
            "source_sha256": manifest["source_sha256"],
            "source_bytes": manifest["source_bytes"],
        },
        "provider": manifest["provider"],
        "thread": manifest["thread"],
        "task_packets": manifest["task_packets"],
        "warnings": manifest["warnings"],
    }
