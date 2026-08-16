"""Bounded task-packet initialization and read-only growth inspection.

The task packet is deliberately a local control surface.  ``init`` knows only
how to establish that surface; ``grow`` reports the shape that is already on
disk and leaves all semantic admission to the Agent.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import re

from .errors import SvcError
from .resources import read_document


TASKS_DIRECTORY = "tasks"
TASK_PACKET_FILENAME = "packet.md"
TASK_PACKET_GUIDANCE_PATH = "task-packet/index.md"
TASK_PACKET_GROWTH_PATH = "task-packet/growth.md"
TASK_PACKET_TEMPLATE_INDEX_PATH = "templates/task-packet/index.md"
TASK_PACKET_TEMPLATE_PATH = "templates/task-packet/packet.template.md"

_MAX_INVENTORY_ENTRIES = 100
_MAX_INVENTORY_DIRECTORY_LEVELS = 2
_STABLE_ROOT_ENTRIES = frozenset(
    {
        TASK_PACKET_FILENAME,
        "plan.md",
        "task-map.md",
        "inquiry.md",
        "design.md",
        "decisions.md",
        "verification.md",
    }
)
_TRACK_OR_PHASE_RE = re.compile(r"^(?:track|phase)-[^/]+\.md$")


@dataclass(frozen=True)
class TaskPacket:
    """One validated task-local packet address."""

    root: Path
    task_id: str
    path: Path


@dataclass(frozen=True)
class _InventoryEntry:
    """One bounded path observation, with no file-content interpretation."""

    relative_path: str
    kind: str
    recognized: bool


def init_task_packet(repo: Path, task_id: str) -> TaskPacket:
    """Create one absent packet from the packaged template without replacement."""

    packet = locate_task_packet(repo, task_id)
    # Resolve the no-overwrite decision before touching the packaged resource;
    # an existing packet must remain protected even if a template is absent.
    if packet.path.is_symlink() or packet.path.exists():
        raise SvcError(
            "task-packet-exists",
            "Task packet already exists and was not replaced.",
            {"path": str(packet.path)},
        )
    _validate_existing_task_parents(packet)
    content = _packet_template(task_id)
    _ensure_packet_parent(packet)
    try:
        with packet.path.open("xb") as destination:
            destination.write(content)
    except FileExistsError as error:
        raise SvcError(
            "task-packet-exists",
            "Task packet already exists and was not replaced.",
            {"path": str(packet.path)},
        ) from error
    except OSError as error:
        raise SvcError(
            "task-packet-write-failed",
            "Could not create the task packet.",
            {"path": str(packet.path), "reason": str(error)},
        ) from error
    return packet


def grow_task_packet(repo: Path, task_id: str) -> bytes:
    """Return a bounded, read-only brief for one existing packet."""

    packet = locate_task_packet(repo, task_id)
    _validate_existing_task_parents(packet)
    _require_existing_packet(packet)
    try:
        inventory, truncated = _inventory(packet.path.parent)
    except OSError as error:
        raise SvcError(
            "task-packet-inventory-failed",
            "Could not inspect the task packet directory without changing it.",
            {"path": str(packet.path.parent), "reason": str(error)},
        ) from error
    return _render_growth_brief(packet, inventory, truncated)


def locate_task_packet(repo: Path, task_id: str) -> TaskPacket:
    """Return the only permitted packet address for a normalized task ID."""

    root = _require_repo(repo)
    parts = _task_id_parts(task_id)
    tasks_root = root / TASKS_DIRECTORY
    packet_path = tasks_root.joinpath(*parts, TASK_PACKET_FILENAME)
    _assert_within_tasks(tasks_root, packet_path, task_id)
    return TaskPacket(root=root, task_id=task_id, path=packet_path)


def _require_repo(repo: Path) -> Path:
    root = repo.resolve()
    if not root.is_dir():
        raise SvcError(
            "repo-not-directory",
            "Project root is not a directory.",
            {"repo": str(repo)},
        )
    return root


def _task_id_parts(task_id: str) -> tuple[str, ...]:
    path = PurePosixPath(task_id)
    if (
        not task_id
        or "\\" in task_id
        or "\x00" in task_id
        or "\n" in task_id
        or "\r" in task_id
        or path.is_absolute()
        or "." in path.parts
        or ".." in path.parts
        or path.as_posix() != task_id
    ):
        raise SvcError(
            "invalid-task-id",
            "Task ID must be a non-empty normalized relative path inside tasks/.",
            {"task_id": task_id},
        )
    return path.parts


def _assert_within_tasks(tasks_root: Path, packet_path: Path, task_id: str) -> None:
    try:
        packet_path.resolve(strict=False).relative_to(tasks_root)
    except ValueError as error:
        raise SvcError(
            "invalid-task-id",
            "Task ID must resolve inside the repository tasks/ directory.",
            {"task_id": task_id},
        ) from error


def _packet_template(task_id: str) -> bytes:
    try:
        template = read_document(TASK_PACKET_TEMPLATE_PATH)
    except FileNotFoundError as error:
        raise SvcError(
            "task-packet-template-unavailable",
            "Packaged task-packet template is unavailable.",
            {"path": TASK_PACKET_TEMPLATE_PATH},
        ) from error
    placeholder = b"# <Task>"
    if placeholder not in template:
        raise SvcError(
            "task-packet-template-invalid",
            "Packaged task-packet template does not contain its task placeholder.",
            {"path": TASK_PACKET_TEMPLATE_PATH},
        )
    return template.replace(placeholder, f"# {task_id}".encode("utf-8"), 1)


def _ensure_packet_parent(packet: TaskPacket) -> None:
    tasks_root = packet.root / TASKS_DIRECTORY
    directory = tasks_root
    for part in PurePosixPath(packet.task_id).parts:
        _ensure_directory(directory, packet)
        directory = directory / part
    _ensure_directory(directory, packet)
    _assert_within_tasks(tasks_root, packet.path, packet.task_id)


def _ensure_directory(directory: Path, packet: TaskPacket) -> None:
    try:
        directory.mkdir(exist_ok=True)
    except OSError as error:
        raise SvcError(
            "task-packet-parent-unavailable",
            "Task packet parent directory cannot be created.",
            {"path": str(directory), "reason": str(error)},
        ) from error
    if directory.is_symlink() or not directory.is_dir():
        raise SvcError(
            "task-packet-parent-unsafe",
            "Task packet parent must be a real directory inside tasks/.",
            {"path": str(directory), "task_id": packet.task_id},
        )


def _require_existing_packet(packet: TaskPacket) -> None:
    if packet.path.is_symlink() or not packet.path.is_file():
        raise SvcError(
            "task-packet-not-found",
            "Task packet does not exist as a regular file.",
            {"path": str(packet.path)},
        )


def _validate_existing_task_parents(packet: TaskPacket) -> None:
    """Reject symlink/non-directory parents before a read-only traversal.

    ``Path.is_file`` follows a symlink, so checking only ``packet.path`` would
    allow a packet reached through a symlinked task directory.  Missing parents
    are left to ``_require_existing_packet`` so a normal absent packet keeps
    its useful not-found diagnostic.
    """

    current = packet.root / TASKS_DIRECTORY
    for part in PurePosixPath(packet.task_id).parts:
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            raise SvcError(
                "task-packet-parent-unsafe",
                "Task packet parent must be a real directory inside tasks/.",
                {"path": str(current), "task_id": packet.task_id},
            )
        if not current.exists():
            return
        current = current / part
    if current.is_symlink() or (current.exists() and not current.is_dir()):
        raise SvcError(
            "task-packet-parent-unsafe",
            "Task packet parent must be a real directory inside tasks/.",
            {"path": str(current), "task_id": packet.task_id},
        )


def _inventory(root: Path) -> tuple[tuple[_InventoryEntry, ...], bool]:
    """Observe at most 100 paths across two levels without following symlinks."""

    # ``packet.md`` is the universal Human entry, so it must remain visible
    # even when the surrounding directory exceeds the observation budget.
    paths: list[tuple[str, str]] = [(TASK_PACKET_FILENAME, "regular file")]

    def visit_once(
        directory: Path, relative_directory: str, directory_level: int
    ) -> bool:
        child_directories: list[os.DirEntry[str]] = []
        with os.scandir(directory) as iterator:
            for entry in iterator:
                relative = (
                    f"{relative_directory}/{entry.name}"
                    if relative_directory
                    else entry.name
                )
                if relative == TASK_PACKET_FILENAME:
                    continue
                if len(paths) >= _MAX_INVENTORY_ENTRIES:
                    return True
                paths.append((relative, _entry_kind(entry)))
                if entry.is_dir(follow_symlinks=False):
                    child_directories.append(entry)
            if directory_level >= _MAX_INVENTORY_DIRECTORY_LEVELS:
                return False
        for entry in sorted(child_directories, key=lambda item: item.name):
            child_relative = (
                f"{relative_directory}/{entry.name}"
                if relative_directory
                else entry.name
            )
            if visit_once(
                directory / entry.name, child_relative, directory_level + 1
            ):
                return True
        return False

    truncated = visit_once(root, "", 0)
    paths.sort(key=lambda item: item[0])
    recognized_bases = _recognized_bases(paths)
    inventory = tuple(
        _InventoryEntry(
            relative_path=relative,
            kind=kind,
            recognized=_is_recognized(relative, recognized_bases),
        )
        for relative, kind in paths
    )
    return inventory, truncated


def _recognized_bases(paths: list[tuple[str, str]]) -> frozenset[str]:
    """Return stable addresses which can own same-stem supporting depth."""

    root_names = {
        relative
        for relative, kind in paths
        if "/" not in relative
        and _is_recognizable_kind(kind)
        and _is_stable_root_name(relative)
    }
    cell_names = {
        relative
        for relative, kind in paths
        if relative.startswith("cells/")
        and relative.count("/") == 1
        and _is_recognizable_kind(kind)
        and PurePosixPath(relative).suffix == ".md"
        and PurePosixPath(relative).name != ""
    }
    return frozenset((*root_names, *cell_names))


def _is_recognized(relative: str, recognized_bases: frozenset[str]) -> bool:
    if relative == "cells":
        return True
    if relative in recognized_bases:
        return True
    for base in recognized_bases:
        if base == TASK_PACKET_FILENAME:
            continue
        stem = PurePosixPath(base).with_suffix("").as_posix()
        if relative == stem or relative.startswith(f"{stem}/"):
            return True
    if relative.startswith("cells/"):
        cell_entry, _, remainder = relative.partition("/")
        if cell_entry in recognized_bases:
            return True
        # ``cells/<entry>/...`` is supporting depth only when the stable Cell
        # entry exists; unknown cells remain report-only.
        cell_stem = cell_entry
        return any(
            base == f"cells/{cell_stem}.md"
            for base in recognized_bases
        ) and bool(remainder)
    return False


def _is_stable_root_name(relative: str) -> bool:
    name = PurePosixPath(relative).name
    return name in _STABLE_ROOT_ENTRIES or bool(_TRACK_OR_PHASE_RE.fullmatch(name))


def _is_recognizable_kind(kind: str) -> bool:
    return kind in {"regular file", "symlink (not followed)"}


def _entry_kind(entry: os.DirEntry[str]) -> str:
    if entry.is_symlink():
        return "symlink (not followed)"
    if entry.is_dir(follow_symlinks=False):
        return "directory"
    if entry.is_file(follow_symlinks=False):
        return "regular file"
    return "non-regular"


def _render_growth_brief(
    packet: TaskPacket,
    inventory: tuple[_InventoryEntry, ...],
    truncated: bool,
) -> bytes:
    recognized = tuple(item for item in inventory if item.recognized)
    unknown = tuple(item for item in inventory if not item.recognized)
    lines = [
        "Task packet growth brief",
        f"Packet: {packet.path}",
        "",
        "Observed inventory (sample sorted by relative path; maximum two directory levels; maximum 100 entries):",
    ]
    if inventory:
        lines.extend(
            f"  {item.relative_path} [{item.kind}]" for item in inventory
        )
    else:
        lines.append("  (empty)")
    if truncated:
        lines.append(
            "Inventory truncated: yes "
            f"(showing {len(inventory)} entries; at least "
            f"{len(inventory) + 1} exist; scan stopped at the observation limit)."
        )
    else:
        lines.append(
            f"Inventory truncated: no ({len(inventory)} entries; limit 100)."
        )
    lines.extend(("", "Recognized packet entries:"))
    if recognized:
        lines.extend(f"  {item.relative_path}" for item in recognized)
    else:
        lines.append("  (none)")
    lines.extend(("", "Unrecognized entries (reported only):"))
    if unknown:
        lines.extend(f"  {item.relative_path}" for item in unknown)
    else:
        lines.append("  (none)")
    lines.extend(
        (
            "",
            "Work-topology questions:",
            "  Is the task still one compact Plan, or has Track/Phase topology been semantically admitted?",
            "  If topology is admitted, which real Track/Phase Plan owners or Cells and integration returns exist now?",
            "  Does any same-stem supporting depth have an independent consumer and return, or should it remain inline?",
            "",
            "Information-topology questions:",
            "  Does an Inquiry, Design, Decision, or Verification concern now have a distinct owner, consumer, and return?",
            "  Are current synthesis, evidence/freshness, authority, or reopen conditions getting lost in the owner entry?",
            "  Which supporting artifact has useful content now, and what precise owner should receive its return?",
            "",
            f"Guidance: {TASK_PACKET_GUIDANCE_PATH}",
            f"Growth guidance: {TASK_PACKET_GROWTH_PATH}",
            f"Template family: {TASK_PACKET_TEMPLATE_INDEX_PATH}",
            f"Packet template: {TASK_PACKET_TEMPLATE_PATH}",
            "",
            "Semantic boundary:",
            "  No semantic decision was made from filenames, file size, or Agent count.",
            "  No file was changed; this command is read-only.",
            "  The Agent must perform any coherent shape edit and update packet.md returns.",
        )
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


__all__ = [
    "TASK_PACKET_GUIDANCE_PATH",
    "TASK_PACKET_GROWTH_PATH",
    "TASK_PACKET_TEMPLATE_INDEX_PATH",
    "TASK_PACKET_TEMPLATE_PATH",
    "TaskPacket",
    "grow_task_packet",
    "init_task_packet",
    "locate_task_packet",
]
