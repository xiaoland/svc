from __future__ import annotations

import errno
import json
import sqlite3
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from svc_cli.errors import SvcError
from svc_cli.telemetry.agent_threads import (
    ArchiveFilter,
    ArchiveState,
    ProviderContext,
    SourceAvailability,
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
    def test_list_projects_metadata_without_rollout_projection(
        self,
        inventory_case: InventoryCase,
    ) -> None:
        source = inventory_case.root / "rollout.jsonl"
        records = [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "type": "session_meta",
                "payload": {"id": "thread-db"},
            },
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "type": "message",
                "payload": {"role": "user", "content": "private"},
            },
        ]
        source.write_text(
            "\n".join(json.dumps(record) for record in records) + "\n",
            encoding="utf-8",
        )
        with state_database(inventory_case.root) as connection:
            connection.execute(
                "CREATE TABLE threads (id TEXT, rollout_path TEXT, created_at INTEGER, updated_at INTEGER, archived INTEGER)"
            )
            connection.execute(
                "INSERT INTO threads VALUES (?, ?, ?, ?, ?)",
                ("thread-db", source.name, 1, 2, 0),
            )

        listed = inventory_case.list(limit=5)

        assert listed.items[0].thread_id == "thread-db"
        assert listed.items[0].archive_state == ArchiveState.ACTIVE
        assert listed.items[0].created_at == "1"
        assert listed.omitted_sources == 0
        assert not (inventory_case.root / "state_5.sqlite-wal").exists()
        assert not (inventory_case.root / "state_5.sqlite-shm").exists()

    def test_list_marks_a_missing_rollout_without_scanning_or_failing_all_metadata(
        self,
        inventory_case: InventoryCase,
    ) -> None:
        with state_database(inventory_case.root) as connection:
            connection.execute(
                "CREATE TABLE threads (id TEXT, rollout_path TEXT, updated_at INTEGER)"
            )
            connection.execute(
                "INSERT INTO threads VALUES (?, ?, ?)",
                ("thread-missing", "sessions/missing.jsonl", "2"),
            )

        listed = inventory_case.list(limit=5)

        assert (listed.items[0].thread_id) == ("thread-missing")
        assert (listed.items[0].archive_state) == (ArchiveState.UNKNOWN)
        assert (listed.items[0].source_availability) == (SourceAvailability.MISSING)

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

    @pytest.mark.parametrize(
        ("rows", "limit", "expected_ids", "expected_omitted"),
        [
            pytest.param(
                [
                    ("unsafe-leading", "../escaped.jsonl", 4),
                    ("unresolvable-leading", "\x00unresolvable.jsonl", 3),
                    ("safe-recent", "recent.jsonl", 2),
                    ("safe-older", "older.jsonl", 1),
                ],
                2,
                ["safe-recent", "safe-older"],
                2,
                id="unsafe-before-safe-limit",
            ),
            pytest.param(
                [
                    ("unsafe-newer", "../escaped-newer.jsonl", 2),
                    ("unsafe-older", "../escaped-older.jsonl", 1),
                ],
                1,
                [],
                2,
                id="all-unsafe-degraded",
            ),
        ],
    )
    def test_list_omits_unsafe_rows_before_safe_limit(
        self,
        rows: list[tuple[str, str, int]],
        limit: int,
        expected_ids: list[str],
        expected_omitted: int,
        inventory_case: InventoryCase,
    ) -> None:
        for _, path, _ in rows:
            if path in {"recent.jsonl", "older.jsonl"}:
                (inventory_case.root / path).write_text(
                    "metadata-only",
                    encoding="utf-8",
                )

        with state_database(inventory_case.root) as connection:
            connection.execute(
                "CREATE TABLE threads (id TEXT, rollout_path TEXT, updated_at INTEGER)"
            )
            connection.executemany("INSERT INTO threads VALUES (?, ?, ?)", rows)

        listed = inventory_case.list(limit=limit)

        assert [item.thread_id for item in listed.items] == expected_ids
        assert listed.omitted_sources == expected_omitted
        if expected_ids:
            with pytest.raises(SvcError) as raised:
                inventory_case.provider.resolve(
                    ProviderContext(home=inventory_case.root),
                    ThreadSelection(thread_id="unsafe-leading"),
                )
            assert raised.value.code == "thread-source-unsafe"

    def test_list_uses_stable_descriptor_order_when_timestamps_tie(
        self,
        inventory_case: InventoryCase,
    ) -> None:
        alpha = inventory_case.root / "alpha.jsonl"
        zulu = inventory_case.root / "zulu.jsonl"
        alpha.write_text("metadata-only", encoding="utf-8")
        zulu.write_text("metadata-only", encoding="utf-8")
        with state_database(inventory_case.root) as connection:
            connection.execute(
                "CREATE TABLE threads (id TEXT, rollout_path TEXT, updated_at TEXT)"
            )
            connection.executemany(
                "INSERT INTO threads VALUES (?, ?, ?)",
                [
                    ("zulu-safe", zulu.name, "same-time"),
                    ("middle-unsafe", "../escaped.jsonl", "same-time"),
                    ("alpha-safe", alpha.name, "same-time"),
                ],
            )

        listed = inventory_case.list(limit=2)

        assert ([item.thread_id for item in listed.items]) == (["alpha-safe", "zulu-safe"])
        assert (listed.omitted_sources) == (1)

    def test_inventory_filters_lifecycle_before_limit_and_keeps_availability_independent(
        self,
        inventory_case: InventoryCase,
    ) -> None:
        active = inventory_case.root / "active.jsonl"
        archived = inventory_case.root / "archived.jsonl"
        unknown = inventory_case.root / "unknown.jsonl"
        active.write_text("metadata-only", encoding="utf-8")
        archived.write_text("metadata-only", encoding="utf-8")
        unknown.write_text("metadata-only", encoding="utf-8")
        with state_database(inventory_case.root) as connection:
            connection.execute(
                "CREATE TABLE threads (id TEXT, rollout_path TEXT, archived, recency_at_ms INTEGER)"
            )
            connection.executemany(
                "INSERT INTO threads VALUES (?, ?, ?, ?)",
                [
                    ("active-newest", active.name, 0, 400),
                    ("active-missing", "active-missing.jsonl", 0, 375),
                    ("active-unavailable", None, 0, 350),
                    ("archived-unavailable", None, 1, 325),
                    ("archived-available", archived.name, 1, 300),
                    ("unknown-middle", unknown.name, "1", 200),
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

        assert ([item.source_availability for item in active_listing.items]) == ([
                SourceAvailability.AVAILABLE,
                SourceAvailability.MISSING,
                SourceAvailability.UNAVAILABLE,
            ])
        assert ([item.thread_id for item in archived_listing.items]) == (["archived-unavailable", "archived-available", "archived-missing"])
        assert ([item.source_availability for item in archived_listing.items]) == ([
                SourceAvailability.UNAVAILABLE,
                SourceAvailability.AVAILABLE,
                SourceAvailability.MISSING,
            ])
        assert ([item.thread_id for item in all_listing.items]) == ([
                "active-newest",
                "active-missing",
                "active-unavailable",
                "archived-unavailable",
                "archived-available",
                "unknown-middle",
                "archived-missing",
            ])
        assert (all_listing.items[5].archive_state) == (ArchiveState.UNKNOWN)

    def test_inventory_recency_fallback_units_ranges_and_display_times_are_exact(
        self,
        inventory_case: InventoryCase,
    ) -> None:
        for name in ("recency", "updated-ms", "seconds", "missing"):
            (inventory_case.root / f"{name}.jsonl").write_text(
                "metadata-only",
                encoding="utf-8",
            )
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
                    ("from-updated-ms", "updated-ms.jsonl", 0, "invalid", 12, "invalid", 6_000),
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

        assert ([item.thread_id for item in listed.items]) == (["from-seconds", "from-updated-ms", "from-recency", "missing-recency"])
        by_id = {item.thread_id: item for item in listed.items}
        assert (by_id["from-recency"].created_at) == ("0")
        assert (by_id["from-recency"].updated_at) == ("11")
        assert (by_id["from-updated-ms"].created_at) is None
        assert (by_id["from-seconds"].created_at) is None
        assert (by_id["from-seconds"].updated_at) == ("7")
        assert (by_id["missing-recency"].updated_at) == (str(sqlite_integer_overflow))

    def test_inventory_omits_invalid_ids_and_ambiguous_duplicates(
        self,
        inventory_case: InventoryCase,
    ) -> None:
        safe_a = inventory_case.root / "safe-a.jsonl"
        safe_b = inventory_case.root / "safe-b.jsonl"
        safe_a.write_text("metadata-only", encoding="utf-8")
        safe_b.write_text("metadata-only", encoding="utf-8")
        rows: list[tuple[object, str, int, int]] = [
            ("", safe_a.name, 0, 270),
            (" leading-space", safe_a.name, 0, 260),
            ("trailing-space ", safe_a.name, 0, 250),
            ("control\nid", safe_a.name, 0, 240),
            ("\u2066format-id", safe_a.name, 0, 230),
            ("x" * (codex_rollout.MAX_THREAD_ID_CHARS + 1), safe_a.name, 0, 220),
            (123, safe_a.name, 0, 210),
            ("duplicate", safe_a.name, 0, 200),
            ("duplicate", safe_b.name, 1, 190),
            ("safe-a", safe_a.name, 0, 20),
            ("safe-b", safe_b.name, 0, 10),
        ]
        with state_database(inventory_case.root) as connection:
            connection.execute(
                "CREATE TABLE threads (id, rollout_path, archived, recency_at_ms INTEGER)"
            )
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
        assert listed.omitted_sources == len(rows) - 2
        assert "duplicate" not in {item.thread_id for item in active.items}
        assert "duplicate" not in {item.thread_id for item in archived.items}

    @pytest.mark.parametrize(
        "unsafe_path_kind",
        [
            pytest.param("escape", id="parent-escape"),
            pytest.param("control", id="control-character"),
            pytest.param("oversize", id="oversize"),
            pytest.param("directory", id="nonregular-directory"),
            pytest.param("final-link", id="final-symlink"),
            pytest.param("parent-link", id="parent-symlink"),
        ],
    )
    def test_inventory_omits_unsafe_paths_before_limit(
        self,
        unsafe_path_kind: str,
        inventory_case: InventoryCase,
    ) -> None:
        safe = inventory_case.root / "safe.jsonl"
        safe.write_text("metadata-only", encoding="utf-8")
        target = inventory_case.root / "link-target.jsonl"
        target.write_text("metadata-only", encoding="utf-8")
        directory = inventory_case.root / "directory"
        directory.mkdir()
        path_by_kind = {
            "escape": "../escape.jsonl",
            "control": "bad\npath.jsonl",
            "oversize": "x" * (codex_rollout.MAX_ROLLOUT_PATH_CHARS + 1),
            "directory": directory.name,
        }
        if unsafe_path_kind == "final-link":
            path = inventory_case.root / "final-link.jsonl"
            try:
                path.symlink_to(target)
            except OSError:
                pytest.skip("symlink creation is unavailable")
            unsafe_path = path.name
        elif unsafe_path_kind == "parent-link":
            parent_target = inventory_case.root / "parent-target"
            parent_target.mkdir()
            (parent_target / "nested.jsonl").write_text(
                "metadata-only",
                encoding="utf-8",
            )
            parent_link = inventory_case.root / "parent-link"
            try:
                parent_link.symlink_to(parent_target, target_is_directory=True)
            except OSError:
                pytest.skip("symlink creation is unavailable")
            unsafe_path = f"{parent_link.name}/nested.jsonl"
        else:
            unsafe_path = path_by_kind[unsafe_path_kind]

        with state_database(inventory_case.root) as connection:
            connection.execute(
                "CREATE TABLE threads (id TEXT, rollout_path TEXT, archived INTEGER, recency_at_ms INTEGER)"
            )
            connection.executemany(
                "INSERT INTO threads VALUES (?, ?, ?, ?)",
                [
                    ("unsafe", unsafe_path, 0, 2_000),
                    ("safe", safe.name, 0, 1_000),
                ],
            )

        listed = inventory_case.list(limit=1)

        assert [item.thread_id for item in listed.items] == ["safe"]
        assert listed.omitted_sources == 1

    def test_inventory_path_open_is_zero_byte_and_denials_are_unavailable(
        self,
        monkeypatch: pytest.MonkeyPatch,
        inventory_case: InventoryCase,
    ) -> None:
        source = inventory_case.root / "source.jsonl"
        source.write_text("private body must not be read", encoding="utf-8")
        prefix = source.name.encode("utf-8")

        read_sizes: list[int] = []

        def zero_byte_read(_descriptor: int, size: int) -> bytes:
            read_sizes.append(size)
            return b""

        with monkeypatch.context() as patched:
            patched.setattr(codex_rollout.os, "read", zero_byte_read)
            available = codex_rollout._inventory_source_availability(
                inventory_case.root,
                "text",
                prefix,
                0,
            )
        assert (available) == (SourceAvailability.AVAILABLE)
        assert (read_sizes[-1]) == (0)

        denied = PermissionError(errno.EACCES, "denied")

        def denied_open(*_args: object, **_kwargs: object) -> int:
            raise denied

        with monkeypatch.context() as patched:
            patched.setattr(codex_rollout.os, "open", denied_open)
            unavailable = codex_rollout._inventory_source_availability(
                inventory_case.root,
                "text",
                prefix,
                0,
            )
        assert (unavailable) == (SourceAvailability.UNAVAILABLE)

    def test_inventory_rejects_reparse_and_descriptor_identity_changes(
        self,
        monkeypatch: pytest.MonkeyPatch,
        inventory_case: InventoryCase,
    ) -> None:
        source = inventory_case.root / "source.jsonl"
        source.write_text("metadata-only", encoding="utf-8")
        prefix = source.name.encode("utf-8")
        actual = source.lstat()
        reparse = SimpleNamespace(
            st_mode=stat.S_IFREG | 0o600,
            st_file_attributes=getattr(
                stat,
                "FILE_ATTRIBUTE_REPARSE_POINT",
                0x400,
            ),
        )
        with monkeypatch.context() as patched:
            patched.setattr(Path, "lstat", lambda _path: reparse)
            assert (codex_rollout._inventory_source_availability(
                inventory_case.root,
                "text",
                prefix,
                0,
            )) is None

        displaced = SimpleNamespace(
            st_mode=actual.st_mode,
            st_dev=actual.st_dev,
            st_ino=actual.st_ino + 1,
            st_file_attributes=0,
        )
        with monkeypatch.context() as patched:
            patched.setattr(
                codex_rollout.os,
                "fstat",
                lambda _descriptor: displaced,
            )
            assert (codex_rollout._inventory_source_availability(
                inventory_case.root,
                "text",
                prefix,
                0,
            )) is None

    def test_inventory_is_bounded_and_filters_before_limit(
        self,
        monkeypatch: pytest.MonkeyPatch,
        inventory_case: InventoryCase,
    ) -> None:
        for name in ("active-new", "active-old", "archived"):
            (inventory_case.root / f"{name}.jsonl").write_text(
                "metadata-only",
                encoding="utf-8",
            )
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
        assert (listing.inventory_truncated)
        item = listing.items[0]
        assert (item.workspace) is None
        assert (item.workspace_truncated)
        assert (item.title) == ("t" * 160)
        assert (item.title_truncated)
        assert (item.first_user_message) == ("m" * 512)
        assert (item.first_user_message_truncated)
        assert (item.created_at) == ("3")
        assert (item.updated_at) == ("4")
        assert (item.recency_at_ms) == (8_000)
        assert (materialized_prefixes) == ([(4_096, 4_097), (160, 161), (512, 513)])

    def test_inventory_preserves_provider_display_controls_without_escaping(
        self,
        inventory_case: InventoryCase,
    ) -> None:
        source = inventory_case.root / "control.jsonl"
        source.write_text("metadata-only", encoding="utf-8")
        title = "title\x00after\n\x1b[31m\u202e"
        first_message = "first\r\nmessage"
        with state_database(inventory_case.root) as connection:
            connection.execute(
                """
                CREATE TABLE threads (
                    id TEXT,
                    rollout_path TEXT,
                    archived INTEGER,
                    cwd TEXT,
                    title TEXT,
                    first_user_message TEXT
                )
                """
            )
            connection.execute(
                "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "thread-control",
                    source.name,
                    0,
                    "/work/project",
                    title,
                    first_message,
                ),
            )

        item = inventory_case.list(limit=1).items[0]

        assert (item.title) == (title)
        assert (item.first_user_message) == (first_message)
        assert not (item.title_truncated)
        assert not (item.first_user_message_truncated)

    def test_inventory_query_reads_only_bounded_display_columns(
        self,
        monkeypatch: pytest.MonkeyPatch,
        inventory_case: InventoryCase,
    ) -> None:
        source = inventory_case.root / "source.jsonl"
        source.write_text("metadata-only", encoding="utf-8")
        raw_connection = sqlite3.connect(":memory:")
        raw_connection.execute(
            """
            CREATE TABLE threads (
                id TEXT,
                rollout_path TEXT,
                archived INTEGER,
                cwd TEXT,
                title TEXT,
                first_user_message TEXT,
                preview TEXT,
                reasoning TEXT,
                tool_payload TEXT
            )
            """
        )
        raw_connection.execute(
            "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "thread-rich",
                source.name,
                0,
                "/work",
                "title",
                "message",
                "private-preview",
                "private-reasoning",
                "private-tool",
            ),
        )
        read_columns: list[str] = []

        def authorize(
            action: int,
            first: str | None,
            second: str | None,
            *_args: object,
        ) -> int:
            if action == sqlite3.SQLITE_READ and second is not None:
                read_columns.append(second)
            return sqlite3.SQLITE_OK

        raw_connection.set_authorizer(authorize)

        class RecordingConnection:
            def execute(self, statement, *args):
                return raw_connection.execute(statement, *args)

            def close(self):
                raw_connection.close()

        recording_connection = RecordingConnection()
        monkeypatch.setattr(
            codex_rollout,
            "_state_connection",
            lambda *_args, **_kwargs: recording_connection,
        )
        listing = inventory_case.list(limit=1)

        assert [item.thread_id for item in listing.items] == ["thread-rich"]
        assert {"cwd", "title", "first_user_message"} <= set(read_columns)
        assert not {"preview", "reasoning", "tool_payload"} & set(read_columns)

    def test_inventory_requires_exact_id_and_rollout_path_columns(
        self,
        inventory_case: InventoryCase,
    ) -> None:
        with state_database(inventory_case.root) as connection:
            connection.execute(
                "CREATE TABLE threads (thread_id TEXT, rolloutPath TEXT)"
            )

        with pytest.raises(SvcError) as raised:
            inventory_case.list()

        assert (raised.value.code) == ("thread-source-incompatible")
