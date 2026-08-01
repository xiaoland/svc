from __future__ import annotations

import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest

from svc_cli.errors import SvcError
from svc_cli.telemetry.agent_threads import (
    ArchiveFilter,
    ArchiveState,
    ProviderContext,
    ThreadInventoryQuery,
    ThreadSelection,
)
from svc_cli.telemetry.providers import CodexRolloutProvider
from svc_cli.telemetry.providers import codex_rollout


@dataclass(frozen=True)
class InventoryCase:
    root: Path
    provider: CodexRolloutProvider

    def list(
        self,
        *,
        limit: int = 20,
        archive_state: ArchiveFilter = ArchiveFilter.ALL,
    ):
        return self.provider.list_inventory(
            ProviderContext(home=self.root),
            ThreadInventoryQuery(archive_state=archive_state, limit=limit),
        )


@pytest.fixture
def inventory_case() -> Iterator[InventoryCase]:
    with tempfile.TemporaryDirectory() as tmp:
        yield InventoryCase(root=Path(tmp), provider=CodexRolloutProvider())


@contextmanager
def state_database(root: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(root / "state_5.sqlite")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


class TestCodexInventory:
    def test_list_requires_only_metadata_and_does_not_probe_rollouts(
        self,
        monkeypatch: pytest.MonkeyPatch,
        inventory_case: InventoryCase,
    ) -> None:
        with state_database(inventory_case.root) as connection:
            connection.execute("CREATE TABLE threads (id TEXT, updated_at INTEGER)")
            connection.execute(
                "INSERT INTO threads VALUES (?, ?)",
                ("thread-metadata", "2"),
            )
        monkeypatch.setattr(
            codex_rollout,
            "_open_source",
            lambda *_args, **_kwargs: pytest.fail("inventory must not open rollout sources"),
        )

        listed = inventory_case.list(limit=5)

        assert (listed.items[0].thread_id) == ("thread-metadata")
        assert (listed.items[0].archive_state) == (ArchiveState.UNKNOWN)

    def test_list_is_metadata_only_and_defers_rollout_signature_to_export(
        self,
        inventory_case: InventoryCase,
    ) -> None:
        source = inventory_case.root / "not-a-rollout.jsonl"
        source.write_text("private non-rollout body", encoding="utf-8")
        with state_database(inventory_case.root) as connection:
            connection.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT)")
            connection.execute(
                "INSERT INTO threads VALUES (?, ?)",
                ("thread-metadata-only", source.name),
            )

        listed = inventory_case.list(limit=5)

        assert (listed.items[0].thread_id) == ("thread-metadata-only")
        with pytest.raises(SvcError) as raised:
            inventory_case.provider.resolve(
                ProviderContext(home=inventory_case.root),
                ThreadSelection(thread_id="thread-metadata-only"),
            )
        assert (raised.value.code) == ("thread-source-incompatible")

    def test_list_uses_stable_descriptor_order_when_timestamps_tie(
        self,
        inventory_case: InventoryCase,
    ) -> None:
        with state_database(inventory_case.root) as connection:
            connection.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT, updated_at TEXT)")
            connection.executemany(
                "INSERT INTO threads VALUES (?, ?, ?)",
                [
                    ("zulu", "missing-zulu.jsonl", "same-time"),
                    ("middle", "../outside.jsonl", "same-time"),
                    ("alpha", None, "same-time"),
                ],
            )

        listed = inventory_case.list(limit=2)

        assert [item.thread_id for item in listed.items] == ["alpha", "middle"]
        assert listed.inventory_truncated

    def test_inventory_filters_lifecycle_before_limit(
        self,
        inventory_case: InventoryCase,
    ) -> None:
        with state_database(inventory_case.root) as connection:
            connection.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT, archived, recency_at_ms INTEGER)")
            connection.executemany(
                "INSERT INTO threads VALUES (?, ?, ?, ?)",
                [
                    ("active-newest", "active.jsonl", 0, 400),
                    ("active-missing", "active-missing.jsonl", 0, 375),
                    ("active-unavailable", None, 0, 350),
                    ("archived-unavailable", None, 1, 325),
                    ("archived-available", "archived.jsonl", 1, 300),
                    ("unknown-middle", "unknown.jsonl", "1", 200),
                    ("archived-missing", "missing.jsonl", 1, 100),
                ],
            )

        active_listing = inventory_case.list(
            limit=3,
            archive_state=ArchiveFilter.ACTIVE,
        )
        archived_listing = inventory_case.list(
            limit=3,
            archive_state=ArchiveFilter.ARCHIVED,
        )
        all_listing = inventory_case.list(limit=10)

        assert [item.thread_id for item in active_listing.items] == [
            "active-newest",
            "active-missing",
            "active-unavailable",
        ]
        assert ([item.thread_id for item in archived_listing.items]) == (
            ["archived-unavailable", "archived-available", "archived-missing"]
        )
        assert ([item.thread_id for item in all_listing.items]) == (
            [
                "active-newest",
                "active-missing",
                "active-unavailable",
                "archived-unavailable",
                "archived-available",
                "unknown-middle",
                "archived-missing",
            ]
        )
        assert (all_listing.items[5].archive_state) == (ArchiveState.UNKNOWN)

    def test_inventory_recency_fallback_units_ranges_and_display_times_are_exact(
        self,
        inventory_case: InventoryCase,
    ) -> None:
        sqlite_integer_overflow = 2**63 - 1
        with state_database(inventory_case.root) as connection:
            connection.execute(
                """
                CREATE TABLE threads (
                    id TEXT,
                    rollout_path TEXT,
                    archived INTEGER,
                    created_at,
                    updated_at,
                    recency_at_ms,
                    updated_at_ms
                )
                """
            )
            connection.executemany(
                "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    ("from-recency", "recency.jsonl", 0, 0, 11, 5_000, 99_000),
                    (
                        "from-updated-ms",
                        "updated-ms.jsonl",
                        0,
                        "invalid",
                        12,
                        "invalid",
                        6_000,
                    ),
                    ("from-seconds", "seconds.jsonl", 0, -1, 7, -1, None),
                    (
                        "missing-recency",
                        "missing.jsonl",
                        0,
                        None,
                        sqlite_integer_overflow,
                        None,
                        None,
                    ),
                ],
            )

        listed = inventory_case.list()

        assert ([item.thread_id for item in listed.items]) == (
            ["from-seconds", "from-updated-ms", "from-recency", "missing-recency"]
        )
        by_id = {item.thread_id: item for item in listed.items}
        assert (by_id["from-recency"].created_at) == ("0")
        assert (by_id["from-recency"].updated_at) == ("11")
        assert (by_id["from-updated-ms"].created_at) is None
        assert (by_id["from-seconds"].created_at) is None
        assert (by_id["from-seconds"].updated_at) == ("7")
        assert (by_id["missing-recency"].updated_at) == (str(sqlite_integer_overflow))

    def test_inventory_omits_unusable_and_ambiguous_ids(
        self,
        inventory_case: InventoryCase,
    ) -> None:
        rows: list[tuple[object, str, int, int]] = [
            ("", "missing.jsonl", 0, 220),
            (123, "missing.jsonl", 0, 210),
            ("duplicate", "first.jsonl", 0, 200),
            ("duplicate", "second.jsonl", 1, 190),
            ("safe-a", "missing.jsonl", 0, 20),
            ("safe-b", "missing.jsonl", 0, 10),
        ]
        with state_database(inventory_case.root) as connection:
            connection.execute("CREATE TABLE threads (id, rollout_path, archived, recency_at_ms INTEGER)")
            connection.executemany(
                "INSERT INTO threads VALUES (?, ?, ?, ?)",
                rows,
            )

        listed = inventory_case.list(limit=2)
        active = inventory_case.list(
            limit=20,
            archive_state=ArchiveFilter.ACTIVE,
        )
        archived = inventory_case.list(
            limit=20,
            archive_state=ArchiveFilter.ARCHIVED,
        )

        assert [item.thread_id for item in listed.items] == ["safe-a", "safe-b"]
        assert "duplicate" not in {item.thread_id for item in active.items}
        assert "duplicate" not in {item.thread_id for item in archived.items}

    def test_inventory_is_bounded_and_filters_before_limit(
        self,
        monkeypatch: pytest.MonkeyPatch,
        inventory_case: InventoryCase,
    ) -> None:
        with state_database(inventory_case.root) as connection:
            connection.execute(
                """
                CREATE TABLE threads (
                    id TEXT,
                    rollout_path TEXT,
                    archived INTEGER,
                    recency_at_ms INTEGER,
                    created_at INTEGER,
                    updated_at INTEGER,
                    cwd TEXT,
                    title TEXT,
                    first_user_message TEXT,
                    preview TEXT,
                    reasoning TEXT,
                    tool_payload TEXT
                )
                """
            )
            connection.executemany(
                "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        "archived",
                        "archived.jsonl",
                        1,
                        9_000,
                        1,
                        2,
                        "/archive",
                        "archived-title",
                        "archived-message",
                        "never-select-preview",
                        "never-select-reasoning",
                        "never-select-tool",
                    ),
                    (
                        "active-new",
                        "active-new.jsonl",
                        0,
                        8_000,
                        3,
                        4,
                        "w" * 4_097,
                        "t" * 161,
                        "m" * 513,
                        "never-select-preview",
                        "never-select-reasoning",
                        "never-select-tool",
                    ),
                    (
                        "active-old",
                        "active-old.jsonl",
                        0,
                        7_000,
                        5,
                        6,
                        "/active/old",
                        "old-title",
                        "old-message",
                        "never-select-preview",
                        "never-select-reasoning",
                        "never-select-tool",
                    ),
                ],
            )

        materialized_prefixes: list[tuple[int, int]] = []
        original_decode = codex_rollout._decode_inventory_prefix

        def recording_decode(sqlite_type, prefix, overflow, **kwargs):
            materialized_prefixes.append(
                (
                    kwargs["maximum_code_points"],
                    len(prefix) if isinstance(prefix, bytes) else 0,
                )
            )
            return original_decode(
                sqlite_type,
                prefix,
                overflow,
                **kwargs,
            )

        monkeypatch.setattr(
            codex_rollout,
            "_decode_inventory_prefix",
            recording_decode,
        )
        listing = inventory_case.list(
            archive_state=ArchiveFilter.ACTIVE,
            limit=1,
        )

        assert ([item.thread_id for item in listing.items]) == (["active-new"])
        assert listing.inventory_truncated
        item = listing.items[0]
        assert (item.workspace) is None
        assert item.workspace_truncated
        assert (item.title) == ("t" * 160)
        assert item.title_truncated
        assert (item.first_user_message) == ("m" * 512)
        assert item.first_user_message_truncated
        assert (item.created_at) == ("3")
        assert (item.updated_at) == ("4")
        assert (item.recency_at_ms) == (8_000)
        assert (materialized_prefixes) == ([(4_096, 4_097), (160, 161), (512, 513)])

    def test_inventory_requires_the_exact_id_column(
        self,
        inventory_case: InventoryCase,
    ) -> None:
        with state_database(inventory_case.root) as connection:
            connection.execute("CREATE TABLE threads (thread_id TEXT, rolloutPath TEXT)")

        with pytest.raises(SvcError) as raised:
            inventory_case.list()

        assert (raised.value.code) == ("thread-source-incompatible")
