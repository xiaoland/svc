"""Collection and publication of schema-v3 Agent-thread evidence."""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any, BinaryIO, Callable, Mapping, cast

from ..errors import SvcError
from ..release import runtime_version
from .agent_threads import (
    NormalizationResult,
    NormalizationStatus,
    EvidenceThreadProvider,
    ProviderContext,
    ResolvedThread,
    ThreadSelection,
    SourceStatus,
)
from .evidence import (
    EvidenceError,
    build_evidence_manifest,
    encode_native_index,
    validate_evidence,
    write_evidence_stream,
)
from .trajectory import (
    DEFAULT_NORMALIZATION_POLICY,
    TrajectoryCollector,
    TrajectoryError,
    build_manifest,
    policy_dict,
)


def _evidence_output(
    output: Path,
) -> Path:
    """Validate the stable request shape; exclusive creation owns absence."""

    requested = Path(output).expanduser()
    if requested.suffix != ".zip":
        raise ValueError("Evidence output must have an explicit .zip suffix")
    if not requested.parent.is_dir():
        raise ValueError("Evidence output parent must be an existing directory")
    return requested


def _publish_output(
    output: Path,
    writer: Callable[[BinaryIO], object],
) -> None:
    """Exclusively create one target and retain it only after validation."""

    created = False
    try:
        with output.open("x+b") as archive_stream:
            created = True
            writer(archive_stream)
        validate_evidence(output)
    except Exception:
        if created:
            try:
                output.unlink()
            except OSError:
                pass
        raise


def _diagnostic_sort_key(
    diagnostic: Mapping[str, Any],
) -> tuple[tuple[int, int, int, int], bytes, bytes]:
    source = diagnostic.get("source_ref")
    missing = 2**63 - 1
    coordinates = cast(tuple[int, int, int, int], tuple(
        (
            source.get(key, missing)
            if isinstance(source, Mapping)
            and isinstance(source.get(key, missing), int)
            else missing
        )
        for key in ("event_index", "line", "byte_offset", "component_index")
    ))
    from .trajectory import canonical_json_bytes

    return (
        coordinates,
        str(diagnostic.get("code", "")).encode("ascii"),
        canonical_json_bytes(diagnostic.get("details", {})),
    )


def _finalize_normalization(
    result: NormalizationResult,
    collector: TrajectoryCollector,
    *,
    diagnostic_limit: int = DEFAULT_NORMALIZATION_POLICY.diagnostics,
) -> tuple[dict[str, Any], dict[str, dict[str, int]], list[dict[str, Any]], str]:
    lossiness = {
        group: dict(values)
        for group, values in result.lossiness.items()
    }
    raw_diagnostics = [dict(item) for item in result.diagnostics]
    prior_limit_marker = next(
        (
            item
            for item in raw_diagnostics
            if item.get("code") == "diagnostic-limit-reached"
        ),
        None,
    )
    diagnostics = [
        item
        for item in raw_diagnostics
        if item.get("code") != "diagnostic-limit-reached"
    ]
    if prior_limit_marker is None:
        observed_diagnostic_groups = len(diagnostics)
    else:
        details = prior_limit_marker.get("details")
        observed = (
            details.get("observed_count")
            if isinstance(details, Mapping)
            else None
        )
        observed_diagnostic_groups = (
            observed
            if isinstance(observed, int)
            and not isinstance(observed, bool)
            and observed >= len(diagnostics)
            else len(diagnostics)
        )
    diagnostics_suppressed = int(
        result.counts.get("diagnostics_suppressed", 0)
    )
    status = NormalizationStatus(result.result_status).value
    if collector.limit_reason is not None:
        reason = collector.limit_reason
        # A provider sees sink backpressure only and may conservatively report
        # a record limit. The collector owns the exact resource, observation,
        # and bound, so replace that speculative group for either core limit.
        provider_reported_record_limit = (
            lossiness["partial_reasons"]["record_limit"] > 0
        )
        retained_record_limit = [
            item
            for item in diagnostics
            if item.get("code") == "record-limit-reached"
        ]
        diagnostics = [
            item
            for item in diagnostics
            if item.get("code") != "record-limit-reached"
        ]
        if provider_reported_record_limit:
            lossiness["partial_reasons"]["record_limit"] -= 1
            observed_diagnostic_groups = max(
                0,
                observed_diagnostic_groups - 1,
            )
            if prior_limit_marker is not None and not retained_record_limit:
                # The provider's one speculative group was already among the
                # suppressed occurrences represented by its limit marker.
                diagnostics_suppressed = max(
                    0,
                    diagnostics_suppressed - 1,
                )
        lossiness["partial_reasons"][reason] += 1
        status = NormalizationStatus.PARTIAL.value
        observed_key = (
            "observed_count"
            if reason == "record_limit"
            else "observed_bytes"
        )
        limit_key = "limit_count" if reason == "record_limit" else "limit_bytes"
        observed = collector.limit_observed
        limit = collector.limit_value
        if observed is None or limit is None:
            raise ValueError(
                "Trajectory collector omitted exact limit evidence."
            )
        diagnostics.append(
            {
                "code": reason.replace("_", "-") + "-reached",
                "severity": "warning",
                "action": "partial",
                "count": 1,
                "record_ref": None,
                "source_ref": None,
                "details": {observed_key: observed, limit_key: limit},
            }
        )
        observed_diagnostic_groups += 1

    diagnostics.sort(key=_diagnostic_sort_key)
    observed_diagnostic_groups = max(
        observed_diagnostic_groups,
        len(diagnostics),
    )
    if observed_diagnostic_groups > diagnostic_limit:
        retained = diagnostics[: diagnostic_limit - 1]
        suppressed = diagnostics[diagnostic_limit - 1 :]
        newly_suppressed = sum(int(item["count"]) for item in suppressed)
        diagnostics_suppressed += newly_suppressed
        retained.append(
            {
                "code": "diagnostic-limit-reached",
                "severity": "warning",
                "action": "truncate",
                "count": 1,
                "record_ref": None,
                "source_ref": None,
                "details": {
                    "observed_count": observed_diagnostic_groups,
                    "limit_count": diagnostic_limit,
                },
            }
        )
        diagnostics = retained

    lossiness["truncated"]["diagnostics"] = diagnostics_suppressed
    counts = dict(result.counts)
    counts["diagnostics_emitted"] = sum(
        int(item["count"]) for item in diagnostics
    )
    counts["diagnostics_suppressed"] = diagnostics_suppressed
    return counts, lossiness, diagnostics, status


def _normalize_captured_to_streams(
    provider: EvidenceThreadProvider,
    context: ProviderContext,
    selection: ThreadSelection,
    native_stream: BinaryIO,
    trajectory_stream: BinaryIO,
    *,
    resolved: ResolvedThread | None = None,
) -> tuple[dict[str, Any], bytes, bytes, bytes]:
    """Capture once, then build the native-bound projection from that capture."""

    resolved = resolved or provider.resolve(context, selection)
    if resolved.provider_id != provider.provider_id:
        raise ValueError(
            "Resolved thread provider_id does not match provider"
        )
    bounds = policy_dict()["bounds"]
    assert isinstance(bounds, Mapping)
    native_stream.seek(0)
    native_stream.truncate(0)
    capture = provider.capture_native(
        resolved,
        native_stream,
        cast(Mapping[str, int], bounds),
    )
    if (
        capture.provider_id != resolved.provider_id
        or capture.adapter_id != resolved.adapter_id
        or capture.source_format != resolved.source_format
    ):
        raise ValueError("Captured source identity does not match selection")
    native_index = encode_native_index(capture.frames)

    trajectory_stream.seek(0)
    trajectory_stream.truncate(0)
    collector = TrajectoryCollector(trajectory_stream)
    native_stream.seek(0)
    result = provider.stream_normalize_captured(
        resolved,
        native_stream,
        capture,
        collector.emit,
        cast(Mapping[str, int], bounds),
    )
    encoded = collector.finish()
    counts, lossiness, diagnostics, result_status = (
        _finalize_normalization(
            result,
            collector,
            diagnostic_limit=int(bounds["diagnostics"]),
        )
    )
    counts.update(
        {
            "records_emitted": encoded.records,
            "trajectory_bytes": encoded.trajectory_size,
            "records_by_type": dict(encoded.records_by_type),
            "messages_by_role": dict(encoded.messages_by_role),
            "tool_calls": encoded.tool_calls,
            "tool_results": encoded.tool_results,
            "task_references": encoded.task_references,
        }
    )
    trajectory_stream.seek(0)
    projection = dict(
        build_manifest(
            trajectory_source=trajectory_stream,
            source={
                "provider_id": result.provider_id,
                "adapter_id": result.adapter_id,
                "source_format": result.source_format,
                "thread_ref": result.thread_ref,
                "source_status": SourceStatus(result.source_status).value,
            },
            result_status=result_status,
            capabilities=result.capabilities,
            lossiness=lossiness,
            diagnostics=diagnostics,
            counts=counts,
            exporter_version=runtime_version(),
        )
    )
    native_stream.seek(0)
    native_bytes = native_stream.read()
    trajectory_stream.seek(0)
    trajectory_bytes = trajectory_stream.read()
    if not isinstance(native_bytes, bytes) or not isinstance(
        trajectory_bytes,
        bytes,
    ):
        raise ValueError("Evidence staging streams must return bytes")
    manifest = dict(
        build_evidence_manifest(
            native=native_bytes,
            native_index=native_index,
            projection=projection,
            trajectory=trajectory_bytes,
            capture={
                "status": "partial" if capture.is_partial else "complete",
                "unknown_remainder": capture.unknown_remainder,
                "representation": "provider-bytes",
            },
        )
    )
    return manifest, native_bytes, native_index, trajectory_bytes


def write_agent_thread_evidence(
    provider: EvidenceThreadProvider,
    context: ProviderContext,
    selection: ThreadSelection,
    output: Path,
) -> dict[str, Any]:
    """Capture and exclusively create one validated schema-v3 archive."""

    resolved = provider.resolve(context, selection)
    target = _evidence_output(output)
    native = tempfile.SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b")
    trajectory = tempfile.SpooledTemporaryFile(
        max_size=1024 * 1024,
        mode="w+b",
    )
    try:
        manifest, native_bytes, native_index, trajectory_bytes = (
            _normalize_captured_to_streams(
                provider,
                context,
                selection,
                cast(BinaryIO, native),
                cast(BinaryIO, trajectory),
                resolved=resolved,
            )
        )

        def write(stream: BinaryIO) -> Any:
            return write_evidence_stream(
                stream,
                manifest,
                native_bytes,
                native_index,
                trajectory_bytes,
            )

        _publish_output(target, write)
        return manifest
    except (TrajectoryError, EvidenceError) as error:
        raise SvcError(error.code, error.message) from error
    finally:
        native.close()
        trajectory.close()


__all__ = [
    "write_agent_thread_evidence",
]
