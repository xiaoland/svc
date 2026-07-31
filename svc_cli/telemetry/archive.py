"""Safe collection and publication of schema-v3 Agent-thread evidence."""

from __future__ import annotations

from dataclasses import dataclass
import errno
import os
from pathlib import Path
import secrets
import stat
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
    ValidatedEvidence,
    build_evidence_manifest,
    encode_native_index,
    validate_evidence_members,
    write_evidence_stream,
)
from .trajectory import (
    DEFAULT_NORMALIZATION_POLICY,
    TrajectoryCollector,
    TrajectoryError,
    build_manifest,
    policy_dict,
)


_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


@dataclass(frozen=True)
class _OutputTarget:
    output: Path
    parent_identity: tuple[int, int, int]


def _is_link_or_reparse_point(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        (getattr(info, "st_file_attributes", 0) or 0)
        & _FILE_ATTRIBUTE_REPARSE_POINT
    )


def _directory_identity(info: os.stat_result) -> tuple[int, int, int]:
    return (info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode))


def _regular_file_identity(
    info: os.stat_result,
    *,
    description: str,
) -> tuple[int, int, int, int, int]:
    if _is_link_or_reparse_point(info) or not stat.S_ISREG(info.st_mode):
        raise OSError(f"{description} is not a regular file")
    # Windows may update ctime during read-only access.
    return (
        info.st_dev,
        info.st_ino,
        stat.S_IFMT(info.st_mode),
        info.st_size,
        info.st_mtime_ns,
    )


def _verify_output_parent(
    parent: Path,
    identity: tuple[int, int, int],
) -> None:
    try:
        info = parent.lstat()
        resolved = parent.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ValueError("Bundle output parent cannot be re-verified safely") from error
    if (
        _is_link_or_reparse_point(info)
        or not stat.S_ISDIR(info.st_mode)
        or _directory_identity(info) != identity
        or resolved != parent
    ):
        raise ValueError("Bundle output parent changed after validation")


def _canonical_evidence_output(
    output: Path,
    *,
    source: Path | None = None,
) -> _OutputTarget:
    """Resolve an absent evidence target without imposing a privacy location."""

    requested = Path(output).expanduser()
    if requested.suffix != ".zip":
        raise ValueError("Evidence output must have an explicit .zip suffix")
    try:
        requested_parent = requested.parent.lstat()
        physical_parent = requested.parent.resolve(strict=True)
        physical_info = physical_parent.lstat()
    except (OSError, RuntimeError) as error:
        raise ValueError(
            "Evidence output parent must be an existing directory"
        ) from error
    if (
        _is_link_or_reparse_point(requested_parent)
        or not stat.S_ISDIR(requested_parent.st_mode)
        or _is_link_or_reparse_point(physical_info)
        or not stat.S_ISDIR(physical_info.st_mode)
    ):
        raise ValueError(
            "Evidence output parent must be an existing non-link directory"
        )
    physical_output = physical_parent / requested.name
    if source is not None:
        try:
            physical_source = Path(source).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise ValueError("Evidence source cannot be resolved safely") from error
        if physical_output == physical_source:
            raise ValueError("Evidence output must differ from the selected source")
    if os.path.lexists(requested) or os.path.lexists(physical_output):
        raise FileExistsError(f"Evidence output already exists: {requested}")
    return _OutputTarget(
        output=physical_output,
        parent_identity=_directory_identity(physical_info),
    )


def _supports_anchored_publication() -> bool:
    return (
        os.name != "nt"
        and os.open in os.supports_dir_fd
        and os.link in os.supports_dir_fd
        and os.unlink in os.supports_dir_fd
        and hasattr(os, "O_DIRECTORY")
    )


def _open_output_directory(
    parent: Path,
    identity: tuple[int, int, int],
) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(parent, flags)
    except OSError as error:
        raise ValueError(
            "Bundle output parent cannot be opened safely"
        ) from error
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(info.st_mode)
            or _directory_identity(info) != identity
        ):
            raise ValueError(
                "Bundle output parent changed while being opened"
            )
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _create_anchored_temp(
    parent_fd: int,
    output_name: str,
) -> tuple[int, str]:
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
    for _ in range(32):
        name = f".{output_name}.{secrets.token_hex(16)}.tmp"
        try:
            return os.open(name, flags, 0o666, dir_fd=parent_fd), name
        except FileExistsError:
            continue
    raise OSError("Could not allocate a unique bundle staging filename")


def _publish_anchored_without_overwrite(
    parent_fd: int,
    temp_name: str,
    output_name: str,
) -> None:
    try:
        os.link(
            temp_name,
            output_name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
            follow_symlinks=False,
        )
    except FileExistsError:
        raise FileExistsError(f"Bundle output already exists: {output_name}")
    except OSError as error:
        if error.errno == errno.EEXIST:
            raise FileExistsError(
                f"Bundle output already exists: {output_name}"
            ) from error
        raise
    finally:
        try:
            os.unlink(temp_name, dir_fd=parent_fd)
        except OSError:
            pass


def _publish_without_overwrite(temp_path: Path, output: Path) -> None:
    try:
        if os.name == "nt":
            os.rename(temp_path, output)
        else:
            os.link(temp_path, output)
    except FileExistsError:
        raise FileExistsError(f"Bundle output already exists: {output}")
    except OSError as error:
        if error.errno == errno.EEXIST:
            raise FileExistsError(
                f"Bundle output already exists: {output}"
            ) from error
        raise
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass


def _create_fallback_temp(parent: Path, output_name: str) -> tuple[int, Path]:
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
    for _ in range(32):
        candidate = parent / f".{output_name}.{secrets.token_hex(16)}.tmp"
        try:
            return os.open(candidate, flags, 0o666), candidate
        except FileExistsError:
            continue
    raise OSError("Could not allocate a unique archive staging filename")


def _publish_output(
    target: _OutputTarget,
    writer: Callable[[BinaryIO], object],
) -> None:
    """Write and atomically publish one absent-target archive."""

    parent = target.output.parent
    temp_path: Path | None = None
    temp_name: str | None = None
    parent_fd: int | None = None
    staging_fd: int | None = None
    staging_identity: tuple[int, int, int, int, int] | None = None
    try:
        _verify_output_parent(
            parent,
            target.parent_identity,
        )
        if _supports_anchored_publication():
            parent_fd = _open_output_directory(
                parent,
                target.parent_identity,
            )
            staging_fd, temp_name = _create_anchored_temp(
                parent_fd,
                target.output.name,
            )
        else:
            staging_fd, temp_path = _create_fallback_temp(
                parent,
                target.output.name,
            )
        with os.fdopen(staging_fd, "w+b") as archive_stream:
            staging_fd = None
            writer(archive_stream)
            archive_stream.flush()
            os.fsync(archive_stream.fileno())
            staging_identity = _regular_file_identity(
                os.fstat(archive_stream.fileno()),
                description="Archive staging file",
            )

        _verify_output_parent(
            parent,
            target.parent_identity,
        )
        if parent_fd is not None:
            assert temp_name is not None
            _publish_anchored_without_overwrite(
                parent_fd,
                temp_name,
                target.output.name,
            )
            temp_name = None
            published = os.stat(
                target.output.name,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
        else:
            assert temp_path is not None
            _publish_without_overwrite(temp_path, target.output)
            temp_path = None
            published = target.output.lstat()
        if _regular_file_identity(
            published,
            description="Published archive",
        ) != staging_identity:
            raise SvcError(
                "bundle-output-mutated",
                "Archive output changed during atomic publication.",
            )
    finally:
        if staging_fd is not None:
            try:
                os.close(staging_fd)
            except OSError:
                pass
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass
        if parent_fd is not None:
            if temp_name is not None:
                try:
                    os.unlink(temp_name, dir_fd=parent_fd)
                except OSError:
                    pass
            os.close(parent_fd)


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


def normalize_agent_thread_evidence(
    provider: EvidenceThreadProvider,
    context: ProviderContext,
    selection: ThreadSelection,
) -> ValidatedEvidence:
    """Collect schema-v3 evidence ephemerally without publication."""

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
            )
        )
        return validate_evidence_members(
            manifest,
            native_bytes,
            native_index,
            trajectory_bytes,
        )
    except (TrajectoryError, EvidenceError) as error:
        raise SvcError(error.code, error.message) from error
    finally:
        native.close()
        trajectory.close()


def write_agent_thread_evidence(
    provider: EvidenceThreadProvider,
    context: ProviderContext,
    selection: ThreadSelection,
    output: Path,
) -> dict[str, Any]:
    """Capture and atomically publish one schema-v3 evidence archive."""

    resolved = provider.resolve(context, selection)
    target = _canonical_evidence_output(output, source=resolved.source_path)
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
    "normalize_agent_thread_evidence",
    "write_agent_thread_evidence",
]
