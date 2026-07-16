"""Provider-neutral ZIP publication for explicit agent-thread captures."""

from __future__ import annotations

from dataclasses import dataclass
import errno
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import stat
import tempfile
import zipfile

from ..errors import SvcError
from ..release import runtime_version
from .agent_threads import (
    ARCHIVE_SCHEMA_VERSION,
    CaptureEvidence,
    ProviderContext,
    SourceSnapshot,
    ThreadProvider,
    ThreadSelection,
)
from .task_packets import TaskPacketEnumeration, copy_packet_file, discover_task_packet_roots, iter_packet_files


_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


@dataclass(frozen=True)
class _OutputTarget:
    repository: Path
    output: Path
    parent_identity: tuple[int, int, int]


def _safe_component(value: str, label: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or path.is_absolute()
        or len(path.parts) != 1
        or path.parts[0] in (".", "..")
    ):
        raise ValueError(f"{label} must be a single safe path component")
    if path.as_posix() != value or "/" in value or "\\" in value:
        raise ValueError(f"{label} must be a single safe path component")
    return value


def _is_link_or_reparse_point(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        (getattr(info, "st_file_attributes", 0) or 0) & _FILE_ATTRIBUTE_REPARSE_POINT
    )


def _directory_identity(info: os.stat_result) -> tuple[int, int, int]:
    return (info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode))


def _verify_output_parent(parent: Path, identity: tuple[int, int, int], repository: Path) -> None:
    """Reject a changed, linked, or repository-local output directory."""
    try:
        info = parent.lstat()
        resolved = parent.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"Archive output parent cannot be re-verified safely: {exc}") from exc
    if (
        _is_link_or_reparse_point(info)
        or not stat.S_ISDIR(info.st_mode)
        or _directory_identity(info) != identity
        or resolved != parent
    ):
        raise ValueError("Archive output parent changed after validation")
    try:
        parent.relative_to(repository)
    except ValueError:
        return
    raise ValueError("Archive output must be outside the repository so it cannot alter task-packet evidence")


def _entry_info(name: str) -> zipfile.ZipInfo:
    # Fixed ZIP metadata avoids platform-specific timestamps and permissions.
    # The manifest intentionally carries the evidence capture time.
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (0o600 & 0xFFFF) << 16
    return info


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _evidence_dict(evidence: CaptureEvidence) -> dict[str, object]:
    return {
        "source_sha256": evidence.source_sha256,
        "source_bytes": evidence.source_bytes,
        "record_counts": dict(sorted(evidence.record_counts.items())),
        "capabilities": dict(sorted(evidence.capabilities.items())),
        "warnings": [warning.as_dict() for warning in evidence.warnings],
    }


def _publish_without_overwrite(temp_path: Path, output: Path) -> None:
    """Publish an absent target without replacing an existing destination."""
    try:
        if os.name == "nt":
            # Windows `rename` refuses an existing destination and does not
            # require hard-link support from the output filesystem.
            os.rename(temp_path, output)
        else:
            os.link(temp_path, output)
    except FileExistsError:
        raise FileExistsError(f"Archive output already exists: {output}")
    except OSError as exc:
        # Some filesystems report an existing target as EEXIST rather than the
        # Python-specific exception.  Preserve the no-overwrite invariant.
        if exc.errno == errno.EEXIST:
            raise FileExistsError(f"Archive output already exists: {output}") from exc
        raise
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass


def _regular_file_identity(info: os.stat_result, *, description: str) -> tuple[int, int, int]:
    if _is_link_or_reparse_point(info) or not stat.S_ISREG(info.st_mode):
        raise OSError(f"{description} is not a regular file")
    return (info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode))


def _published_identity(path: Path) -> tuple[int, int, int]:
    return _regular_file_identity(path.lstat(), description=f"Published archive {path}")


def _supports_anchored_publication() -> bool:
    return (
        os.name != "nt"
        and os.open in os.supports_dir_fd
        and os.link in os.supports_dir_fd
        and os.unlink in os.supports_dir_fd
        and hasattr(os, "O_DIRECTORY")
    )


def _open_output_directory(parent: Path, identity: tuple[int, int, int]) -> int:
    """Open a POSIX directory handle bound to the validated physical parent."""
    flags = os.O_RDONLY | os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(parent, flags)
    except OSError as exc:
        raise ValueError(f"Archive output parent cannot be opened safely: {exc}") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISDIR(info.st_mode) or _directory_identity(info) != identity:
            raise ValueError("Archive output parent changed while being opened")
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _create_anchored_temp(parent_fd: int, output_name: str) -> tuple[int, str]:
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
    for _ in range(32):
        name = f".{output_name}.{secrets.token_hex(16)}.tmp"
        try:
            return os.open(name, flags, 0o600, dir_fd=parent_fd), name
        except FileExistsError:
            continue
    raise OSError("Could not allocate a unique archive staging filename")


def _anchored_published_identity(parent_fd: int, output_name: str) -> tuple[int, int, int]:
    info = os.stat(output_name, dir_fd=parent_fd, follow_symlinks=False)
    return _regular_file_identity(info, description=f"Published archive {output_name}")


def _publish_anchored_without_overwrite(parent_fd: int, temp_name: str, output_name: str) -> None:
    """Hard-link within an opened POSIX directory, immune to path redirection."""
    try:
        os.link(
            temp_name,
            output_name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
            follow_symlinks=False,
        )
    except FileExistsError:
        raise FileExistsError(f"Archive output already exists: {output_name}")
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            raise FileExistsError(f"Archive output already exists: {output_name}") from exc
        raise
    finally:
        try:
            os.unlink(temp_name, dir_fd=parent_fd)
        except OSError:
            pass


def _source_signature(info: os.stat_result) -> SourceSnapshot:
    return SourceSnapshot(
        device=info.st_dev,
        inode=info.st_ino,
        size=info.st_size,
        mtime_ns=info.st_mtime_ns,
    )


def _validate_evidence(evidence: CaptureEvidence) -> None:
    """Reject invalid static-provider output before it can shape a ZIP manifest."""
    if (
        not isinstance(evidence.source_sha256, str)
        or len(evidence.source_sha256) != 64
        or any(character not in "0123456789abcdef" for character in evidence.source_sha256)
    ):
        raise ValueError("provider returned an invalid source SHA-256")
    if isinstance(evidence.source_bytes, bool) or not isinstance(evidence.source_bytes, int) or evidence.source_bytes < 0:
        raise ValueError("provider returned an invalid source byte count")
    for record_type, count in evidence.record_counts.items():
        if (
            not isinstance(record_type, str)
            or not record_type
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
        ):
            raise ValueError("provider returned an invalid record count")
    for capability, state in evidence.capabilities.items():
        if not isinstance(capability, str) or not capability or not isinstance(state, str) or not state:
            raise ValueError("provider returned an invalid capability declaration")
    if evidence.source_snapshot is not None:
        snapshot = evidence.source_snapshot
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (snapshot.device, snapshot.inode, snapshot.size, snapshot.mtime_ns)
        ):
            raise ValueError("provider returned an invalid source snapshot")


def _verify_captured_source(resolved_path: Path, evidence: CaptureEvidence) -> None:
    """Prove that the raw ZIP member is still a stable native source snapshot.

    Providers verify during their own read.  This final check closes the
    capture-to-publication window while the archive core is discovering and
    copying optional task-packet material.
    """
    source = Path(resolved_path).expanduser()
    try:
        before = source.lstat()
    except OSError as exc:
        raise SvcError(
            "thread-source-mutated",
            "The native thread source disappeared before archive publication.",
            {"path": str(source)},
        ) from exc
    if _is_link_or_reparse_point(before) or not stat.S_ISREG(before.st_mode):
        raise SvcError(
            "thread-source-mutated",
            "The native thread source is no longer a regular non-symlink file.",
            {"path": str(source)},
        )
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        fd = os.open(source, flags)
    except OSError as exc:
        raise SvcError(
            "thread-source-mutated",
            "The native thread source cannot be safely re-verified before publication.",
            {"path": str(source)},
        ) from exc
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or _source_signature(opened) != _source_signature(before):
            raise SvcError(
                "thread-source-mutated",
                "The native thread source changed while being re-verified.",
                {"path": str(source)},
            )
        digest = hashlib.sha256()
        total = 0
        with os.fdopen(fd, "rb") as stream:
            fd = -1
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                total += len(chunk)
            final = os.fstat(stream.fileno())
        try:
            after = source.lstat()
        except OSError as exc:
            raise SvcError(
                "thread-source-mutated",
                "The native thread source disappeared during re-verification.",
                {"path": str(source)},
            ) from exc
        if (
            _source_signature(opened) != _source_signature(final)
            or _source_signature(before) != _source_signature(after)
        ):
            raise SvcError(
                "thread-source-mutated",
                "The native thread source changed during re-verification.",
                {"path": str(source)},
            )
        if total != evidence.source_bytes or digest.hexdigest() != evidence.source_sha256:
            raise SvcError(
                "thread-source-mutated",
                "The native thread source no longer matches the captured archive evidence.",
                {"path": str(source)},
            )
        if evidence.source_snapshot is not None and _source_signature(final) != evidence.source_snapshot:
            raise SvcError(
                "thread-source-mutated",
                "The native thread source no longer has the captured filesystem identity.",
                {"path": str(source)},
            )
    finally:
        if fd != -1:
            os.close(fd)


def _canonical_repository_and_output(repository: Path, output: Path) -> _OutputTarget:
    """Resolve physical paths and reject ZIP output that would mutate the repo."""
    requested_repository = Path(repository).expanduser()
    requested_output = Path(output).expanduser()
    if requested_output.suffix != ".zip":
        raise ValueError("Archive output must have an explicit .zip suffix")
    if not requested_repository.exists() or not requested_repository.is_dir():
        raise ValueError("Repository must be an existing directory")
    try:
        requested_parent_info = requested_output.parent.lstat()
    except OSError as exc:
        raise ValueError("Archive output parent must be an existing directory") from exc
    if _is_link_or_reparse_point(requested_parent_info) or not stat.S_ISDIR(requested_parent_info.st_mode):
        raise ValueError("Archive output parent must be an existing non-link directory")
    try:
        physical_repository = requested_repository.resolve(strict=True)
        physical_parent = requested_output.parent.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"Repository or archive output parent cannot be resolved safely: {exc}") from exc
    try:
        physical_parent_info = physical_parent.lstat()
    except OSError as exc:
        raise ValueError("Archive output parent cannot be inspected safely") from exc
    if (
        not physical_repository.is_dir()
        or _is_link_or_reparse_point(physical_parent_info)
        or not stat.S_ISDIR(physical_parent_info.st_mode)
    ):
        raise ValueError("Repository and archive output parent must resolve to directories")
    physical_output = physical_parent / requested_output.name
    if os.path.lexists(requested_output) or os.path.lexists(physical_output):
        raise FileExistsError(f"Archive output already exists: {requested_output}")
    try:
        physical_output.relative_to(physical_repository)
    except ValueError:
        return _OutputTarget(
            repository=physical_repository,
            output=physical_output,
            parent_identity=_directory_identity(physical_parent_info),
        )
    raise ValueError("Archive output must be outside the repository so it cannot alter task-packet evidence")


def write_agent_thread_archive(
    provider: ThreadProvider,
    context: ProviderContext,
    selection: ThreadSelection,
    repository: Path,
    output: Path,
) -> dict[str, object]:
    """Capture one exact provider thread and atomically publish a local ZIP.

    The provider owns source resolution and parsing.  This function owns only
    archive layout, task-packet association, manifest construction, and safe
    publication.  It returns the same JSON-ready manifest written to the ZIP.
    """
    target = _canonical_repository_and_output(repository, output)
    repository, output = target.repository, target.output
    parent = output.parent

    provider_id = _safe_component(provider.provider_id, "provider_id")
    resolved = provider.resolve(context, selection)
    if resolved.provider_id != provider_id:
        raise ValueError("Resolved thread provider_id does not match provider")
    artifact_path = resolved.artifact.archive_path
    # SourceArtifact validates lexical normalization; this additional check
    # protects third-party implementations that bypass its constructor.
    artifact_parts = PurePosixPath(artifact_path).parts
    if (
        not artifact_parts
        or any(ord(character) < 32 or ord(character) == 127 for character in artifact_path)
        or artifact_path.startswith("/")
        or "\\" in artifact_path
        or ".." in artifact_parts
    ):
        raise ValueError("Resolved artifact archive path is unsafe")
    raw_name = f"providers/{provider_id}/{artifact_path}"

    temp_path: Path | None = None
    temp_name: str | None = None
    parent_fd: int | None = None
    staging_fd: int | None = None
    staging_identity: tuple[int, int, int] | None = None
    try:
        _verify_output_parent(parent, target.parent_identity, repository)
        if _supports_anchored_publication():
            parent_fd = _open_output_directory(parent, target.parent_identity)
            staging_fd, temp_name = _create_anchored_temp(parent_fd, output.name)
        else:
            staging_fd, fallback_name = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp", dir=parent)
            temp_path = Path(fallback_name)
        if os.name != "nt":
            os.fchmod(staging_fd, 0o600)
        staging_identity = _regular_file_identity(
            os.fstat(staging_fd), description="Archive staging file"
        )
        temp_file = os.fdopen(staging_fd, "w+b")
        staging_fd = None
        with temp_file:
            with zipfile.ZipFile(temp_file, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
                # Provider sinks are spooled independently because zipfile
                # permits only one open write handle at a time.  They remain
                # bounded-memory for large native artifacts.
                with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b") as raw_output:
                    with tempfile.SpooledTemporaryFile(max_size=1 * 1024 * 1024, mode="w+b") as index_output:
                        evidence = provider.stream_capture(resolved, raw_output, index_output)
                        raw_output.seek(0)
                        index_output.seek(0)
                        for entry_name, source in ((raw_name, raw_output), ("thread/index.json", index_output)):
                            with archive.open(_entry_info(entry_name), mode="w") as destination:
                                while True:
                                    chunk = source.read(1024 * 1024)
                                    if not chunk:
                                        break
                                    destination.write(chunk)

                if not isinstance(evidence, CaptureEvidence):
                    raise TypeError("provider.stream_capture must return CaptureEvidence")
                _validate_evidence(evidence)

                discovery = discover_task_packet_roots(repository, evidence.occurrences)
                task_entries: dict[str, tuple[Path, str, int]] = {}
                task_warnings = list(discovery.warnings)
                tasks_root = repository / "tasks"
                manifest_packets: list[dict[str, object]] = []
                packet_enumerations: list[TaskPacketEnumeration] = []
                for root in discovery.roots:
                    packet_manifest = root.as_dict()
                    packet_files_manifest: list[dict[str, object]] = []
                    try:
                        packet_files = iter_packet_files(root.root, tasks_root)
                    except (OSError, ValueError) as exc:
                        task_warnings.append({"code": "task_packet_read_error", "details": {"path": root.lexical_path, "error": str(exc)}})
                        packet_manifest["files"] = packet_files_manifest
                        manifest_packets.append(packet_manifest)
                        continue
                    packet_enumerations.append(packet_files)
                    for packet_file in packet_files:
                        entry_name = packet_file.archive_path
                        existing = task_entries.get(entry_name)
                        if existing is not None:
                            existing_source, digest, byte_count = existing
                            if existing_source != packet_file.source_path:
                                raise SvcError(
                                    "task-packet-archive-collision",
                                    "Two task-packet members resolve to the same archive path.",
                                    {
                                        "packet": root.lexical_path,
                                        "archive_path": entry_name,
                                    },
                                )
                            packet_files_manifest.append(
                                {
                                    "archive_path": entry_name,
                                    "sha256": digest,
                                    "bytes": byte_count,
                                    "shared": True,
                                }
                            )
                            continue
                        try:
                            # Validate and snapshot the member before creating
                            # its ZIP entry.  A failed read therefore cannot
                            # leave an unreferenced partial member in a
                            # publishable archive.
                            with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b") as packet_snapshot:
                                digest, byte_count = copy_packet_file(packet_file, tasks_root, packet_snapshot)
                                packet_snapshot.seek(0)
                                with archive.open(_entry_info(entry_name), mode="w") as destination:
                                    while True:
                                        chunk = packet_snapshot.read(1024 * 1024)
                                        if not chunk:
                                            break
                                        destination.write(chunk)
                        except (OSError, ValueError) as exc:
                            raise SvcError(
                                "task-packet-mutated",
                                "A selected task packet changed while it was being archived.",
                                {
                                    "packet": root.lexical_path,
                                    "member": str(packet_file.source_path),
                                },
                            ) from exc
                        task_entries[entry_name] = (packet_file.source_path, digest, byte_count)
                        packet_files_manifest.append(
                            {
                                "archive_path": entry_name,
                                "sha256": digest,
                                "bytes": byte_count,
                            }
                        )
                    try:
                        packet_files.verify(tasks_root)
                    except (OSError, ValueError) as exc:
                        raise SvcError(
                            "task-packet-mutated",
                            "A selected task packet changed while it was being archived.",
                            {"packet": root.lexical_path},
                        ) from exc
                    packet_manifest["files"] = packet_files_manifest
                    manifest_packets.append(packet_manifest)

                evidence_dict = _evidence_dict(evidence)
                warning_values = list(evidence_dict.pop("warnings", [])) + task_warnings
                manifest: dict[str, object] = {
                    "schema_version": ARCHIVE_SCHEMA_VERSION,
                    "exporter": {"name": "svc", "version": runtime_version()},
                    "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "provider": {
                        "id": resolved.provider_id,
                        "adapter_id": resolved.adapter_id,
                        "source_format": resolved.source_format,
                    },
                    "thread": {
                        "id": resolved.thread_id,
                        "source_state": resolved.source_state,
                    },
                    "artifact": {
                        "archive_path": raw_name,
                        "media_type": resolved.artifact.media_type,
                        "sha256": evidence.source_sha256,
                        "bytes": evidence.source_bytes,
                    },
                    **evidence_dict,
                    "warnings": warning_values,
                    "task_packets": manifest_packets,
                }
                archive.writestr(_entry_info("manifest.json"), _json_bytes(manifest))
            temp_file.flush()
            os.fsync(temp_file.fileno())
        # The archive is a snapshot.  Validate its mutable evidence inputs at
        # the atomic-commit boundary, after all ZIP serialization and fsync.
        # Changes after publication cannot alter the already hash-bound ZIP.
        _verify_output_parent(parent, target.parent_identity, repository)
        _verify_captured_source(resolved.artifact.source_path, evidence)
        for packet_files in packet_enumerations:
            try:
                packet_files.verify(tasks_root)
            except (OSError, ValueError) as exc:
                raise SvcError(
                    "task-packet-mutated",
                    "A selected task packet changed before archive publication.",
                ) from exc
        _verify_output_parent(parent, target.parent_identity, repository)
        if parent_fd is not None:
            assert temp_name is not None
            _publish_anchored_without_overwrite(parent_fd, temp_name, output.name)
            temp_name = None
            try:
                published_identity = _anchored_published_identity(parent_fd, output.name)
            except OSError as exc:
                raise SvcError(
                    "archive-output-mutated",
                    "Archive output changed during atomic publication and is not trusted.",
                    {"output": str(output)},
                ) from exc
        else:
            assert temp_path is not None
            _publish_without_overwrite(temp_path, output)
            temp_path = None
            try:
                published_identity = _published_identity(output)
            except OSError as exc:
                raise SvcError(
                    "archive-output-mutated",
                    "Archive output changed during atomic publication and is not trusted.",
                    {"output": str(output)},
                ) from exc
        if staging_identity != published_identity:
            raise SvcError(
                "archive-output-mutated",
                "Archive output changed during atomic publication and is not trusted.",
                {"output": str(output)},
            )
        return manifest
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
            try:
                os.close(parent_fd)
            except OSError:
                pass
