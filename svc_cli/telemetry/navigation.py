"""Pure, bounded models for the sensitive agent-thread navigator.

This module deliberately has no UI, provider, or filesystem dependency.  It
turns a bounded provider projection into an immutable lexical tree snapshot;
the Textual adapter can then decide when to materialize a node without making
the widget a source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
import re
import unicodedata
from typing import Iterable, Iterator

from .agent_threads import (
    ArchiveFilter,
    ArchiveState,
    MAX_FIRST_MESSAGE_CHARS,
    MAX_INTERACTIVE_ROWS,
    MAX_TITLE_CHARS,
    MAX_WORKSPACE_CHARS,
    SensitiveInventoryListing,
    SensitiveInventoryQuery,
    SensitiveInventoryRow,
    SourceAvailability,
    ThreadRef,
)


_CONTROL_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:[\\/]")
_SEPARATOR = re.compile(r"[\\/]+")


class WorkspaceFlavor(StrEnum):
    """Lexical path flavor; this is never a claim about the host filesystem."""

    POSIX = "posix"
    WINDOWS_DRIVE = "windows-drive"
    WINDOWS_UNC = "windows-unc"
    RELATIVE = "relative"
    TRUNCATED = "truncated"
    UNKNOWN = "unknown"


class NavigationNodeKind(StrEnum):
    """Kinds in the provider/workspace/lifecycle/thread tree."""

    PROVIDER = "provider"
    WORKSPACE = "workspace"
    LIFECYCLE = "lifecycle"
    THREAD = "thread"


def _has_forbidden_control(value: str) -> bool:
    return any(unicodedata.category(character) in _CONTROL_CATEGORIES for character in value)


def _utf8(value: str, *, field_name: str) -> bytes:
    try:
        return value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{field_name} must be representable UTF-8 text") from error


def _coerce_archive_filter(value: ArchiveFilter | str) -> ArchiveFilter:
    try:
        return ArchiveFilter(value)
    except (TypeError, ValueError) as error:
        raise ValueError("archive_filter must be active, archived, or all") from error


SelectionRef = ThreadRef


@dataclass(frozen=True, slots=True)
class WorkspacePath:
    """A lexical workspace path decomposition with no host lookup."""

    flavor: WorkspaceFlavor
    root: str
    components: tuple[str, ...]
    raw: str | None = field(default=None, repr=False)

    @property
    def is_known(self) -> bool:
        return self.flavor not in {WorkspaceFlavor.UNKNOWN, WorkspaceFlavor.TRUNCATED}

    @property
    def tree_parts(self) -> tuple[str, ...]:
        if self.flavor is WorkspaceFlavor.UNKNOWN:
            return ("<unknown workspace>",)
        if self.flavor is WorkspaceFlavor.TRUNCATED:
            return ("<truncated workspace>",)
        return (self.root, *self.components)

    @property
    def group_key(self) -> tuple[str, ...]:
        return (self.flavor.value, self.root, *self.components)

    def __repr__(self) -> str:
        return f"WorkspacePath(flavor={self.flavor.value!r}, component_count={len(self.components)})"


def parse_workspace(value: str | None, *, truncated: bool = False) -> WorkspacePath:
    """Parse a workspace lexically; never resolve, stat, or walk it."""

    if truncated or (isinstance(value, str) and len(value) > MAX_WORKSPACE_CHARS):
        return WorkspacePath(WorkspaceFlavor.TRUNCATED, "<truncated workspace>", (), None)
    if value is None or not isinstance(value, str) or not value or _has_forbidden_control(value):
        return WorkspacePath(WorkspaceFlavor.UNKNOWN, "<unknown workspace>", (), None)
    _utf8(value, field_name="workspace")

    if _DRIVE_PREFIX.match(value):
        root = value[:2]
        components = tuple(part for part in _SEPARATOR.split(value[2:]) if part)
        return WorkspacePath(WorkspaceFlavor.WINDOWS_DRIVE, root, components, value)

    if value.startswith(("\\\\", "//")):
        pieces = tuple(part for part in _SEPARATOR.split(value[2:]) if part)
        if len(pieces) < 2:
            return WorkspacePath(WorkspaceFlavor.UNKNOWN, "<unknown workspace>", (), None)
        root = "\\\\" + pieces[0] + "\\" + pieces[1]
        return WorkspacePath(WorkspaceFlavor.WINDOWS_UNC, root, pieces[2:], value)

    if value.startswith("/"):
        components = tuple(part for part in value.split("/") if part)
        return WorkspacePath(WorkspaceFlavor.POSIX, "/", components, value)

    components = tuple(part for part in _SEPARATOR.split(value) if part)
    if not components:
        return WorkspacePath(WorkspaceFlavor.UNKNOWN, "<unknown workspace>", (), None)
    return WorkspacePath(WorkspaceFlavor.RELATIVE, "<relative>", components, value)


def workspace_path(row: SensitiveInventoryRow) -> WorkspacePath:
    return parse_workspace(row.workspace, truncated=row.workspace_truncated)


def escape_control_text(value: str | None) -> str:
    """Escape terminal-affecting Unicode code points for painting only."""

    if value is None:
        return ""
    if not isinstance(value, str):
        return ""
    return "".join(
        f"\\u{{{ord(character):04X}}}"
        if unicodedata.category(character) in _CONTROL_CATEGORIES
        else character
        for character in value
    )


visible_text = escape_control_text


def _recognition_base(row: SensitiveInventoryRow) -> tuple[str, str]:
    title = row.title if row.title is not None else "<missing title>"
    message = row.first_user_message if row.first_user_message is not None else "<no first user message>"
    return title, message


def recognition_label(
    row: SensitiveInventoryRow,
    *,
    duplicate_index: int | None = None,
) -> str:
    """Build a bounded recognition label without changing the stored fields."""

    title, message = _recognition_base(row)
    title_marker = " [truncated]" if row.title_truncated else ""
    message_marker = (
        " [truncated]" if row.first_user_message_truncated else ""
    )
    # Both values are primary recognition evidence, even when the title is
    # unique.
    label = (
        f"{title}{title_marker} — "
        f"{message}{message_marker}"
    )
    if duplicate_index is not None and duplicate_index > 1:
        label = f"{label} ({duplicate_index})"
    return label


@dataclass(frozen=True, slots=True)
class NavigationNode:
    """Immutable render-neutral tree node."""

    kind: NavigationNodeKind
    key: tuple[str, ...]
    label: str = field(repr=False)
    children: tuple["NavigationNode", ...] = field(default_factory=tuple, repr=False)
    selection: SelectionRef | None = field(default=None, repr=False)
    row: SensitiveInventoryRow | None = field(default=None, repr=False)
    disabled: bool = False

    @property
    def expandable(self) -> bool:
        return bool(self.children) or self.kind is not NavigationNodeKind.THREAD

    def iter_leaves(self) -> Iterator["NavigationNode"]:
        if self.kind is NavigationNodeKind.THREAD:
            yield self
            return
        for child in self.children:
            yield from child.iter_leaves()

    def __repr__(self) -> str:
        return f"NavigationNode(kind={self.kind.value!r}, child_count={len(self.children)}, disabled={self.disabled})"


@dataclass(frozen=True, slots=True)
class NavigationSnapshot:
    """Bounded immutable provider/workspace/lifecycle/thread tree."""

    roots: tuple[NavigationNode, ...]
    rows: tuple[SensitiveInventoryRow, ...]
    archive_state: ArchiveFilter
    inventory_truncated: bool = False
    omitted_sources: int = 0

    def contains(self, selection: SelectionRef | None) -> bool:
        if selection is None:
            return False
        return any(row.selection == selection for row in self.rows)

    def find(self, selection: SelectionRef) -> NavigationNode | None:
        for root in self.roots:
            for leaf in root.iter_leaves():
                if leaf.selection == selection:
                    return leaf
        return None

    def iter_leaves(self) -> Iterator[NavigationNode]:
        # Tree siblings retain their lexical grouping order, while callers
        # that consume the bounded flat projection retain the provider's
        # global recency/thread-ID order.
        leaves = {
            leaf.selection: leaf
            for root in self.roots
            for leaf in root.iter_leaves()
            if leaf.selection is not None
        }
        for row in self.rows:
            leaf = leaves.get(row.selection)
            if leaf is not None:
                yield leaf

    def __repr__(self) -> str:
        return (
            f"NavigationSnapshot(root_count={len(self.roots)}, row_count={len(self.rows)}, "
            f"archive_state={self.archive_state.value!r}, inventory_truncated={self.inventory_truncated})"
        )


class _MutableNode:
    __slots__ = ("kind", "key", "label", "children", "selection", "row", "disabled", "order")

    def __init__(
        self,
        kind: NavigationNodeKind,
        key: tuple[str, ...],
        label: str,
        *,
        selection: SelectionRef | None = None,
        row: SensitiveInventoryRow | None = None,
        disabled: bool = False,
        order: int = 0,
    ) -> None:
        self.kind = kind
        self.key = key
        self.label = label
        self.children: dict[tuple[str, ...], _MutableNode] = {}
        self.selection = selection
        self.row = row
        self.disabled = disabled
        self.order = order

    def child(
        self,
        key: tuple[str, ...],
        kind: NavigationNodeKind,
        label: str,
        *,
        selection: SelectionRef | None = None,
        row: SensitiveInventoryRow | None = None,
        disabled: bool = False,
        order: int = 0,
    ) -> "_MutableNode":
        current = self.children.get(key)
        if current is None:
            current = _MutableNode(
                kind,
                key,
                label,
                selection=selection,
                row=row,
                disabled=disabled,
                order=order,
            )
            self.children[key] = current
        return current


def _component_order(node: _MutableNode) -> tuple[int, bytes, int]:
    if node.kind is NavigationNodeKind.WORKSPACE:
        # Valid lexical paths sort bytewise across host path flavors. The two
        # synthetic provenance groups are always after real paths so a
        # Windows drive/UNC root cannot be displaced by an ASCII ``<``.
        flavor = node.key[1] if len(node.key) > 1 else ""
        if flavor == WorkspaceFlavor.TRUNCATED.value:
            workspace_rank = 1
        elif flavor == WorkspaceFlavor.UNKNOWN.value:
            workspace_rank = 2
        else:
            workspace_rank = 0
        return (
            workspace_rank,
            _utf8(node.label, field_name="workspace label"),
            0,
        )
    if node.kind is NavigationNodeKind.LIFECYCLE:
        lifecycle_order = {ArchiveState.ACTIVE.value: 0, ArchiveState.ARCHIVED.value: 1, ArchiveState.UNKNOWN.value: 2}
        return (1, b"", lifecycle_order.get(node.label.lower(), 3))
    return (2, b"", node.order)


def _freeze_node(node: _MutableNode) -> NavigationNode:
    children = tuple(_freeze_node(child) for child in sorted(node.children.values(), key=_component_order))
    return NavigationNode(
        kind=node.kind,
        key=node.key,
        label=node.label,
        children=children,
        selection=node.selection,
        row=node.row,
        disabled=node.disabled,
    )


def build_navigation_snapshot(
    rows: Iterable[SensitiveInventoryRow] | SensitiveInventoryListing,
    *,
    archive_state: ArchiveFilter | str = ArchiveFilter.ACTIVE,
    limit: int = MAX_INTERACTIVE_ROWS,
) -> NavigationSnapshot:
    """Build a deterministic bounded tree from the sensitive projection."""

    selected_filter = _coerce_archive_filter(archive_state)
    if isinstance(rows, SensitiveInventoryListing):
        listing = SensitiveInventoryListing.from_rows(
            rows.items,
            archive_state=selected_filter,
            limit=limit,
            omitted_sources=rows.omitted_sources,
        )
        truncated = rows.inventory_truncated or listing.inventory_truncated
    else:
        listing = SensitiveInventoryListing.from_rows(rows, archive_state=selected_filter, limit=limit)
        truncated = listing.inventory_truncated

    ordered_rows = listing.items
    duplicate_counts: dict[tuple[str, tuple[str, ...], str], int] = {}
    pair_counts: dict[tuple[str, tuple[str, ...], str, str], int] = {}
    parsed_paths: dict[SelectionRef, WorkspacePath] = {}
    for row in ordered_rows:
        path = workspace_path(row)
        parsed_paths[row.selection] = path
        title = row.title or "<missing title>"
        title_key = (row.provider_id, path.group_key, title)
        pair_key = (*title_key, row.first_user_message or "<no first user message>")
        duplicate_counts[title_key] = duplicate_counts.get(title_key, 0) + 1
        pair_counts[pair_key] = pair_counts.get(pair_key, 0) + 1

    pair_seen: dict[tuple[str, tuple[str, ...], str, str], int] = {}
    providers: dict[tuple[str, ...], _MutableNode] = {}
    for index, row in enumerate(ordered_rows):
        provider_key = ("provider", row.provider_id)
        provider = providers.get(provider_key)
        if provider is None:
            provider = _MutableNode(NavigationNodeKind.PROVIDER, provider_key, row.provider_id)
            providers[provider_key] = provider

        path = parsed_paths[row.selection]
        parent = provider
        path_prefix: list[str] = []
        for part_index, part in enumerate(path.tree_parts):
            path_prefix.append(part)
            workspace_key = ("workspace", path.flavor.value, path.root, *path_prefix)
            parent = parent.child(workspace_key, NavigationNodeKind.WORKSPACE, part)

        lifecycle = ArchiveState(row.archive_state).value
        lifecycle_key = (*parent.key, "lifecycle", lifecycle)
        lifecycle_node = parent.child(lifecycle_key, NavigationNodeKind.LIFECYCLE, lifecycle)
        title = row.title or "<missing title>"
        title_key = (row.provider_id, path.group_key, title)
        pair_key = (*title_key, row.first_user_message or "<no first user message>")
        duplicate_index: int | None = None
        if duplicate_counts[title_key] > 1 or row.title is None:
            pair_seen[pair_key] = pair_seen.get(pair_key, 0) + 1
            if pair_counts[pair_key] > 1:
                duplicate_index = pair_seen[pair_key]
        label = recognition_label(
            row,
            duplicate_index=duplicate_index,
        )
        thread_key = (*lifecycle_node.key, "thread", row.provider_id, row.thread_id)
        lifecycle_node.child(
            thread_key,
            NavigationNodeKind.THREAD,
            label,
            selection=row.selection,
            row=row,
            disabled=not row.analyzable,
            order=index,
        )

    roots = tuple(_freeze_node(node) for node in sorted(providers.values(), key=lambda node: _utf8(node.label, field_name="provider label")))
    return NavigationSnapshot(
        roots=roots,
        rows=ordered_rows,
        archive_state=selected_filter,
        inventory_truncated=truncated,
        omitted_sources=listing.omitted_sources,
    )


@dataclass(frozen=True, slots=True)
class LoadGeneration:
    """Opaque token returned to a caller that started a load transition."""

    value: int
    archive_state: ArchiveFilter


@dataclass(frozen=True, slots=True)
class NavigationState:
    """Immutable externally visible controller state."""

    archive_state: ArchiveFilter = ArchiveFilter.ACTIVE
    generation: int = 0
    loading: bool = False
    selected: SelectionRef | None = field(default=None, repr=False)
    snapshot: NavigationSnapshot | None = field(default=None, repr=False)

    def __repr__(self) -> str:
        return (
            f"NavigationState(archive_state={self.archive_state.value!r}, generation={self.generation}, "
            f"loading={self.loading}, selected={self.selected is not None}, "
            f"has_snapshot={self.snapshot is not None})"
        )


class NavigationController:
    """Generation and selection gate for async provider/UI transitions."""

    __slots__ = ("_state",)

    def __init__(self, archive_state: ArchiveFilter | str = ArchiveFilter.ACTIVE) -> None:
        self._state = NavigationState(archive_state=_coerce_archive_filter(archive_state))

    @property
    def state(self) -> NavigationState:
        return self._state

    def begin_load(self, archive_state: ArchiveFilter | str | None = None) -> LoadGeneration:
        selected_filter = self._state.archive_state if archive_state is None else _coerce_archive_filter(archive_state)
        generation = self._state.generation + 1
        self._state = replace(self._state, archive_state=selected_filter, generation=generation, loading=True)
        return LoadGeneration(generation, selected_filter)

    # Short alias useful to adapters that call filter transitions explicitly.
    begin_filter = begin_load

    def is_current(self, token: LoadGeneration) -> bool:
        return token.value == self._state.generation and token.archive_state == self._state.archive_state

    def accept(self, token: LoadGeneration, snapshot: NavigationSnapshot) -> bool:
        if not self.is_current(token):
            return False
        selected = self._state.selected if snapshot.contains(self._state.selected) else None
        self._state = replace(self._state, loading=False, snapshot=snapshot, selected=selected)
        return True

    def reject(self, token: LoadGeneration) -> bool:
        if not self.is_current(token):
            return False
        self._state = replace(self._state, loading=False)
        return True

    def select(self, selection: SelectionRef | None) -> bool:
        if selection is None:
            self._state = replace(self._state, selected=None)
            return True
        if self._state.snapshot is None or not self._state.snapshot.contains(selection):
            return False
        self._state = replace(self._state, selected=selection)
        return True


__all__ = [
    "ArchiveFilter",
    "ArchiveState",
    "LoadGeneration",
    "MAX_FIRST_MESSAGE_CHARS",
    "MAX_INTERACTIVE_ROWS",
    "MAX_TITLE_CHARS",
    "MAX_WORKSPACE_CHARS",
    "NavigationController",
    "NavigationNode",
    "NavigationNodeKind",
    "NavigationSnapshot",
    "NavigationState",
    "SensitiveInventoryListing",
    "SensitiveInventoryQuery",
    "SensitiveInventoryRow",
    "SelectionRef",
    "SourceAvailability",
    "ThreadRef",
    "WorkspaceFlavor",
    "WorkspacePath",
    "build_navigation_snapshot",
    "escape_control_text",
    "parse_workspace",
    "recognition_label",
    "visible_text",
    "workspace_path",
]
