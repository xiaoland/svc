"""Public service functions for explicit local agent-thread telemetry."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..errors import SvcError
from .analysis import (
    AnalysisError,
    AnalysisResult,
    analyze_trajectory,
)
from .agent_threads import (
    ArchiveFilter,
    ProviderContext,
    SensitiveInventoryListing,
    SensitiveInventoryQuery,
    ThreadInventoryQuery,
    ThreadSelection,
)
from .archive import normalize_agent_thread, write_agent_thread_bundle
from .providers import provider as local_provider
from .trajectory import (
    TrajectoryError,
    ValidatedBundle,
    validate_bundle,
)


TELEMETRY_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PreparedAgentThreadAnalysis:
    """Validated evidence plus its deterministic projection for local use."""

    bundle: ValidatedBundle = field(repr=False)
    analysis: AnalysisResult = field(repr=False)

    def __repr__(self) -> str:
        return (
            "PreparedAgentThreadAnalysis("
            f"bundle_id={self.analysis.bundle_id!r}, "
            f"result_status={self.analysis.result_status!r})"
        )


def _context(codex_home: Path | None) -> ProviderContext:
    return ProviderContext(home=Path(codex_home).expanduser() if codex_home is not None else None)


def _inventory_query(archive_state: ArchiveFilter | str, limit: int) -> ThreadInventoryQuery:
    try:
        return ThreadInventoryQuery(archive_state=archive_state, limit=limit)
    except ValueError as error:
        raise SvcError("invalid-inventory-query", str(error)) from error


def list_agent_threads(
    codex_home: Path | None,
    limit: int,
    archive_state: ArchiveFilter | str = ArchiveFilter.ALL,
) -> dict[str, object]:
    """List safe Codex thread selection metadata without reading thread bodies."""

    provider = local_provider()
    try:
        query = _inventory_query(archive_state, limit)
        listing = provider.list_inventory(_context(codex_home), query)
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
        "threads": [item.as_descriptor().as_dict() for item in listing.items],
    }
    if listing.omitted_sources:
        payload["warnings"] = [{"code": "thread-source-omitted", "count": listing.omitted_sources}]
    return payload


def list_sensitive_agent_threads(
    codex_home: Path | None,
    archive_state: ArchiveFilter | str = ArchiveFilter.ACTIVE,
) -> SensitiveInventoryListing:
    """Return the in-process-only bounded recognition inventory."""

    try:
        query = SensitiveInventoryQuery(archive_state=archive_state)
    except ValueError as error:
        raise SvcError(
            "invalid-inventory-query",
            str(error),
        ) from error
    provider = local_provider()
    try:
        return provider.list_sensitive_inventory(
            _context(codex_home),
            query,
        )
    except SvcError as error:
        raise SvcError(error.code, error.message) from error


def export_agent_thread(
    *,
    codex_home: Path | None,
    thread_id: str | None,
    source: Path | None,
    repository: Path,
    output: Path,
    include_sensitive: bool,
) -> dict[str, object]:
    """Create one explicit, local, sensitive normalized trajectory bundle."""

    if not include_sensitive:
        raise SvcError(
            "sensitive-export-not-acknowledged",
            "Exporting a normalized agent thread requires --include-sensitive.",
        )
    try:
        selection = ThreadSelection(thread_id=thread_id, source=source)
    except ValueError as error:
        raise SvcError("invalid-thread-selector", str(error)) from error

    provider = local_provider()
    try:
        manifest = write_agent_thread_bundle(
            provider,
            _context(codex_home),
            selection,
            Path(repository),
            Path(output),
        )
    except SvcError as error:
        # Provider/archive diagnostics may carry native IDs, source paths, or
        # operating-system details.  The public export failure is deliberately
        # stable and redacted, just like the safe inventory path.
        raise SvcError(error.code, error.message) from error
    except FileExistsError as error:
        raise SvcError(
            "output-exists",
            "Bundle output already exists and was not replaced.",
        ) from error
    except ValueError as error:
        raise SvcError("invalid-export-request", str(error)) from error
    except OSError as error:
        raise SvcError(
            "output-write-failed",
            "Could not write the agent-thread bundle.",
        ) from error

    return {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "command": "telemetry agent-thread export",
        "status": "exported",
        "bundle": {
            "path": str(output),
            "bundle_id": manifest["bundle_id"],
            "trajectory": manifest["trajectory"],
        },
        "source": manifest["source"],
        "result_status": manifest["result_status"],
        "capabilities": manifest["capabilities"],
        "counts": manifest["counts"],
        "lossiness": manifest["lossiness"],
        "diagnostics": manifest["diagnostics"],
    }


def prepare_agent_thread_analysis(
    *,
    input_bundle: Path | None,
    thread_id: str | None,
    source: Path | None,
    codex_home: Path | None,
) -> PreparedAgentThreadAnalysis:
    """Validate or ephemerally normalize exactly one analysis authority."""

    selectors = sum(
        value is not None
        for value in (input_bundle, thread_id, source)
    )
    if selectors != 1:
        raise SvcError(
            "invalid-analysis-request",
            "Exactly one analysis input, thread ID, or source is required.",
        )
    if input_bundle is not None and codex_home is not None:
        raise SvcError(
            "invalid-analysis-request",
            "--codex-home is not valid with --input.",
        )

    try:
        if input_bundle is not None:
            bundle = validate_bundle(Path(input_bundle))
        else:
            selection = ThreadSelection(
                thread_id=thread_id,
                source=source,
            )
            bundle = normalize_agent_thread(
                local_provider(),
                _context(codex_home),
                selection,
            )
        analysis = analyze_trajectory(bundle)
        return PreparedAgentThreadAnalysis(bundle, analysis)
    except SvcError as error:
        raise SvcError(error.code, error.message) from error
    except TrajectoryError as error:
        raise SvcError(error.code, error.message) from error
    except AnalysisError as error:
        raise SvcError(error.code, error.message) from error
    except ValueError as error:
        raise SvcError(
            "invalid-analysis-request",
            str(error),
        ) from error
