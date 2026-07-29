from __future__ import annotations

import asyncio
from typing import Mapping

import pytest
from textual.widgets import TabbedContent, Tree

from svc_cli.telemetry.agent_threads import (
    ArchiveFilter,
    SensitiveInventoryListing,
    SensitiveInventoryRow,
    SourceAvailability,
    ThreadRef,
)
from svc_cli.telemetry.analysis import AnalysisResult
from svc_cli.telemetry.trajectory import ValidatedBundle, ValidatedTrajectory
from svc_cli.telemetry.tui import AgentThreadAnalysisApp, AnalysisDocument


def _row(
    thread_id: str,
    *,
    archive: str = "active",
    availability: str = "available",
    workspace: str | None = "/workspace/project",
    title: str | None = "Title",
    message: str | None = "First message",
) -> SensitiveInventoryRow:
    return SensitiveInventoryRow(
        provider_id="codex",
        thread_id=thread_id,
        archive_state=archive,
        source_availability=availability,
        workspace=workspace,
        title=title,
        first_user_message=message,
        recency_at_ms=100,
    )


def _document(
    bundle_id: str = "bundle-1",
    *,
    result_status: str = "ready",
    records: tuple[Mapping[str, object], ...] | None = None,
    lossiness: Mapping[str, object] | None = None,
) -> AnalysisDocument:
    records = records or (
        {"record_id": "r0", "record_index": 0, "type": "meta"},
        {
            "record_id": "r1",
            "record_index": 1,
            "type": "message",
            "role": "user",
            "timestamp": "2026-07-28T00:00:00Z",
            "turn_ref": "turn-1",
        },
    )
    trajectory = ValidatedTrajectory(records, b"", "trajectory-hash")
    bundle = ValidatedBundle(
        {
            "source": {"source_status": "ready"},
            "capabilities": {"terminal_events": "available"},
        },
        trajectory,
        bundle_id,
    )
    payload: Mapping[str, object] = {
        "result_status": result_status,
        "dimensions": {
            "task_evidence": {
                "status": "available",
                "finding_ids": [],
                "unknown_ids": [],
            }
        },
        "metrics": {
            "tool_outcomes": {"calls": 1, "results": 1},
            "lanes": {"lane_count": 1},
            "context_changes": {"changes": []},
            "task_evidence": {"user_turn_count": 1},
            "svc_signals": {"svc_cli_calls": 0},
            "terminal_coverage": {"status": "complete"},
        },
        "lossiness": lossiness
        or {"bundle": {"source_status": "ready"}, "analysis": {"limits_reached": []}},
    }
    return AnalysisDocument(
        bundle, AnalysisResult(payload, b"{}\n", result_status, bundle_id)
    )


async def _expand_all(tree: Tree[object], pilot) -> list[object]:
    pending = list(tree.root.children)
    leaves: list[object] = []
    while pending:
        node = pending.pop(0)
        if node.allow_expand and not node.children:
            node.expand()
            await pilot.pause()
        if node.children:
            pending.extend(node.children)
        else:
            leaves.append(node)
    return leaves


@pytest.mark.asyncio
async def test_constructor_and_document_repr_are_structural() -> None:
    document = _document()
    assert "trajectory-hash" not in repr(document)
    assert repr(document) == "AnalysisDocument(<validated>)"
    with pytest.raises(ValueError):
        AgentThreadAnalysisApp(
            initial_document=document,
            inventory_loader=lambda _: SensitiveInventoryListing(()),
        )
    with pytest.raises(ValueError):
        AgentThreadAnalysisApp(inventory_loader=lambda _: SensitiveInventoryListing(()))


@pytest.mark.asyncio
async def test_lazy_tree_markup_control_escape_and_unavailable_selection() -> None:
    rows = SensitiveInventoryListing(
        (
            _row("available", title="[bold]\x1b[31munsafe\n"),
            _row(
                "missing",
                availability=SourceAvailability.MISSING,
                title=None,
                message=None,
            ),
        )
    )
    calls: list[ThreadRef] = []

    async def inventory(_archive_state: ArchiveFilter) -> SensitiveInventoryListing:
        return rows

    async def analyze(selection: ThreadRef) -> AnalysisDocument:
        calls.append(selection)
        return _document(selection.thread_id)

    app = AgentThreadAnalysisApp(inventory_loader=inventory, analysis_loader=analyze)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(0.1)
        tree = app.query_one("#inventory-tree", Tree)
        assert len(tree.root.children) == 1
        assert len(tree.root.children[0].children) == 0, "children are lazy"
        leaves = await _expand_all(tree, pilot)
        assert len(leaves) == 2
        unavailable = next(
            node for node in leaves if node.data.row.thread_id == "missing"
        )
        assert not unavailable.allow_expand
        assert "[unavailable]" in str(unavailable.label)
        tree.select_node(unavailable)
        await pilot.pause()
        app.action_open_analysis()
        await pilot.pause(0.05)
        assert calls == []
        assert "unavailable" in str(app._status.render())
        available = next(
            node for node in leaves if node.data.row.thread_id == "available"
        )
        tree.select_node(available)
        await pilot.pause()
        app.action_open_analysis()
        await pilot.pause(0.1)
        assert calls == [ThreadRef("codex", "available")]
        assert "\x1b" not in str(available.label)
        assert "\\u{001B}" in str(available.label)


@pytest.mark.asyncio
async def test_analysis_views_keyboard_filter_resize_and_quit() -> None:
    rows = SensitiveInventoryListing(
        (_row("active"), _row("archived", archive="archived"))
    )
    seen_filters: list[ArchiveFilter] = []

    async def inventory(archive_state: ArchiveFilter) -> SensitiveInventoryListing:
        seen_filters.append(archive_state)
        return rows

    async def analyze(_selection: ThreadRef) -> AnalysisDocument:
        return _document()

    app = AgentThreadAnalysisApp(inventory_loader=inventory, analysis_loader=analyze)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(0.1)
        await pilot.press("l")
        await pilot.pause(0.1)
        await pilot.press("r")
        await pilot.pause(0.1)
        await pilot.press("a")
        await pilot.pause(0.1)
        assert seen_filters[0] == ArchiveFilter.ACTIVE
        assert ArchiveFilter.ALL in seen_filters
        assert ArchiveFilter.ARCHIVED in seen_filters
        assert app.archive_state == ArchiveFilter.ACTIVE

        tree = app.query_one("#inventory-tree", Tree)
        leaves = await _expand_all(tree, pilot)
        tree.select_node(leaves[0])
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause(0.1)
        assert app.document is not None
        assert len(app.query("TabPane")) == 8
        view_ids = (
            "overview",
            "timeline",
            "tools",
            "lanes",
            "context",
            "tasks",
            "terminal",
            "loss",
        )
        for key, expected in zip("12345678", view_ids):
            await pilot.press(key)
            assert app.query_one("#analysis-tabs", TabbedContent).active == expected
        await pilot.resize_terminal(30, 10)
        await pilot.pause()
        await pilot.press("q")
        assert app.return_value is None


@pytest.mark.asyncio
async def test_stale_inventory_and_analysis_results_are_ignored() -> None:
    active_gate = asyncio.Event()
    analysis_gate = asyncio.Event()
    rows_active = SensitiveInventoryListing((_row("active"),))
    rows_archived = SensitiveInventoryListing((_row("archived", archive="archived"),))
    calls: list[ArchiveFilter] = []

    async def inventory(archive_state: ArchiveFilter) -> SensitiveInventoryListing:
        calls.append(archive_state)
        if archive_state is ArchiveFilter.ACTIVE:
            await active_gate.wait()
            return rows_active
        if archive_state is ArchiveFilter.ALL:
            return SensitiveInventoryListing(rows_active.items + rows_archived.items)
        return rows_archived

    async def analyze(selection: ThreadRef) -> AnalysisDocument:
        if selection.thread_id == "active":
            await analysis_gate.wait()
            return _document("stale")
        return _document("fresh")

    app = AgentThreadAnalysisApp(inventory_loader=inventory, analysis_loader=analyze)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause(0.1)
        assert app.archive_state == ArchiveFilter.ARCHIVED
        assert app._snapshot.rows[0].thread_id == "archived"
        active_gate.set()
        await pilot.pause(0.1)
        assert app._snapshot.rows[0].thread_id == "archived"

        await pilot.press("l")
        await pilot.pause(0.1)
        assert app.archive_state == ArchiveFilter.ALL

        tree = app.query_one("#inventory-tree", Tree)
        leaves = await _expand_all(tree, pilot)
        active_node = next(
            node for node in leaves if node.data.row.thread_id == "active"
        )
        archived_node = next(
            node for node in leaves if node.data.row.thread_id == "archived"
        )
        tree.select_node(active_node)
        await pilot.pause()
        app.action_open_analysis()
        tree.select_node(archived_node)
        await pilot.pause()
        app.action_open_analysis()
        await pilot.pause(0.1)
        assert app.document.bundle.bundle_id == "fresh"
        analysis_gate.set()
        await pilot.pause(0.1)
        assert app.document.bundle.bundle_id == "fresh"


@pytest.mark.asyncio
async def test_error_and_cancel_do_not_leak_loader_values() -> None:
    gate = asyncio.Event()

    async def inventory(_archive_state: ArchiveFilter) -> SensitiveInventoryListing:
        return SensitiveInventoryListing((_row("one"),))

    async def analyze(_selection: ThreadRef) -> AnalysisDocument:
        await gate.wait()
        raise ValueError("PRIVATE_TITLE_SHOULD_NOT_APPEAR")

    app = AgentThreadAnalysisApp(inventory_loader=inventory, analysis_loader=analyze)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(0.1)
        leaves = await _expand_all(app.query_one("#inventory-tree", Tree), pilot)
        app.query_one("#inventory-tree", Tree).select_node(leaves[0])
        await pilot.pause()
        app.action_open_analysis()
        await pilot.pause()
        app.action_cancel_work()
        await pilot.pause()
        status = str(app._status.render())
        assert "cancelled" in status
        assert "PRIVATE_TITLE" not in status
        gate.set()


@pytest.mark.asyncio
async def test_truncated_five_thousand_inventory_is_lazy_and_explicit() -> None:
    rows = tuple(_row(f"thread-{index:04d}") for index in range(5_000))

    async def inventory(_archive_state: ArchiveFilter) -> SensitiveInventoryListing:
        return SensitiveInventoryListing(rows, inventory_truncated=True)

    async def analyze(_selection: ThreadRef) -> AnalysisDocument:
        return _document()

    app = AgentThreadAnalysisApp(inventory_loader=inventory, analysis_loader=analyze)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(0.2)
        assert "inventory truncated" in str(app._status.render())
        assert "narrow lifecycle" in str(app._status.render())
        tree = app.query_one("#inventory-tree", Tree)
        assert len(tree.root.children) == 1
        assert len(tree.root.children[0].children) == 0, (
            "5,000 rows are not eagerly materialized"
        )
        lifecycle = tree.root.children[0]
        while True:
            lifecycle.expand()
            await pilot.pause()
            if len(lifecycle.children) == 5_000:
                break
            lifecycle = lifecycle.children[0]
        assert len(lifecycle.children) == 5_000


@pytest.mark.asyncio
async def test_selected_marker_survives_filter_reload_and_lazy_materialization() -> (
    None
):
    rows = SensitiveInventoryListing(
        (_row("active"), _row("archived", archive="archived"))
    )

    async def inventory(_archive_state: ArchiveFilter) -> SensitiveInventoryListing:
        return rows

    async def analyze(_selection: ThreadRef) -> AnalysisDocument:
        return _document()

    app = AgentThreadAnalysisApp(inventory_loader=inventory, analysis_loader=analyze)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(0.1)
        tree = app.query_one("#inventory-tree", Tree)
        leaves = await _expand_all(tree, pilot)
        selected = next(node for node in leaves if node.data.row.thread_id == "active")
        tree.select_node(selected)
        await pilot.pause()
        assert str(selected.label).startswith("> ")
        selected_ref = app.selected_ref
        await pilot.press("l")
        await pilot.pause(0.1)
        assert app.selected_ref == selected_ref
        leaves = await _expand_all(tree, pilot)
        selected_after_reload = next(
            node for node in leaves if node.data.row.thread_id == "active"
        )
        assert str(selected_after_reload.label).startswith("> ")


@pytest.mark.asyncio
async def test_partial_loss_views_tools_pairing_timeline_filter_jump_and_escape() -> (
    None
):
    records = (
        {"record_id": "r0", "record_index": 0, "type": "meta"},
        {
            "record_id": "r1",
            "record_index": 1,
            "type": "tool_call",
            "tool_call_id": "call-1",
            "name": "shell",
        },
        {
            "record_id": "r2",
            "record_index": 2,
            "type": "tool_result",
            "tool_call_id": "call-1",
            "status": "error",
            "content_meta": {"truncated": True},
            "content": "PRIVATE_TOOL_RESULT",
        },
        {
            "record_id": "r3",
            "record_index": 3,
            "type": "tool_call",
            "tool_call_id": "call-2",
            "name": "pending",
        },
        {
            "record_id": "r4",
            "record_index": 4,
            "type": "tool_result",
            "tool_call_id": "call-orphan",
            "status": "unknown",
        },
        {"record_id": "r5", "record_index": 5, "type": "event", "event_kind": "error"},
    )
    lossiness = {
        "bundle": {
            "source_status": "partial",
            "dropped": {"invalid_json": 1},
            "truncated": {"message": 1},
        },
        "analysis": {"limits_reached": ["finding"], "findings_omitted": 1},
    }
    app = AgentThreadAnalysisApp(
        initial_document=_document(
            result_status="partial", records=records, lossiness=lossiness
        )
    )
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.2)
        assert "result=partial" in str(app._analysis_status.render())
        await pilot.press("3")
        await pilot.pause()
        tools_text = str(app.query_one("#tools Static").render())
        assert "call/result" in tools_text
        assert "pending" in tools_text
        assert "orphan" in tools_text
        assert "truncated" in tools_text
        assert "error" in tools_text
        assert "PRIVATE_TOOL_RESULT" not in tools_text
        await pilot.press("2")
        await pilot.press("f")
        await pilot.pause(0.1)
        assert "step filter" in str(app._status.render())
        await pilot.press("j")
        assert "jumped to record" in str(app._status.render())
        await pilot.resize_terminal(24, 8)
        await pilot.pause()
        await pilot.press("escape")
        assert app.return_value is None
