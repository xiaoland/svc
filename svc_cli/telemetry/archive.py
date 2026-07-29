"""Safe publication of normalized agent-thread bundles."""

from __future__ import annotations

from dataclasses import dataclass
import errno
from io import BytesIO
import os
from pathlib import Path
import secrets
import stat
import tempfile
from typing import BinaryIO, Mapping

from ..errors import SvcError
from ..release import runtime_version
from .agent_threads import (
    NormalizationResult,
    NormalizationStatus,
    ProviderContext,
    ThreadProvider,
    ThreadSelection,
)
from .trajectory import (
    DEFAULT_NORMALIZATION_POLICY,
    TrajectoryCollector,
    TrajectoryError,
    ValidatedBundle,
    build_manifest,
    policy_dict,
    validate_trajectory_bytes,
    write_bundle_stream,
)


_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


@dataclass(frozen=True)
class _OutputTarget:
    repository: Path
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
    repository: Path,
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
    try:
        parent.relative_to(repository)
    except ValueError:
        return
    raise ValueError(
        "Bundle output must remain outside the repository"
    )


def _canonical_repository_and_output(
    repository: Path,
    output: Path,
) -> _OutputTarget:
    requested_repository = Path(repository).expanduser()
    requested_output = Path(output).expanduser()
    if requested_output.suffix != ".zip":
        raise ValueError("Bundle output must have an explicit .zip suffix")
    if not requested_repository.exists() or not requested_repository.is_dir():
        raise ValueError("Repository must be an existing directory")
    try:
        requested_parent_info = requested_output.parent.lstat()
    except OSError as error:
        raise ValueError(
            "Bundle output parent must be an existing directory"
        ) from error
    if _is_link_or_reparse_point(requested_parent_info) or not stat.S_ISDIR(
        requested_parent_info.st_mode
    ):
        raise ValueError(
            "Bundle output parent must be an existing non-link directory"
        )
    try:
        physical_repository = requested_repository.resolve(strict=True)
        physical_parent = requested_output.parent.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ValueError(
            "Repository or bundle output parent cannot be resolved safely"
        ) from error
    physical_parent_info = physical_parent.lstat()
    if (
        not physical_repository.is_dir()
        or _is_link_or_reparse_point(physical_parent_info)
        or not stat.S_ISDIR(physical_parent_info.st_mode)
    ):
        raise ValueError(
            "Repository and bundle output parent must resolve to directories"
        )
    physical_output = physical_parent / requested_output.name
    if os.path.lexists(requested_output) or os.path.lexists(physical_output):
        raise FileExistsError(f"Bundle output already exists: {requested_output}")
    try:
        physical_output.relative_to(physical_repository)
    except ValueError:
        return _OutputTarget(
            repository=physical_repository,
            output=physical_output,
            parent_identity=_directory_identity(physical_parent_info),
        )
    raise ValueError(
        "Bundle output must remain outside the repository"
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
            return os.open(name, flags, 0o600, dir_fd=parent_fd), name
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


def _diagnostic_sort_key(
    diagnostic: Mapping[str, object],
) -> tuple[tuple[int, int, int, int], bytes, bytes]:
    source = diagnostic.get("source_ref")
    missing = 2**63 - 1
    coordinates = tuple(
        (
            source.get(key, missing)
            if isinstance(source, Mapping)
            and isinstance(source.get(key, missing), int)
            else missing
        )
        for key in ("event_index", "line", "byte_offset", "component_index")
    )
    from .trajectory import canonical_json_bytes

    return (
        coordinates,  # type: ignore[arg-type]
        str(diagnostic.get("code", "")).encode("ascii"),
        canonical_json_bytes(diagnostic.get("details", {})),
    )


def _finalize_normalization(
    result: NormalizationResult,
    collector: TrajectoryCollector,
    *,
    diagnostic_limit: int = DEFAULT_NORMALIZATION_POLICY.diagnostics,
) -> tuple[dict[str, object], dict[str, dict[str, int]], list[dict[str, object]], str]:
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
    status = result.result_status.value
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


def _normalize_to_stream(
    provider: ThreadProvider,
    context: ProviderContext,
    selection: ThreadSelection,
    trajectory_stream: BinaryIO,
) -> dict[str, object]:
    """Run the one shared normalizer into a caller-owned bounded stream."""

    resolved = provider.resolve(context, selection)
    if resolved.provider_id != provider.provider_id:
        raise ValueError(
            "Resolved thread provider_id does not match provider"
        )

    collector = TrajectoryCollector(trajectory_stream)
    bounds = policy_dict()["bounds"]
    assert isinstance(bounds, Mapping)
    result = provider.stream_normalize(
        resolved,
        collector.emit,
        bounds,
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
    source = {
        "provider_id": result.provider_id,
        "adapter_id": result.adapter_id,
        "source_format": result.source_format,
        "thread_ref": result.thread_ref,
        "source_status": result.source_status.value,
    }
    return dict(
        build_manifest(
            trajectory_source=trajectory_stream,
            source=source,
            result_status=result_status,
            capabilities=result.capabilities,
            lossiness=lossiness,
            diagnostics=diagnostics,
            counts=counts,
            exporter_version=runtime_version(),
        )
    )


def normalize_agent_thread(
    provider: ThreadProvider,
    context: ProviderContext,
    selection: ThreadSelection,
) -> ValidatedBundle:
    """Normalize an explicit local source ephemerally without publication."""

    stream = BytesIO()
    try:
        manifest = _normalize_to_stream(
            provider,
            context,
            selection,
            stream,
        )
        trajectory = validate_trajectory_bytes(stream.getvalue())
        return ValidatedBundle(
            manifest=manifest,
            trajectory=trajectory,
            bundle_id=str(manifest["bundle_id"]),
            path=None,
        )
    except TrajectoryError as error:
        raise SvcError(error.code, error.message) from error
    finally:
        stream.close()


def write_agent_thread_bundle(
    provider: ThreadProvider,
    context: ProviderContext,
    selection: ThreadSelection,
    repository: Path,
    output: Path,
) -> dict[str, object]:
    """Normalize one exact local source and atomically publish schema v2."""

    target = _canonical_repository_and_output(repository, output)
    parent = target.output.parent

    trajectory_temp = tempfile.SpooledTemporaryFile(
        max_size=1024 * 1024,
        mode="w+b",
    )
    temp_path: Path | None = None
    temp_name: str | None = None
    parent_fd: int | None = None
    staging_fd: int | None = None
    staging_identity: tuple[int, int, int, int, int] | None = None
    try:
        manifest = _normalize_to_stream(
            provider,
            context,
            selection,
            trajectory_temp,
        )

        _verify_output_parent(
            parent,
            target.parent_identity,
            target.repository,
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
            staging_fd, fallback_name = tempfile.mkstemp(
                prefix=f".{target.output.name}.",
                suffix=".tmp",
                dir=parent,
            )
            temp_path = Path(fallback_name)
        if os.name != "nt":
            os.fchmod(staging_fd, 0o600)
        with os.fdopen(staging_fd, "w+b") as bundle_stream:
            staging_fd = None
            trajectory_temp.seek(0)
            write_bundle_stream(bundle_stream, manifest, trajectory_temp)
            bundle_stream.flush()
            os.fsync(bundle_stream.fileno())
            staging_identity = _regular_file_identity(
                os.fstat(bundle_stream.fileno()),
                description="Bundle staging file",
            )

        _verify_output_parent(
            parent,
            target.parent_identity,
            target.repository,
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
        published_identity = _regular_file_identity(
            published,
            description="Published bundle",
        )
        if published_identity != staging_identity:
            raise SvcError(
                "bundle-output-mutated",
                "Bundle output changed during atomic publication.",
            )
        return manifest
    except TrajectoryError as error:
        raise SvcError(error.code, error.message) from error
    finally:
        trajectory_temp.close()
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


__all__ = [
    "normalize_agent_thread",
    "write_agent_thread_bundle",
]
