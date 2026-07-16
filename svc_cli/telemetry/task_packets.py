"""Safe, lexical association of task-packet material with a capture.

This module deliberately does not inspect provider data.  Callers pass the
``TextOccurrence`` values returned by a provider and those values are the only
source used to discover task packet paths.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import BinaryIO, Iterable, Iterator

from .agent_threads import TextOccurrence


_TASK_PATH_RE = re.compile(r"(?<![\w./-])/?tasks/[^\s\x00<>\"'`\[\]{}()\\]+", re.UNICODE)
_TRAILING_PUNCTUATION = ".,;:!?)]}>\"'。！？；：）】》」』、"
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
_WINDOWS_INVALID_COMPONENT = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED_DEVICE = re.compile(
    r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$", re.IGNORECASE
)


@dataclass(frozen=True)
class TaskPacketRoot:
    """One physical packet root and all message occurrence provenance."""

    root: Path
    lexical_path: str
    provenance: tuple[dict[str, object], ...]

    @property
    def archive_root(self) -> str:
        return f"task-packets/{self.lexical_path}"

    def as_dict(self) -> dict[str, object]:
        return {
            "root": self.lexical_path,
            "archive_root": self.archive_root,
            "occurrences": list(self.provenance),
        }


@dataclass(frozen=True)
class TaskPacketDiscovery:
    roots: tuple[TaskPacketRoot, ...]
    warnings: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class TaskPacketFile:
    """A regular packet file to be copied by the archive core without buffering it."""

    source_path: Path
    archive_path: str
    tasks_root_identity: tuple[int, int, int]
    file_identity: tuple[int, ...]

    @property
    def stat_identity(self) -> tuple[int, ...]:
        """Compatibility name for callers that describe the field as stat identity."""
        return self.file_identity


@dataclass(frozen=True)
class TaskPacketEnumeration:
    """A packet file enumeration and its immutable tree snapshot.

    ``archive`` can iterate this object exactly as it iterated the old tuple
    return value, then call :meth:`verify` immediately before publication.  A
    verification failure means that a member was added, removed, replaced,
    or that a directory in the packet tree changed after enumeration.
    """

    root: Path
    tasks_root_identity: tuple[int, int, int]
    root_identity: tuple[int, int, int]
    files: tuple[TaskPacketFile, ...]
    tree_identity: tuple[tuple[str, tuple[int, ...]], ...]

    def __iter__(self) -> Iterator[TaskPacketFile]:
        return iter(self.files)

    def __len__(self) -> int:
        return len(self.files)

    def verify(self, tasks_root: Path) -> None:
        stable_tasks_root, tasks_root_identity = _stable_tasks_root(Path(tasks_root))
        if tasks_root_identity != self.tasks_root_identity:
            raise ValueError("Task packet directory changed after file enumeration")
        try:
            lexical_root_info = self.root.lstat()
        except OSError as exc:
            raise ValueError("Task packet root changed after file enumeration") from exc
        if _unsafe_link_info(lexical_root_info):
            raise ValueError("Task packet root changed after file enumeration")
        try:
            root = self.root.resolve(strict=True)
            root.relative_to(stable_tasks_root)
        except (OSError, ValueError) as exc:
            raise ValueError("Task packet root changed after file enumeration") from exc
        try:
            root_info = root.lstat()
        except OSError as exc:
            raise ValueError(f"Task packet root cannot be inspected: {root}: {exc}") from exc
        if _unsafe_link_info(root_info) or not stat.S_ISDIR(root_info.st_mode):
            raise ValueError("Task packet root changed after file enumeration")
        current_root_identity, current_tree = _tree_snapshot(root)
        if current_root_identity != self.root_identity or current_tree != dict(self.tree_identity):
            raise ValueError("Task packet tree changed after file enumeration")


def _warning(code: str, **details: object) -> dict[str, object]:
    return {"code": code, "details": details}


def _unsafe_link_info(info: object) -> bool:
    """Return true for symlinks and Windows junction/reparse points.

    ``st_file_attributes`` is present on Windows ``stat_result`` and may be
    supplied by platform fixtures.  Keeping this check attribute-based makes
    the policy work on Python 3.11 without importing Windows-only modules.
    """
    mode = getattr(info, "st_mode", 0)
    attributes = getattr(info, "st_file_attributes", 0) or 0
    return stat.S_ISLNK(mode) or bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT)


def _valid_lexical_path(path: PurePosixPath) -> bool:
    """Apply Windows lexical restrictions on every platform.

    Task references are portable archive inputs.  Rejecting names that cannot
    be represented safely on Windows also prevents platform-specific OSError
    from escaping discovery on a Windows host.
    """
    for part in path.parts:
        if part in ("tasks", ".", ".."):
            continue
        if _WINDOWS_INVALID_COMPONENT.search(part):
            return False
        if part.endswith((".", " ")):
            return False
        if _WINDOWS_RESERVED_DEVICE.fullmatch(part):
            return False
    return True


def _lexical_paths(occurrences: Iterable[TextOccurrence]) -> Iterable[tuple[str, TextOccurrence]]:
    for occurrence in occurrences:
        for match in _TASK_PATH_RE.finditer(occurrence.text):
            raw = match.group(0)
            # ``:`` and ``?`` are invalid Windows path characters, not merely
            # sentence punctuation, when they terminate a task component.
            value = raw if raw.endswith((":", "?")) else raw.rstrip(_TRAILING_PUNCTUATION)
            if value:
                yield value, occurrence


def _normal_relative(value: str) -> PurePosixPath | None:
    """Return a safe lexical path, rejecting traversal and absolute forms."""
    if not value or value.startswith("/") or "\\" in value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or path.parts[0:1] != ("tasks",):
        return None
    if any(part in ("", ".", "..") for part in path.parts):
        return None
    if not _valid_lexical_path(path):
        return None
    return path


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _path_has_symlink(tasks_root: Path, relative: PurePosixPath) -> bool:
    current = tasks_root
    for part in relative.parts[1:]:
        current = current / part
        try:
            if _unsafe_link_info(current.lstat()):
                return True
        except (FileNotFoundError, OSError):
            return False
    return False


def _qualifying_root(candidate: Path, tasks_root: Path) -> tuple[Path, str] | None:
    """Find the nearest existing ancestor that is a packet (has packet.md)."""
    start = candidate if candidate.is_dir() else candidate.parent
    try:
        tasks_root_real = tasks_root.resolve(strict=False)
        current = start
        while _inside(tasks_root_real, current.resolve(strict=False)) and current != tasks_root.parent:
            # ``tasks/`` is a workspace container, never a packet root.  In
            # particular, tasks/packet.md must remain an invalid candidate.
            if current == tasks_root:
                break
            marker = current / "packet.md"
            if current.is_dir() and marker.is_file() and not _unsafe_link_info(marker.lstat()):
                relative = current.relative_to(tasks_root).as_posix()
                return current, f"tasks/{relative}"
            current = current.parent
    except OSError:
        return None
    return None


def discover_task_packet_roots(
    repository: Path, occurrences: Iterable[TextOccurrence]
) -> TaskPacketDiscovery:
    """Discover packet roots from supplied occurrence text only.

    Missing candidates and candidates that fail path/symlink validation become
    warnings.  They never prevent the native provider evidence from being
    archived.
    """
    repository = Path(repository)
    tasks_root = repository / "tasks"
    warnings: list[dict[str, object]] = []
    by_physical: dict[Path, tuple[str, list[dict[str, object]]]] = {}

    for lexical, occurrence in _lexical_paths(occurrences):
        relative = _normal_relative(lexical)
        if relative is None:
            warnings.append(_warning("task_packet_invalid_path", path=lexical, **occurrence.provenance()))
            continue

        lexical_fs = repository.joinpath(*relative.parts)
        try:
            tasks_info = tasks_root.lstat()
        except OSError as exc:
            warnings.append(_warning("task_packet_unresolvable", path=lexical, error=str(exc), **occurrence.provenance()))
            continue
        if _unsafe_link_info(tasks_info):
            warnings.append(_warning("task_packet_symlink_escape", path=lexical, **occurrence.provenance()))
            continue
        if _path_has_symlink(tasks_root, relative):
            warnings.append(_warning("task_packet_symlink_escape", path=lexical, **occurrence.provenance()))
            continue
        # Resolve without requiring existence to expose symlink escapes while
        # preserving a useful lexical path in the warning.
        try:
            resolved = lexical_fs.resolve(strict=False)
        except OSError as exc:
            warnings.append(_warning("task_packet_unresolvable", path=lexical, error=str(exc), **occurrence.provenance()))
            continue
        try:
            repository_resolved = repository.resolve(strict=True)
            tasks_resolved = tasks_root.resolve(strict=False)
        except OSError as exc:
            warnings.append(_warning("task_packet_unresolvable", path=lexical, error=str(exc), **occurrence.provenance()))
            continue
        if not _inside(repository_resolved, tasks_resolved):
            warnings.append(_warning("task_packet_symlink_escape", path=lexical, **occurrence.provenance()))
            continue
        if not _inside(tasks_resolved, resolved):
            warnings.append(_warning("task_packet_symlink_escape", path=lexical, **occurrence.provenance()))
            continue
        try:
            exists = lexical_fs.exists()
            is_dir = lexical_fs.is_dir()
            is_file = lexical_fs.is_file()
        except OSError as exc:
            warnings.append(_warning("task_packet_invalid_path", path=lexical, error=str(exc), **occurrence.provenance()))
            continue
        if not exists:
            warnings.append(_warning("task_packet_missing", path=lexical, **occurrence.provenance()))
            continue
        if not is_dir and not is_file:
            warnings.append(_warning("task_packet_invalid_candidate", path=lexical, **occurrence.provenance()))
            continue

        qualifying = _qualifying_root(lexical_fs, tasks_root)
        if qualifying is None:
            warnings.append(_warning("task_packet_invalid_candidate", path=lexical, reason="packet.md not found", **occurrence.provenance()))
            continue
        root_fs, root_lexical = qualifying

        try:
            root_real = root_fs.resolve(strict=True)
            if not _inside(tasks_resolved, root_real):
                warnings.append(_warning("task_packet_symlink_escape", path=lexical, **occurrence.provenance()))
                continue
        except OSError as exc:
            warnings.append(_warning("task_packet_unresolvable", path=lexical, error=str(exc), **occurrence.provenance()))
            continue
        provenance = occurrence.provenance()
        provenance["path"] = lexical
        existing = by_physical.get(root_real)
        if existing is None:
            by_physical[root_real] = (root_lexical, [provenance])
        else:
            # Preserve every occurrence while keeping one physical root.
            existing[1].append(provenance)

    valid_roots: list[TaskPacketRoot] = []
    for physical, value in sorted(by_physical.items(), key=lambda item: (item[1][0], str(item[0]))):
        # Symlink members are rejected rather than followed, even when their
        # target remains inside the repository.  This keeps the archive a
        # faithful copy of regular packet material only.
        try:
            members = physical.rglob("*") if physical.is_dir() else ()
            if any(_unsafe_link_info(member.lstat()) for member in members):
                warnings.append(_warning("task_packet_symlink_member", path=value[0]))
                continue
        except OSError as exc:
            warnings.append(_warning("task_packet_unresolvable", path=value[0], error=str(exc)))
            continue
        valid_roots.append(TaskPacketRoot(root=physical, lexical_path=value[0], provenance=tuple(value[1])))
    roots = tuple(valid_roots)
    return TaskPacketDiscovery(roots=roots, warnings=tuple(warnings))


def _stat_signature(info: os.stat_result) -> tuple[int, ...]:
    """Return the fields that identify a stable regular-file snapshot."""
    return (
        info.st_dev,
        info.st_ino,
        stat.S_IFMT(info.st_mode),
        info.st_size,
        info.st_mtime_ns,
        getattr(info, "st_file_attributes", 0) or 0,
    )


def _directory_identity(info: os.stat_result) -> tuple[int, int, int]:
    return (info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode))


def _stable_tasks_root(tasks_root: Path) -> tuple[Path, tuple[int, int, int]]:
    """Resolve a physical task root without losing a lexical symlink check."""
    tasks_root = Path(tasks_root)
    try:
        before = tasks_root.lstat()
    except OSError as exc:
        raise ValueError(f"Task packet directory cannot be inspected: {tasks_root}: {exc}") from exc
    if _unsafe_link_info(before) or not stat.S_ISDIR(before.st_mode):
        raise ValueError(f"Task packet directory is unsafe: {tasks_root}")
    try:
        physical = tasks_root.resolve(strict=True)
        after = tasks_root.lstat()
    except OSError as exc:
        raise ValueError(f"Task packet directory cannot be resolved safely: {tasks_root}: {exc}") from exc
    if (
        _unsafe_link_info(after)
        or not stat.S_ISDIR(after.st_mode)
        or _directory_identity(before) != _directory_identity(after)
    ):
        raise ValueError(f"Task packet directory changed while resolving: {tasks_root}")
    try:
        repository_real = tasks_root.parent.resolve(strict=True)
        physical.relative_to(repository_real)
    except (OSError, ValueError) as exc:
        raise ValueError(f"Task packet directory escapes repository: {tasks_root}") from exc
    return physical, _directory_identity(before)


def _regular_member(path: Path, *, description: str) -> os.stat_result:
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise ValueError(f"Task packet {description} disappeared: {path}") from exc
    except OSError as exc:
        raise ValueError(f"Task packet {description} cannot be inspected: {path}: {exc}") from exc
    if _unsafe_link_info(info):
        raise ValueError(f"Task packet {description} is a symlink: {path}")
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"Task packet {description} is not a regular file: {path}")
    return info


def _assert_regular_path_chain(
    tasks_root: Path,
    relative: Path,
    expected_root_identity: tuple[int, int, int] | None = None,
) -> None:
    """Reject a changed symlink component before opening a packet member."""
    try:
        root_info = tasks_root.lstat()
    except OSError as exc:
        raise ValueError(f"Task packet directory cannot be inspected: {tasks_root}: {exc}") from exc
    if (
        _unsafe_link_info(root_info)
        or not stat.S_ISDIR(root_info.st_mode)
        or (expected_root_identity is not None and _directory_identity(root_info) != expected_root_identity)
    ):
        raise ValueError(f"Task packet directory is unsafe: {tasks_root}")
    current = tasks_root
    for part in relative.parts[:-1]:
        current = current / part
        try:
            info = current.lstat()
        except OSError as exc:
            raise ValueError(f"Task packet path component cannot be inspected: {current}: {exc}") from exc
        if _unsafe_link_info(info) or not stat.S_ISDIR(info.st_mode):
            raise ValueError(f"Task packet path component is unsafe: {current}")


def _tree_snapshot(root: Path) -> tuple[tuple[int, int, int], dict[str, tuple[int, ...]]]:
    """Capture every non-root member, rejecting links and reparse points."""
    try:
        root_info = root.lstat()
    except OSError as exc:
        raise ValueError(f"Task packet root cannot be inspected: {root}: {exc}") from exc
    if _unsafe_link_info(root_info) or not stat.S_ISDIR(root_info.st_mode):
        raise ValueError(f"Task packet root is unsafe: {root}")
    snapshot: dict[str, tuple[int, ...]] = {}
    try:
        members = sorted(root.rglob("*"), key=lambda path: path.relative_to(root).as_posix())
    except OSError as exc:
        raise ValueError(f"Task packet tree cannot be enumerated: {root}: {exc}") from exc
    for member in members:
        try:
            info = member.lstat()
        except OSError as exc:
            raise ValueError(f"Unable to inspect task packet member {member}: {exc}") from exc
        if _unsafe_link_info(info):
            raise ValueError(f"Task packet member is a symlink or reparse point: {member}")
        relative = member.relative_to(root).as_posix()
        if stat.S_ISDIR(info.st_mode):
            snapshot[relative] = (1, *_directory_identity(info))
        elif stat.S_ISREG(info.st_mode):
            snapshot[relative] = (2, *_stat_signature(info))
        else:
            # Keep unsupported entries in the snapshot so their addition or
            # replacement cannot silently alter the copied tree.
            snapshot[relative] = (3, *_stat_signature(info))
    return _directory_identity(root_info), snapshot


def iter_packet_files(root: Path, tasks_root: Path) -> TaskPacketEnumeration:
    """Enumerate packet files without reading their content into memory.

    The caller must use :func:`copy_packet_file` to copy every returned entry.
    That second, descriptor-bound check makes a concurrent symlink swap or file
    replacement fail before publication instead of silently copying an
    unintended file.
    """
    root = Path(root)
    tasks_root_lexical = Path(tasks_root)
    tasks_root, tasks_root_identity = _stable_tasks_root(tasks_root_lexical)
    try:
        root_relative = root.relative_to(tasks_root_lexical)
    except ValueError:
        try:
            root_relative = root.resolve(strict=True).relative_to(tasks_root)
        except (OSError, ValueError) as exc:
            raise ValueError("Task packet root escapes repository tasks directory") from exc
    # Treat the root itself as a directory component, not just a resolved
    # target, so a concurrent in-tree symlink replacement is refused.
    _assert_regular_path_chain(tasks_root, root_relative / "packet.md", tasks_root_identity)
    root_real = root.resolve(strict=True)
    if not _inside(tasks_root, root_real):
        raise ValueError("Task packet root escapes repository tasks directory")
    try:
        root_info = root_real.lstat()
    except OSError as exc:
        raise ValueError(f"Task packet root cannot be inspected: {root_real}: {exc}") from exc
    if _unsafe_link_info(root_info) or not stat.S_ISDIR(root_info.st_mode):
        raise ValueError(f"Task packet root is unsafe: {root_real}")

    files: list[TaskPacketFile] = []
    root_identity, tree_identity = _tree_snapshot(root_real)
    for candidate in sorted(root_real.rglob("*"), key=lambda path: path.relative_to(root_real).as_posix()):
        try:
            info = candidate.lstat()
        except OSError as exc:
            raise ValueError(f"Unable to inspect task packet member {candidate}: {exc}") from exc
        if _unsafe_link_info(info):
            raise ValueError(f"Task packet member is a symlink or reparse point: {candidate}")
        if not stat.S_ISREG(info.st_mode):
            continue
        try:
            relative = candidate.relative_to(tasks_root)
        except ValueError as exc:
            raise ValueError(f"Task packet member escapes repository tasks directory: {candidate}") from exc
        _assert_regular_path_chain(tasks_root, relative, tasks_root_identity)
        files.append(
            TaskPacketFile(
                source_path=candidate,
                archive_path=f"task-packets/tasks/{relative.as_posix()}",
                tasks_root_identity=tasks_root_identity,
                file_identity=_stat_signature(info),
            )
        )
    return TaskPacketEnumeration(
        root=root_real,
        tasks_root_identity=tasks_root_identity,
        root_identity=root_identity,
        files=tuple(files),
        tree_identity=tuple(sorted(tree_identity.items())),
    )


def copy_packet_file(packet_file: TaskPacketFile, tasks_root: Path, output: BinaryIO) -> tuple[str, int]:
    """Stream one enumerated packet file with a stable-path verification.

    The archive is abandoned if the member changes during this operation.  The
    result therefore records a digest for exactly the bytes written to the ZIP,
    without retaining the packet in memory.
    """
    tasks_root, tasks_root_identity = _stable_tasks_root(Path(tasks_root))
    if tasks_root_identity != packet_file.tasks_root_identity:
        raise ValueError("Task packet directory changed after file enumeration")
    source = Path(packet_file.source_path)
    try:
        relative = source.relative_to(tasks_root)
    except ValueError as exc:
        raise ValueError(f"Task packet file escapes repository tasks directory: {source}") from exc
    _assert_regular_path_chain(tasks_root, relative, tasks_root_identity)
    before = _regular_member(source, description="file")
    if _stat_signature(before) != packet_file.file_identity:
        raise ValueError(f"Task packet file changed after enumeration: {source}")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        fd = os.open(source, flags)
    except OSError as exc:
        raise ValueError(f"Task packet file cannot be opened safely: {source}: {exc}") from exc
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or _stat_signature(opened) != packet_file.file_identity:
            raise ValueError(f"Task packet file changed while opening: {source}")
        digest = hashlib.sha256()
        total = 0
        with os.fdopen(fd, "rb") as stream:
            fd = -1
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)
                total += len(chunk)
            final = os.fstat(stream.fileno())
        after = _regular_member(source, description="file")
        if _stat_signature(opened) != _stat_signature(final) or _stat_signature(before) != _stat_signature(after):
            raise ValueError(f"Task packet file changed while copying: {source}")
        if total != opened.st_size:
            raise ValueError(f"Task packet file length changed while copying: {source}")
        return digest.hexdigest(), total
    finally:
        if fd != -1:
            os.close(fd)
