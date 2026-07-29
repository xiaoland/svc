from __future__ import annotations

from dataclasses import FrozenInstanceError
import pytest

from svc_cli.telemetry.navigation import (
    ArchiveFilter,
    ArchiveState,
    MAX_INTERACTIVE_ROWS,
    NavigationController,
    NavigationNodeKind,
    SensitiveInventoryListing,
    SensitiveInventoryRow,
    SelectionRef,
    SourceAvailability,
    WorkspaceFlavor,
    build_navigation_snapshot,
    escape_control_text,
    parse_workspace,
)


def row(
    thread_id: str,
    *,
    provider_id: str = "codex",
    archive_state: ArchiveState | str = ArchiveState.ACTIVE,
    source_availability: SourceAvailability | str = SourceAvailability.AVAILABLE,
    workspace: str | None = "/work/project",
    title: str | None = "Same title",
    first_user_message: str | None = "First message",
    recency_at_ms: int | None = 1_000,
) -> SensitiveInventoryRow:
    return SensitiveInventoryRow(
        provider_id=provider_id,
        thread_id=thread_id,
        archive_state=archive_state,
        source_availability=source_availability,
        workspace=workspace,
        title=title,
        first_user_message=first_user_message,
        recency_at_ms=recency_at_ms,
    )


class TestSensitiveInventoryRow:
    def test_provider_bounds_are_validated_without_inspecting_discarded_suffixes(self) -> None:
        oversized_workspace = "w" * 4_097
        oversized_title = "t" * 161
        oversized_message = "m" * 513
        with pytest.raises(ValueError):
            SensitiveInventoryRow(
                "codex",
                "thread-workspace",
                "active",
                "missing",
                workspace=oversized_workspace,
            )
        with pytest.raises(ValueError):
            SensitiveInventoryRow(
                "codex",
                "thread-title",
                "active",
                "missing",
                title=oversized_title,
            )
        with pytest.raises(ValueError):
            SensitiveInventoryRow(
                "codex",
                "thread-message",
                "active",
                "missing",
                first_user_message=oversized_message,
            )

        item = SensitiveInventoryRow(
            "codex",
            "thread-1",
            "active",
            "missing",
            workspace=None,
            workspace_truncated=True,
            title="t" * 160,
            title_truncated=True,
            first_user_message="m" * 512,
            first_user_message_truncated=True,
        )

        assert (item.workspace) is None
        assert (item.workspace_truncated)
        assert (item.title) == ("t" * 160)
        assert (item.title_truncated)
        assert (item.first_user_message) == ("m" * 512)
        assert (item.first_user_message_truncated)
        rendered = repr(item)
        assert ("t" * 20) not in (rendered)
        assert ("m" * 20) not in (rendered)
        assert ("w" * 20) not in (rendered)

    def test_rows_are_immutable_and_invalid_thread_ids_are_rejected(self) -> None:
        item = row("thread-1")
        with pytest.raises(FrozenInstanceError):
            item.title = "changed"  # type: ignore[misc]
        with pytest.raises(ValueError):
            row(" bad")
        with pytest.raises(ValueError):
            row("bad\nthread")


class TestListing:
    def test_filter_precedes_limit_and_unknown_only_appears_in_all(self) -> None:
        items = [
            row("active-new", recency_at_ms=3_000),
            row("archived", archive_state="archived", recency_at_ms=2_000),
            row("unknown", archive_state="unknown", recency_at_ms=1_000),
            row("active-old", recency_at_ms=500),
        ]

        archived = SensitiveInventoryListing.from_rows(items, archive_state="archived", limit=1)
        assert ([item.thread_id for item in archived.items]) == (["archived"])
        assert not (archived.inventory_truncated)

        active = SensitiveInventoryListing.from_rows(items, archive_state="active", limit=2)
        assert ([item.thread_id for item in active.items]) == (["active-new", "active-old"])

        all_items = SensitiveInventoryListing.from_rows(items, archive_state="all")
        assert ([item.thread_id for item in all_items.items]) == (["active-new", "archived", "unknown", "active-old"])

    def test_listing_never_retains_more_than_the_interactive_cap(self) -> None:
        items = (row(f"thread-{index:04d}", recency_at_ms=index) for index in range(MAX_INTERACTIVE_ROWS + 1))
        listing = SensitiveInventoryListing.from_rows(items, archive_state=ArchiveFilter.ALL)
        assert (len(listing.items)) == (MAX_INTERACTIVE_ROWS)
        assert (listing.inventory_truncated)


class TestWorkspace:
    def test_workspace_flavors_are_lexical_and_do_not_resolve(self) -> None:
        posix = parse_workspace("/Users/Sir/project")
        assert (posix.flavor) == (WorkspaceFlavor.POSIX)
        assert (posix.tree_parts) == (("/", "Users", "Sir", "project"))

        drive = parse_workspace(r"C:\Users\Sir\project")
        assert (drive.flavor) == (WorkspaceFlavor.WINDOWS_DRIVE)
        assert (drive.tree_parts) == (("C:", "Users", "Sir", "project"))

        unc = parse_workspace(r"\\server\share\project")
        assert (unc.flavor) == (WorkspaceFlavor.WINDOWS_UNC)
        assert (unc.components) == (("project",))

        relative = parse_workspace(r"work\project")
        assert (relative.flavor) == (WorkspaceFlavor.RELATIVE)
        assert (relative.components) == (("work", "project"))

        missing = parse_workspace(None)
        assert (missing.flavor) == (WorkspaceFlavor.UNKNOWN)
        truncated = parse_workspace("x" * 4_097)
        assert (truncated.flavor) == (WorkspaceFlavor.TRUNCATED)
        assert (truncated.raw) is None


class TestSnapshot:
    def test_tree_groups_provider_workspace_lifecycle_and_thread(self) -> None:
        items = [
            row("z", provider_id="z-provider", workspace="/z", recency_at_ms=3),
            row("b", provider_id="a-provider", workspace=r"C:\repo", recency_at_ms=5),
            row("a", provider_id="a-provider", workspace="/work/project", recency_at_ms=10),
            row("c", provider_id="a-provider", workspace="/work/other", recency_at_ms=9, source_availability="missing"),
        ]
        snapshot = build_navigation_snapshot(items, archive_state=ArchiveFilter.ALL)
        assert ([root.label for root in snapshot.roots]) == (["a-provider", "z-provider"])
        assert (snapshot.archive_state) == (ArchiveFilter.ALL)
        leaves = list(snapshot.iter_leaves())
        assert ([leaf.selection.thread_id for leaf in leaves]) == (["a", "c", "b", "z"])
        missing_leaf = snapshot.find(SelectionRef("a-provider", "c"))
        assert missing_leaf is not None
        assert (missing_leaf.kind) == (NavigationNodeKind.THREAD)
        assert (missing_leaf.disabled)

    def test_every_thread_label_shows_title_and_first_message(self) -> None:
        snapshot = build_navigation_snapshot(
            [
                row(
                    "recognizable",
                    title="Unique title",
                    first_user_message="Why this thread exists",
                )
            ]
        )

        assert (next(snapshot.iter_leaves()).label) == ("Unique title — Why this thread exists")

    def test_duplicate_title_falls_back_to_first_message_and_final_duplicate_index(self) -> None:
        items = [
            row("one", title="duplicate", first_user_message="first", recency_at_ms=2),
            row("two", title="duplicate", first_user_message="second", recency_at_ms=1),
            row("three", title="duplicate", first_user_message="first", recency_at_ms=0),
        ]
        snapshot = build_navigation_snapshot(items)
        labels = [leaf.label for leaf in snapshot.iter_leaves()]
        assert (labels[0]) == ("duplicate — first")
        assert (labels[1]) == ("duplicate — second")
        assert (labels[2]) == ("duplicate — first (2)")

    def test_valid_workspace_roots_precede_truncated_and_unknown_groups(self) -> None:
        items = [
            row("drive", workspace=r"C:\repo"),
            row("posix", workspace="/repo"),
            SensitiveInventoryRow(
                "codex",
                "truncated",
                "active",
                "available",
                workspace=None,
                workspace_truncated=True,
                title="Truncated",
                first_user_message="Workspace",
            ),
            row("unknown", workspace=None),
        ]
        snapshot = build_navigation_snapshot(items)

        assert ([node.label for node in snapshot.roots[0].children]) == (["/", "C:", "<truncated workspace>", "<unknown workspace>"])

    def test_control_escaping_is_paint_only(self) -> None:
        original = "title\x1b[31m\n\u202eend"
        escaped = escape_control_text(original)
        assert (escaped) == (r"title\u{001B}[31m\u{000A}\u{202E}end")
        item = row("thread-control", title=original)
        assert (item.title) == (original)


class TestNavigationController:
    def test_stale_generation_cannot_replace_newer_snapshot(self) -> None:
        controller = NavigationController()
        first = controller.begin_load(ArchiveFilter.ACTIVE)
        second = controller.begin_load(ArchiveFilter.ALL)
        first_snapshot = build_navigation_snapshot([row("first")])
        second_snapshot = build_navigation_snapshot([row("second")], archive_state=ArchiveFilter.ALL)

        assert not (controller.accept(first, first_snapshot))
        assert (controller.accept(second, second_snapshot))
        assert (controller.state.snapshot) == (second_snapshot)

        assert (controller.select(SelectionRef("codex", "second")))
        third = controller.begin_filter(ArchiveFilter.ARCHIVED)
        archived_snapshot = build_navigation_snapshot(
            [row("archived", archive_state=ArchiveState.ARCHIVED)], archive_state=ArchiveFilter.ARCHIVED
        )
        assert (controller.accept(third, archived_snapshot))
        assert (controller.state.selected) is None

    def test_selection_is_kept_when_new_snapshot_contains_it(self) -> None:
        controller = NavigationController()
        token = controller.begin_load()
        snapshot = build_navigation_snapshot([row("same")])
        assert (controller.accept(token, snapshot))
        assert (controller.select(SelectionRef("codex", "same")))

        refresh = controller.begin_load()
        refreshed = build_navigation_snapshot([row("same", recency_at_ms=2)])
        assert (controller.accept(refresh, refreshed))
        assert (controller.state.selected) == (SelectionRef("codex", "same"))
