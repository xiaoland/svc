"""Human agent-thread analysis surface.

The widgets in this module are deliberately a thin adapter over the frozen
navigation and analysis models.  Provider access is supplied by callbacks;
the app never opens a source file and never treats a Textual node id as a
thread identity.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Awaitable, Callable, Mapping, TypeAlias

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Label, Static, TabbedContent, TabPane, Tree
from textual.worker import Worker, WorkerState

from .agent_threads import (
    ArchiveFilter,
    SensitiveInventoryListing,
    SensitiveInventoryRow,
    ThreadRef,
)
from .analysis import AnalysisResult
from .navigation import (
    NavigationController,
    NavigationNode,
    NavigationNodeKind,
    NavigationSnapshot,
    LoadGeneration,
    escape_control_text,
    visible_text,
    build_navigation_snapshot,
)
from .trajectory import ValidatedBundle


@dataclass(frozen=True, slots=True, repr=False)
class AnalysisDocument:
    """The only document shape accepted by the human analysis surface."""

    bundle: ValidatedBundle = field(repr=False)
    analysis: AnalysisResult = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.bundle, ValidatedBundle) or not isinstance(self.analysis, AnalysisResult):
            raise ValueError("invalid analysis document")

    def __repr__(self) -> str:
        return "AnalysisDocument(<validated>)"


InventoryLoader: TypeAlias = Callable[
    [ArchiveFilter], SensitiveInventoryListing | Awaitable[SensitiveInventoryListing]
]
AnalysisLoader: TypeAlias = Callable[
    [ThreadRef], AnalysisDocument | Awaitable[AnalysisDocument]
]


class ViewName(StrEnum):
    OVERVIEW = "overview"
    TIMELINE = "timeline"
    TOOLS = "tools"
    LANES = "lanes"
    CONTEXT = "context"
    TASKS = "tasks"
    TERMINAL = "terminal"
    LOSS = "loss"


_VIEW_NAMES = tuple(ViewName)
_VIEW_IDS = {view: view.value for view in _VIEW_NAMES}
@dataclass(frozen=True, slots=True)
class _WorkerTicket:
    kind: str
    generation: int
    archive_state: ArchiveFilter | None = None
    selection: ThreadRef | None = field(default=None, repr=False)


def _plain_text(value: object, *, limit: int = 512) -> Text:
    """Build a Rich Text object with markup parsing impossible."""

    if value is None:
        rendered = ""
    elif isinstance(value, str):
        rendered = visible_text(value)
    else:
        rendered = visible_text(str(value))
    return Text(rendered[:limit])


def _display_value(value: object, *, limit: int = 240) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return visible_text(value)[:limit]
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    except (TypeError, ValueError):
        encoded = str(type(value).__name__)
    return visible_text(encoded)[:limit]


def _error_code(error: BaseException) -> str:
    code = getattr(error, "code", None)
    if (
        isinstance(code, str)
        and code
        and code.isascii()
        and code == code.lower()
        and all(character.isalnum() or character in "-_" for character in code)
    ):
        return code[:64]
    name = type(error).__name__.lower()
    return name if name and name.isascii() else "worker-error"


class AgentThreadAnalysisApp(App[None]):
    """Interactive selector plus bounded human analysis views."""

    CSS = """
    Screen { layout: vertical; }
    #body { height: 1fr; layout: horizontal; }
    #inventory-panel { width: 34%; min-width: 20; border: solid $panel; }
    #analysis-panel { width: 66%; min-width: 24; }
    #inventory-tree { height: 1fr; }
    #analysis-status { height: auto; min-height: 2; padding: 0 1; }
    #analysis-tabs { height: 1fr; }
    #analysis-tabs TabPane { padding: 0 1; overflow-y: auto; }
    #status { height: 1; padding: 0 1; }
    """

    BINDINGS = [
        Binding("a", "filter_active", "Active"),
        Binding("r", "filter_archived", "Archived"),
        Binding("l", "filter_all", "All"),
        Binding("enter", "open_analysis", "Analyze", priority=True),
        Binding("c", "cancel_work", "Cancel"),
        Binding("f", "toggle_step_filter", "Step filter"),
        Binding("j", "jump_significant", "Jump"),
        Binding("1", "view_overview", "Overview"),
        Binding("2", "view_timeline", "Timeline"),
        Binding("3", "view_tools", "Tools"),
        Binding("4", "view_lanes", "Lanes"),
        Binding("5", "view_context", "Context"),
        Binding("6", "view_tasks", "Tasks"),
        Binding("7", "view_terminal", "Terminal"),
        Binding("8", "view_loss", "Loss"),
        Binding("escape", "quit", "Quit", priority=True),
        Binding("q", "quit", "Quit", priority=True),
    ]

    def __init__(
        self,
        *,
        inventory_loader: InventoryLoader | None = None,
        analysis_loader: AnalysisLoader | None = None,
        archive_state: ArchiveFilter | str = ArchiveFilter.ACTIVE,
        initial_selection: ThreadRef | None = None,
        initial_document: AnalysisDocument | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        try:
            selected_filter = ArchiveFilter(archive_state)
        except (TypeError, ValueError) as error:
            raise ValueError("archive_state must be active, archived, or all") from error
        if initial_document is not None:
            if inventory_loader is not None or analysis_loader is not None or initial_selection is not None:
                raise ValueError("initial_document cannot be combined with loaders or selection")
            if not isinstance(initial_document, AnalysisDocument):
                raise ValueError("initial_document must be an AnalysisDocument")
        elif not callable(inventory_loader) or not callable(analysis_loader):
            raise ValueError("inventory_loader and analysis_loader are required")
        if initial_selection is not None and not isinstance(initial_selection, ThreadRef):
            raise ValueError("initial_selection must be a ThreadRef")
        self.inventory_loader = inventory_loader
        self.analysis_loader = analysis_loader
        self.navigation = NavigationController(selected_filter)
        self.selected_ref: ThreadRef | None = initial_selection
        self.selection_result: ThreadRef | None = initial_selection
        self._initial_document = initial_document
        self._snapshot: NavigationSnapshot | None = None
        self._document: AnalysisDocument | None = None
        self._worker_tickets: dict[int, _WorkerTicket] = {}
        self._inventory_worker: Worker[Any] | None = None
        self._analysis_worker: Worker[Any] | None = None
        self._analysis_generation = 0
        self._tree: Tree[Any] | None = None
        self._status: Label | None = None
        self._analysis_status: Static | None = None
        self._tabs: TabbedContent | None = None
        self._expanded_nodes: set[int] = set()
        self._timeline_filter: str | None = None
        self._timeline_jump_index = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="body"):
            with Vertical(id="inventory-panel"):
                yield Tree(_plain_text("Threads"), id="inventory-tree")
            with Vertical(id="analysis-panel"):
                yield Static(_plain_text("Select a thread and press Enter to analyze."), id="analysis-status")
                with TabbedContent(id="analysis-tabs"):
                    for view in _VIEW_NAMES:
                        # TabPane titles are constant internal labels and its
                        # constructor accepts strings (not Rich Text objects).
                        yield TabPane(view.value.title(), id=_VIEW_IDS[view])
        yield Label(_plain_text("Loading…"), id="status")
        yield Footer()

    async def on_mount(self) -> None:
        self._tree = self.query_one("#inventory-tree", Tree)
        self._status = self.query_one("#status", Label)
        self._analysis_status = self.query_one("#analysis-status", Static)
        self._tabs = self.query_one("#analysis-tabs", TabbedContent)
        if self._initial_document is not None:
            await self._set_document(self._initial_document)
            self._set_status("analysis ready")
            return
        self._start_inventory(self.navigation.state.archive_state)

    @property
    def archive_state(self) -> ArchiveFilter:
        return self.navigation.state.archive_state

    @property
    def document(self) -> AnalysisDocument | None:
        return self._document

    async def action_quit(self) -> None:
        self.exit(None)

    def action_filter_active(self) -> None:
        self._start_inventory(ArchiveFilter.ACTIVE)

    def action_filter_archived(self) -> None:
        self._start_inventory(ArchiveFilter.ARCHIVED)

    def action_filter_all(self) -> None:
        self._start_inventory(ArchiveFilter.ALL)

    def action_cancel_work(self) -> None:
        self._analysis_generation += 1
        if self._inventory_worker is not None:
            self._inventory_worker.cancel()
        if self._analysis_worker is not None:
            self._analysis_worker.cancel()
        if self.navigation.state.loading:
            self.navigation.reject(
                LoadGeneration(self.navigation.state.generation, self.navigation.state.archive_state)
            )
        self._set_status("cancelled")

    def action_open_analysis(self) -> None:
        if self._tree is not None and self._tree.cursor_node is not None:
            cursor_data = self._tree.cursor_node.data
            if isinstance(cursor_data, NavigationNode) and cursor_data.kind is not NavigationNodeKind.THREAD:
                self._tree.cursor_node.expand()
                return
        if self.selected_ref is None:
            self._set_status("no thread selected")
            return
        snapshot = self._snapshot
        node = snapshot.find(self.selected_ref) if snapshot is not None else None
        if node is None or node.row is None:
            self._set_status("selection unavailable")
            return
        if not node.row.analyzable:
            self._set_status("source unavailable")
            return
        self._start_analysis(self.selected_ref)

    def action_view_overview(self) -> None:
        self._activate_view(ViewName.OVERVIEW)

    def action_view_timeline(self) -> None:
        self._activate_view(ViewName.TIMELINE)

    def action_view_tools(self) -> None:
        self._activate_view(ViewName.TOOLS)

    def action_view_lanes(self) -> None:
        self._activate_view(ViewName.LANES)

    def action_view_context(self) -> None:
        self._activate_view(ViewName.CONTEXT)

    def action_view_tasks(self) -> None:
        self._activate_view(ViewName.TASKS)

    def action_view_terminal(self) -> None:
        self._activate_view(ViewName.TERMINAL)

    def action_view_loss(self) -> None:
        self._activate_view(ViewName.LOSS)

    def action_toggle_step_filter(self) -> None:
        filters = (None, "message", "tool", "event", "context")
        current = filters.index(self._timeline_filter)
        self._timeline_filter = filters[(current + 1) % len(filters)]
        self._set_status(f"timeline step filter: {self._timeline_filter or 'all'}")
        self._rerender_document()

    def action_jump_significant(self) -> None:
        if self._document is None:
            self._set_status("timeline unavailable")
            return
        significant = [
            index + 1
            for index, record in enumerate(self._document.bundle.trajectory.records)
            if isinstance(record, Mapping)
            and record.get("type") in {"tool_call", "tool_result", "event", "context"}
        ]
        if not significant:
            self._set_status("no significant timeline step")
            return
        self._timeline_jump_index = (self._timeline_jump_index + 1) % len(significant)
        self._activate_view(ViewName.TIMELINE)
        self._set_status(f"jumped to record {significant[self._timeline_jump_index]}")

    def _activate_view(self, view: ViewName) -> None:
        if self._tabs is not None:
            self._tabs.active = _VIEW_IDS[view]

    def _set_status(self, message: str) -> None:
        if self._status is not None:
            self._status.update(_plain_text(message, limit=160))

    def _set_analysis_status(self, message: str) -> None:
        if self._analysis_status is not None:
            self._analysis_status.update(_plain_text(message, limit=240))

    def _cancel_analysis(self) -> None:
        self._analysis_generation += 1
        if self._analysis_worker is not None:
            self._analysis_worker.cancel()

    def _start_inventory(self, archive_state: ArchiveFilter) -> None:
        if self.inventory_loader is None:
            return
        token = self.navigation.begin_load(archive_state)
        self._cancel_analysis()
        self._snapshot = None
        self._document = None
        self._clear_tree()
        self._set_status(f"loading {archive_state.value}")
        worker = self._inventory_job(token.value, archive_state)
        self._inventory_worker = worker
        self._worker_tickets[id(worker)] = _WorkerTicket("inventory", token.value, archive_state)

    def _start_analysis(self, selection: ThreadRef) -> None:
        if self.analysis_loader is None:
            self._set_status("analysis unavailable")
            return
        self._analysis_generation += 1
        generation = self._analysis_generation
        if self._analysis_worker is not None:
            self._analysis_worker.cancel()
        self._set_status("analyzing")
        worker = self._analysis_job(generation, selection)
        self._analysis_worker = worker
        self._worker_tickets[id(worker)] = _WorkerTicket("analysis", generation, selection=selection)

    @work(group="inventory", exclusive=True, exit_on_error=False)
    async def _inventory_job(self, generation: int, archive_state: ArchiveFilter) -> SensitiveInventoryListing:
        loader = self.inventory_loader
        if loader is None:
            raise RuntimeError("inventory loader is unavailable")
        result = loader(archive_state)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, SensitiveInventoryListing):
            raise ValueError("inventory loader returned an invalid listing")
        return result

    @work(group="analysis", exclusive=True, exit_on_error=False)
    async def _analysis_job(self, generation: int, selection: ThreadRef) -> AnalysisDocument:
        loader = self.analysis_loader
        if loader is None:
            raise RuntimeError("analysis loader is unavailable")
        result = loader(selection)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, AnalysisDocument):
            raise ValueError("analysis loader returned an invalid document")
        return result

    async def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        ticket = self._worker_tickets.get(id(event.worker))
        if ticket is None:
            return
        if event.state in {WorkerState.PENDING, WorkerState.RUNNING}:
            return
        self._worker_tickets.pop(id(event.worker), None)
        if event.state is WorkerState.CANCELLED:
            return
        if event.state is WorkerState.ERROR:
            if ticket.kind == "inventory" and ticket.archive_state is not None:
                token = LoadGeneration(ticket.generation, ticket.archive_state)
                if self.navigation.is_current(token):
                    self.navigation.reject(token)
                else:
                    return
            if ticket.kind == "analysis" and ticket.generation != self._analysis_generation:
                return
            self._set_status(f"{ticket.kind} error: {_error_code(event.worker.error or RuntimeError())}")
            return
        if event.state is not WorkerState.SUCCESS:
            return
        result = event.worker.result
        if ticket.kind == "inventory":
            if ticket.archive_state is None:
                return
            token = LoadGeneration(ticket.generation, ticket.archive_state)
            if not self.navigation.is_current(token):
                return
            if not isinstance(result, SensitiveInventoryListing):
                self.navigation.reject(token)
                self._set_status("inventory error: invalid worker result")
                return
            try:
                snapshot = build_navigation_snapshot(
                    result,
                    archive_state=ticket.archive_state,
                )
            except (ValueError, TypeError) as error:
                self.navigation.reject(token)
                self._set_status(f"inventory error: {_error_code(error)}")
                return
            if not self.navigation.accept(token, snapshot):
                return
            self._snapshot = snapshot
            self._populate_tree(snapshot)
            status_suffix = "; inventory truncated, narrow lifecycle filter" if snapshot.inventory_truncated else ""
            self._set_status(f"{ticket.archive_state.value} inventory ready ({len(snapshot.rows)}){status_suffix}")
            return
        if ticket.kind == "analysis":
            if ticket.generation != self._analysis_generation or ticket.selection != self.selected_ref:
                return
            if not isinstance(result, AnalysisDocument):
                self._set_status("analysis error: invalid worker result")
                return
            await self._set_document(result)
            self._set_status("analysis ready")

    def _clear_tree(self) -> None:
        if self._tree is not None:
            self._tree.clear()
            self._expanded_nodes.clear()

    def _populate_tree(self, snapshot: NavigationSnapshot) -> None:
        if self._tree is None:
            return
        self._tree.clear()
        self._expanded_nodes.clear()
        for node in snapshot.roots:
            self._add_tree_node(self._tree.root, node)
        if self.selected_ref is not None and not snapshot.contains(self.selected_ref):
            self.selected_ref = None
            self.selection_result = None
        elif self.selected_ref is not None:
            self.navigation.select(self.selected_ref)

    def _add_tree_node(self, parent: Any, node: NavigationNode) -> Any:
        label = self._node_label(node)
        tree_node = parent.add(
            label,
            data=node,
            allow_expand=node.kind is not NavigationNodeKind.THREAD and node.expandable,
            expand=False,
        )
        if node.kind is NavigationNodeKind.THREAD and node.disabled:
            # Textual has no per-node disabled flag in 8.2; the explicit
            # marker is intentionally non-color-only and selection is gated.
            tree_node.allow_expand = False
        return tree_node

    def _node_label(self, node: NavigationNode) -> Text:
        marker = "> " if node.kind is NavigationNodeKind.THREAD and node.selection == self.selected_ref else ""
        if node.kind is NavigationNodeKind.THREAD and node.disabled:
            return _plain_text(f"{marker}[unavailable] {node.label}")
        return _plain_text(f"{marker}{node.label}")

    def _refresh_selected_markers(self) -> None:
        if self._tree is None:
            return

        def visit(tree_node: Any) -> None:
            data = tree_node.data
            if isinstance(data, NavigationNode):
                tree_node.set_label(self._node_label(data))
            for child in tree_node.children:
                visit(child)

        for root in self._tree.root.children:
            visit(root)

    async def on_tree_node_expanded(self, event: Tree.NodeExpanded[Any]) -> None:
        node = event.node.data
        if not isinstance(node, NavigationNode) or not node.children:
            return
        marker = id(event.node)
        if marker in self._expanded_nodes:
            return
        self._expanded_nodes.add(marker)
        for child in node.children:
            self._add_tree_node(event.node, child)

    async def on_tree_node_selected(self, event: Tree.NodeSelected[Any]) -> None:
        node = event.node.data
        if not isinstance(node, NavigationNode) or node.kind is not NavigationNodeKind.THREAD:
            return
        if node.selection is None or self._snapshot is None:
            return
        if not self.navigation.select(node.selection):
            return
        self.selected_ref = node.selection
        self.selection_result = node.selection
        self._refresh_selected_markers()
        if node.disabled:
            self._set_status("source unavailable")
        else:
            self._set_status("press Enter to analyze")

    async def _set_document(self, document: AnalysisDocument) -> None:
        self._document = document
        payload = document.analysis.as_dict()
        self._set_analysis_status(
            f"result={_display_value(document.analysis.result_status)} "
            f"bundle={_display_value(document.bundle.bundle_id)}"
        )
        views: dict[ViewName, str] = {
            ViewName.OVERVIEW: self._overview(document, payload),
            ViewName.TIMELINE: self._timeline(document),
            ViewName.TOOLS: self._tools_view(document),
            ViewName.LANES: self._metric_view(payload, "lanes"),
            ViewName.CONTEXT: self._metric_view(payload, "context_changes"),
            ViewName.TASKS: self._metric_view(payload, "task_evidence", "svc_signals"),
            ViewName.TERMINAL: self._metric_view(payload, "terminal_coverage"),
            ViewName.LOSS: self._loss_view(payload),
        }
        for view, text in views.items():
            pane = self.query_one(f"#{_VIEW_IDS[view]}", TabPane)
            await pane.remove_children()
            await pane.mount(Static(_plain_text(text, limit=8000)))

    def _rerender_document(self) -> None:
        if self._document is not None:
            self._render_worker()

    @work(group="render", exclusive=True, exit_on_error=False)
    async def _render_worker(self) -> None:
        if self._document is not None:
            await self._set_document(self._document)

    def _overview(self, document: AnalysisDocument, payload: Mapping[str, object]) -> str:
        manifest = document.bundle.manifest
        capabilities = manifest.get("capabilities", {})
        dimensions = payload.get("dimensions", {})
        source = manifest.get("source")
        source_status = source.get("source_status") if isinstance(source, Mapping) else None
        lines = [
            f"source_status: {_display_value(source_status)}",
            f"result_status: {_display_value(payload.get('result_status'))}",
            f"capabilities: {_display_value(capabilities)}",
            f"dimensions: {_display_value(dimensions)}",
        ]
        return "\n".join(lines)

    def _timeline(self, document: AnalysisDocument) -> str:
        filter_name = self._timeline_filter or "all"
        lines: list[str] = ["overview", f"turn / record resolution (step filter: {filter_name})"]
        current_turn: object = object()
        for index, record in enumerate(document.bundle.trajectory.records[:512]):
            if not isinstance(record, Mapping):
                continue
            record_type = record.get("type")
            if self._timeline_filter == "message" and record_type != "message":
                continue
            if self._timeline_filter == "tool" and record_type not in {"tool_call", "tool_result"}:
                continue
            if self._timeline_filter == "event" and record_type != "event":
                continue
            if self._timeline_filter == "context" and record_type != "context":
                continue
            turn_ref = record.get("turn_ref")
            if turn_ref != current_turn:
                lines.append(f"turn {_display_value(turn_ref or '<unattributed>', limit=96)}")
                current_turn = turn_ref
            fields = []
            for key in (
                "record_id", "type", "role", "event_kind", "status", "timestamp",
                "turn_ref", "actor_ref", "lane_ref",
            ):
                if key in record:
                    fields.append(f"{key}={_display_value(record[key], limit=96)}")
            lines.append(f"record {index + 1:04d} " + " ".join(fields))
        return "\n".join(lines)

    def _metric_view(self, payload: Mapping[str, object], *names: str) -> str:
        metrics = payload.get("metrics")
        dimensions = payload.get("dimensions")
        lines = []
        for name in names:
            dimension = dimensions.get(name) if isinstance(dimensions, Mapping) else None
            status = dimension.get("status", "unknown") if isinstance(dimension, Mapping) else "unknown"
            metric = metrics.get(name) if isinstance(metrics, Mapping) else None
            finding_ids = dimension.get("finding_ids", []) if isinstance(dimension, Mapping) else []
            unknown_ids = dimension.get("unknown_ids", []) if isinstance(dimension, Mapping) else []
            lines.append(
                f"{name} status={_display_value(status)} "
                f"findings={_display_value(finding_ids)} "
                f"unknown={_display_value(unknown_ids)}"
            )
            lines.append(f"evidence: {_display_value(metric, limit=1200)}")
        return "\n".join(lines)

    def _tools_view(self, document: AnalysisDocument) -> str:
        calls: dict[str, Mapping[str, object]] = {}
        results: dict[str, Mapping[str, object]] = {}
        for record in document.bundle.trajectory.records:
            if not isinstance(record, Mapping):
                continue
            tool_id = record.get("tool_call_id")
            if not isinstance(tool_id, str):
                continue
            if record.get("type") == "tool_call":
                calls.setdefault(tool_id, record)
            elif record.get("type") == "tool_result":
                results.setdefault(tool_id, record)
        lines = ["tools: call/result pairs"]
        for tool_id in sorted(set(calls) | set(results))[:512]:
            call = calls.get(tool_id)
            result = results.get(tool_id)
            if call is None:
                lines.append(f"orphan result id={_display_value(tool_id, limit=96)}")
                continue
            name = call.get("name", "<unknown tool>")
            if result is None:
                lines.append(f"pending call name={_display_value(name, limit=96)}")
                continue
            status = result.get("status", "unknown")
            content_meta = result.get("content_meta")
            truncated = isinstance(content_meta, Mapping) and bool(content_meta.get("truncated"))
            marker = "; truncated" if truncated else ""
            lines.append(
                f"call/result name={_display_value(name, limit=96)} "
                f"status={_display_value(status, limit=48)}{marker}"
            )
        return "\n".join(lines)

    def _loss_view(self, payload: Mapping[str, object]) -> str:
        loss = payload.get("lossiness")
        return f"lossiness: {_display_value(loss, limit=4000)}"


__all__ = [
    "AgentThreadAnalysisApp",
    "AnalysisDocument",
    "AnalysisLoader",
    "InventoryLoader",
    "ViewName",
    "escape_control_text",
]
