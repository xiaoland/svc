"""Public service functions for local Agent-thread evidence acquisition."""

from __future__ import annotations

from pathlib import Path

from ..errors import SvcError
from .agent_threads import (
    ArchiveFilter,
    ArchiveState,
    ProviderContext,
    ThreadInventoryQuery,
    ThreadSelection,
)
from .archive import write_agent_thread_evidence
from .providers import provider as local_provider


TELEMETRY_SCHEMA_VERSION = 3


def _context(codex_home: Path | None) -> ProviderContext:
    return ProviderContext(home=(Path(codex_home).expanduser() if codex_home is not None else None))


def list_agent_threads(
    codex_home: Path | None,
    limit: int,
    archive_state: ArchiveFilter | str = ArchiveFilter.ALL,
) -> dict[str, object]:
    """Return one bounded thread inventory for explicit selection."""

    try:
        query = ThreadInventoryQuery(
            archive_state=archive_state,
            limit=limit,
        )
    except ValueError as error:
        raise SvcError("invalid-inventory-query", str(error)) from error
    provider = local_provider()
    listing = provider.list_inventory(_context(codex_home), query)
    threads = [
        {
            "provider_id": row.provider_id,
            "thread_id": row.thread_id,
            "archive_state": ArchiveState(row.archive_state).value,
            "workspace": row.workspace,
            "title": row.title,
            "first_user_message": row.first_user_message,
            "workspace_truncated": row.workspace_truncated,
            "title_truncated": row.title_truncated,
            "first_user_message_truncated": row.first_user_message_truncated,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "recency_at_ms": row.recency_at_ms,
        }
        for row in listing.items
    ]
    return {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "command": "telemetry agent-thread list",
        "status": "listed",
        "provider": provider.provider_id,
        "threads": threads,
        "inventory_truncated": listing.inventory_truncated,
    }


def export_agent_thread(
    *,
    codex_home: Path | None,
    thread_id: str | None,
    source: Path | None,
    output: Path,
) -> dict[str, object]:
    """Capture one exact source into an immutable schema-v3 evidence ZIP."""

    try:
        selection = ThreadSelection(thread_id=thread_id, source=source)
    except ValueError as error:
        raise SvcError("invalid-thread-selector", str(error)) from error
    try:
        manifest = write_agent_thread_evidence(
            local_provider(),
            _context(codex_home),
            selection,
            Path(output),
        )
    except FileExistsError as error:
        raise SvcError(
            "output-exists",
            "Evidence output already exists and was not replaced.",
            {"path": str(output)},
        ) from error
    except ValueError as error:
        raise SvcError("invalid-export-request", str(error)) from error
    except OSError as error:
        raise SvcError(
            "output-write-failed",
            "Could not write the Agent-thread evidence bundle.",
            {"path": str(output), "reason": str(error)},
        ) from error

    projection = manifest["projection"]
    assert isinstance(projection, dict)
    return {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "command": "telemetry agent-thread export",
        "status": "exported",
        "evidence": {
            "path": str(output),
            "evidence_id": manifest["evidence_id"],
            "schema_version": manifest["schema_version"],
            "native": manifest["native"],
            "native_index": manifest["native_index"],
        },
        "capture": manifest["capture"],
        "source": projection["source"],
        "projection_status": projection["result_status"],
        "capabilities": projection["capabilities"],
        "lossiness": projection["lossiness"],
        "diagnostic_groups": len(projection["diagnostics"]),
    }


__all__ = ["export_agent_thread", "list_agent_threads"]
