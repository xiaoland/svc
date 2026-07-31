from __future__ import annotations

import errno
import json
import os
import shutil
import sqlite3
import stat
import tempfile
import pytest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

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


class TestCodexRolloutProvider:
    @pytest.fixture(autouse=True, scope="function")
    def _rollout_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.root = Path(temporary)
            self.provider = CodexRolloutProvider()
            yield

    def source(self, *records: dict[str, object], trailing_newline: bool = True) -> Path:
        path = self.root / "rollout.jsonl"
        text = "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
        path.write_text(text + ("\n" if trailing_newline else ""), encoding="utf-8")
        return path

    def inventory(
        self,
        *,
        limit: int = 20,
        archive_state: ArchiveFilter = ArchiveFilter.ALL,
    ):
        return self.provider.list_inventory(
            ProviderContext(home=self.root),
            ThreadInventoryQuery(archive_state=archive_state, limit=limit),
        )

    @staticmethod
    def envelope(record_type: str, payload: object, timestamp: str = "2026-01-01T00:00:00Z") -> dict[str, object]:
        return {"timestamp": timestamp, "type": record_type, "payload": payload}

    def normalize(self, source: Path, bounds: dict[str, int] | None = None) -> tuple[object, list[dict[str, object]]]:
        resolved = self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(source=source))
        records: list[dict[str, object]] = []
        result = self.provider.stream_normalize(resolved, lambda record: records.append(dict(record)) or True, bounds or {})
        return result, records

    def capture(
        self,
        source: Path,
        bounds: dict[str, int] | None = None,
    ) -> tuple[object, bytes, list[dict[str, object]]]:
        resolved = self.provider.resolve(
            ProviderContext(home=self.root),
            ThreadSelection(source=source),
        )
        native = BytesIO()
        capture = self.provider.capture_native(
            resolved,
            native,
            bounds or {},
        )
        records: list[dict[str, object]] = []
        result = self.provider.stream_normalize_captured(
            resolved,
            native,
            capture,
            lambda record: records.append(dict(record)) or True,
            bounds or {},
        )
        return capture, native.getvalue(), records

    def test_native_capture_exactly_frames_original_bytes_and_binds_projection(
        self,
    ) -> None:
        source = self.source(
            self.envelope("session_meta", {"id": "thread-capture"}),
            self.envelope(
                "response_item",
                {"type": "message", "role": "user", "content": "raw"},
            ),
            trailing_newline=False,
        )
        capture, native, records = self.capture(source)

        assert native == source.read_bytes()
        assert capture.unknown_remainder is False
        assert [frame["frame_status"] for frame in capture.frames] == [
            "complete",
            "complete",
        ]
        assert capture.frames[0]["byte_start"] == 0
        assert capture.frames[-1]["byte_end"] == len(native)
        assert records[0]["type"] == "meta"
        assert "native_record_id" not in records[0]["source_ref"]
        assert records[1]["source_ref"]["native_record_id"] == "n000001"

    def test_acquisition_cut_retains_one_readable_incomplete_final_frame(
        self,
    ) -> None:
        source = self.source(
            self.envelope("session_meta", {"id": "thread-cut"}),
            self.envelope(
                "response_item",
                {"type": "message", "role": "assistant", "content": "later"},
            ),
        )
        first_line = source.read_bytes().find(b"\n") + 1
        limit = first_line + 12
        capture, native, records = self.capture(
            source,
            {"source_bytes": limit},
        )

        assert len(native) == limit
        assert capture.unknown_remainder is True
        assert capture.frames[-1]["frame_status"] == "incomplete"
        assert capture.frames[-1]["byte_end"] == limit
        assert [record["type"] for record in records] == ["meta"]

    def test_projection_line_limit_does_not_remove_large_native_frame(self) -> None:
        source = self.source(
            self.envelope("session_meta", {"id": "thread-large"}),
            self.envelope(
                "response_item",
                {"type": "message", "role": "user", "content": "x" * 256},
            ),
        )
        capture, native, records = self.capture(
            source,
            {"native_line_bytes": 80},
        )

        assert native == source.read_bytes()
        assert capture.frames[1]["frame_status"] == "complete"
        assert capture.frames[1]["byte_end"] - capture.frames[1]["byte_start"] > 80
        assert [record["type"] for record in records] == ["meta"]

    def test_native_capture_freezes_initial_extent_and_declares_source_growth(
        self,
    ) -> None:
        source = self.source(
            self.envelope("session_meta", {"id": "thread-growth"}),
            self.envelope(
                "response_item",
                {"type": "message", "role": "user", "content": "initial"},
            ),
        )
        initial = source.read_bytes()

        class GrowingOutput(BytesIO):
            grew = False

            def write(inner_self, value: bytes) -> int:
                if not inner_self.grew:
                    with source.open("ab") as appended:
                        appended.write(b'{"type":"late"}\n')
                    inner_self.grew = True
                return super().write(value)

        resolved = self.provider.resolve(
            ProviderContext(home=self.root),
            ThreadSelection(source=source),
        )
        output = GrowingOutput()
        capture = self.provider.capture_native(resolved, output, {})

        assert output.getvalue() == initial
        assert capture.source_status.value == "grew"
        assert capture.is_partial is True
        assert capture.unknown_remainder is False

    def test_codex_native_field_paths_map_to_canonical_records(self) -> None:
        source = self.source(
            self.envelope("session_meta", {"id": "thread-1", "cwd": "/work/project"}),
            self.envelope("response_item", {"type": "message", "role": "user", "content": "hello"}),
            self.envelope("response_item", {"type": "reasoning", "summary": "bounded summary"}),
            self.envelope("response_item", {"type": "function_call", "name": "safe", "call_id": "c1", "arguments": {"x": 1}}),
            self.envelope("response_item", {"type": "function_call_output", "call_id": "c1", "status": "success", "output": "ok"}),
        )
        result, records = self.normalize(source)
        assert (result.result_status.value) == ("ready")
        assert ([record["type"] for record in records]) == (["meta", "message", "reasoning", "tool_call", "tool_result"])
        assert (records[0]["workspace"]["label"]) == ("project")
        assert ((records[1]["role"], records[1]["content"])) == (("user", "hello"))
        assert ((records[2]["reasoning_kind"], records[2]["content"])) == (("summary", "bounded summary"))
        assert ((records[3]["name"], records[3]["arguments"])) == (("safe", '{"x":1}'))
        assert (records[4]["tool_call_id"]) == (records[3]["tool_call_id"])
        assert ((records[4]["status"], records[4]["content"], records[4]["link_status"])) == (("success", "ok", "linked"))

    def test_malformed_record_is_dropped_with_partial_loss(self) -> None:
        source = self.root / "malformed-middle.jsonl"
        source.write_bytes((json.dumps(self.envelope("session_meta", {"id": "thread-middle"})) + "\n{not-json}\n" + json.dumps(self.envelope("response_item", {"type": "message", "role": "assistant", "content": "finished"})) + "\n").encode())
        result, records = self.normalize(source)
        assert (result.result_status.value) == ("partial")
        assert (result.lossiness["dropped"]["invalid_json"]) > (0)
        assert ([record["type"] for record in records]) == (["meta", "message"])

    def test_response_item_types_map_to_reasoning_and_tool_records(self) -> None:
        source = self.source(
            self.envelope("session_meta", {"id": "thread-response"}),
            self.envelope("response_item", {"type": "message", "role": "assistant", "content": "nested"}),
            self.envelope("response_item", {"type": "reasoning", "summary": "summary"}),
            self.envelope("response_item", {"type": "function_call", "name": "tool", "call_id": "c"}),
        )
        result, records = self.normalize(source)
        assert (result.capabilities["reasoning"]) == ("summary")
        assert (result.capabilities["tool_linkage"]) == ("explicit")
        assert ([record["type"] for record in records]) == (["meta", "message", "reasoning", "tool_call"])

    def test_conflicting_session_metadata_is_rejected(self) -> None:
        source = self.source(self.envelope("session_meta", {"id": "thread-one"}), self.envelope("session_meta", {"id": "thread-two"}))
        with pytest.raises(SvcError, match="conflicting session metadata") as raised:
            self.normalize(source)
        assert (raised.value.code) == ("thread-source-incompatible")

    def test_task_references_in_tools_and_reasoning_are_not_eligible(self) -> None:
        source = self.source(
            self.envelope("session_meta", {"id": "thread-boundary"}),
            self.envelope("response_item", {"type": "message", "role": "user", "content": "include tasks/eligible/packet.md"}),
            self.envelope("response_item", {"type": "reasoning", "summary": "ignore tasks/reasoning/packet.md"}),
            self.envelope("response_item", {"type": "function_call", "name": "tool", "call_id": "c", "arguments": "ignore tasks/tool-call/packet.md"}),
        )
        _, records = self.normalize(source)
        assert (records[1]["task_refs"]) == (["tasks/eligible/packet.md"])

    def test_list_and_exact_state_resolution_are_metadata_only(self) -> None:
        source = self.source(self.envelope("session_meta", {"id": "thread-db"}), self.envelope("message", {"role": "user", "content": "private"}))
        db = self.root / "state_5.sqlite"
        connection = sqlite3.connect(db)
        connection.execute(
            "CREATE TABLE threads (id TEXT, rollout_path TEXT, created_at INTEGER, updated_at INTEGER, archived INTEGER)"
        )
        connection.execute("INSERT INTO threads VALUES (?, ?, ?, ?, ?)", ("thread-db", source.name, 1, 2, 0))
        connection.commit()
        connection.close()
        listed = self.inventory(limit=5)
        assert (listed.items[0].thread_id) == ("thread-db")
        assert (listed.items[0].archive_state) == (ArchiveState.ACTIVE)
        assert (listed.items[0].created_at) == ("1")
        assert (listed.omitted_sources) == (0)
        assert not ((self.root / "state_5.sqlite-wal").exists())
        assert not ((self.root / "state_5.sqlite-shm").exists())
        resolved = self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(thread_id="thread-db"))
        assert (resolved.thread_id) == ("thread-db")
        assert not ((self.root / "state_5.sqlite-wal").exists())
        assert not ((self.root / "state_5.sqlite-shm").exists())

    def test_state_snapshot_includes_rollback_journal(self) -> None:
        db = self.root / "snapshot.sqlite"
        connection = sqlite3.connect(db)
        connection.execute("CREATE TABLE threads (id TEXT)")
        connection.commit()
        connection.close()
        journal = Path(f"{db}-journal")
        journal.write_bytes(b"journal-fixture")
        snapshot, directory = codex_rollout._state_snapshot(db)
        try:
            assert ((snapshot.parent / journal.name).read_bytes()) == (b"journal-fixture")
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_state_snapshot_identity_ignores_windows_ctime_read_noise(self) -> None:
        before = SimpleNamespace(st_dev=1, st_ino=2, st_size=3, st_mtime_ns=4, st_ctime_ns=5)
        after = SimpleNamespace(st_dev=1, st_ino=2, st_size=3, st_mtime_ns=4, st_ctime_ns=999)
        assert (codex_rollout._state_signature(before)) == (codex_rollout._state_signature(after))

    def test_state_connection_closes_a_connection_rejected_by_sqlite(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        database = self.root / "corrupt.sqlite"
        database.write_bytes(b"not-a-sqlite-database")

        class RejectedConnection:
            def __init__(self) -> None:
                self.close_calls = 0

            def execute(self, *_args: object) -> None:
                raise sqlite3.DatabaseError("not a database")

            def close(self) -> None:
                self.close_calls += 1

        connection = RejectedConnection()
        monkeypatch.setattr(
            codex_rollout.sqlite3,
            "connect",
            lambda *_args, **_kwargs: connection,
        )

        with pytest.raises(SvcError) as raised:
            codex_rollout._state_connection(database)

        assert (raised.value.code) == ("thread-source-incompatible")
        assert (connection.close_calls) == (1)

    def test_list_marks_a_missing_rollout_without_scanning_or_failing_all_metadata(self) -> None:
        db = self.root / "state_5.sqlite"
        connection = sqlite3.connect(db)
        connection.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT, updated_at INTEGER)")
        connection.execute("INSERT INTO threads VALUES (?, ?, ?)", ("thread-missing", "sessions/missing.jsonl", "2"))
        connection.commit()
        connection.close()

        listed = self.inventory(limit=5)
        assert (listed.items[0].thread_id) == ("thread-missing")
        assert (listed.items[0].archive_state) == (ArchiveState.UNKNOWN)
        assert (listed.items[0].source_availability) == (SourceAvailability.MISSING)

    def test_list_is_metadata_only_and_defers_rollout_signature_to_export(self) -> None:
        source = self.root / "not-a-rollout.jsonl"
        source.write_text("private non-rollout body", encoding="utf-8")
        db = self.root / "state_5.sqlite"
        connection = sqlite3.connect(db)
        connection.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT)")
        connection.execute("INSERT INTO threads VALUES (?, ?)", ("thread-metadata-only", source.name))
        connection.commit()
        connection.close()

        listed = self.inventory(limit=5)
        assert (listed.items[0].thread_id) == ("thread-metadata-only")
        with pytest.raises(SvcError) as raised:
            self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(thread_id="thread-metadata-only"))
        assert (raised.value.code) == ("thread-source-incompatible")

    def test_list_omits_unsafe_rows_without_spending_the_safe_result_limit(self) -> None:
        recent = self.root / "recent.jsonl"
        older = self.root / "older.jsonl"
        recent.write_text("metadata-only", encoding="utf-8")
        older.write_text("metadata-only", encoding="utf-8")
        database = self.root / "state_5.sqlite"
        connection = sqlite3.connect(database)
        connection.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT, updated_at INTEGER)")
        connection.executemany(
            "INSERT INTO threads VALUES (?, ?, ?)",
            [
                ("unsafe-leading", "../escaped.jsonl", 4),
                ("unresolvable-leading", "\x00unresolvable.jsonl", 3),
                ("safe-recent", recent.name, 2),
                ("safe-older", older.name, 1),
            ],
        )
        connection.commit()
        connection.close()

        listed = self.inventory(limit=2)

        assert ([item.thread_id for item in listed.items]) == (["safe-recent", "safe-older"])
        assert (listed.omitted_sources) == (2)
        with pytest.raises(SvcError) as raised:
            self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(thread_id="unsafe-leading"))
        assert (raised.value.code) == ("thread-source-unsafe")

    def test_list_reports_an_all_unsafe_inventory_as_degraded(self) -> None:
        database = self.root / "state_5.sqlite"
        connection = sqlite3.connect(database)
        connection.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT, updated_at TEXT)")
        connection.executemany(
            "INSERT INTO threads VALUES (?, ?, ?)",
            [
                ("unsafe-newer", "../escaped-newer.jsonl", "2"),
                ("unsafe-older", "../escaped-older.jsonl", "1"),
            ],
        )
        connection.commit()
        connection.close()

        listed = self.inventory(limit=1)

        assert (listed.items) == (())
        assert (listed.omitted_sources) == (2)

    def test_list_uses_stable_descriptor_order_when_timestamps_tie(self) -> None:
        alpha = self.root / "alpha.jsonl"
        zulu = self.root / "zulu.jsonl"
        alpha.write_text("metadata-only", encoding="utf-8")
        zulu.write_text("metadata-only", encoding="utf-8")
        database = self.root / "state_5.sqlite"
        connection = sqlite3.connect(database)
        connection.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT, updated_at TEXT)")
        connection.executemany(
            "INSERT INTO threads VALUES (?, ?, ?)",
            [
                ("zulu-safe", zulu.name, "same-time"),
                ("middle-unsafe", "../escaped.jsonl", "same-time"),
                ("alpha-safe", alpha.name, "same-time"),
            ],
        )
        connection.commit()
        connection.close()

        listed = self.inventory(limit=2)

        assert ([item.thread_id for item in listed.items]) == (["alpha-safe", "zulu-safe"])
        assert (listed.omitted_sources) == (1)

    def test_inventory_filters_lifecycle_before_limit_and_keeps_availability_independent(self) -> None:
        active = self.root / "active.jsonl"
        archived = self.root / "archived.jsonl"
        unknown = self.root / "unknown.jsonl"
        active.write_text("metadata-only", encoding="utf-8")
        archived.write_text("metadata-only", encoding="utf-8")
        unknown.write_text("metadata-only", encoding="utf-8")
        database = self.root / "state_5.sqlite"
        connection = sqlite3.connect(database)
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
        connection.commit()
        connection.close()

        active_listing = self.inventory(limit=3, archive_state=ArchiveFilter.ACTIVE)
        archived_listing = self.inventory(limit=3, archive_state=ArchiveFilter.ARCHIVED)
        all_listing = self.inventory(limit=10)

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

    def test_inventory_recency_fallback_units_ranges_and_display_times_are_exact(self) -> None:
        for name in ("recency", "updated-ms", "seconds", "missing"):
            (self.root / f"{name}.jsonl").write_text("metadata-only", encoding="utf-8")
        database = self.root / "state_5.sqlite"
        connection = sqlite3.connect(database)
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
                    codex_rollout._MAX_RECENCY_SECONDS + 1,
                    None,
                    None,
                ),
            ],
        )
        connection.commit()
        connection.close()

        listed = self.inventory()

        assert ([item.thread_id for item in listed.items]) == (["from-seconds", "from-updated-ms", "from-recency", "missing-recency"])
        by_id = {item.thread_id: item for item in listed.items}
        assert (by_id["from-recency"].created_at) == ("0")
        assert (by_id["from-recency"].updated_at) == ("11")
        assert (by_id["from-updated-ms"].created_at) is None
        assert (by_id["from-seconds"].created_at) is None
        assert (by_id["from-seconds"].updated_at) == ("7")
        assert (by_id["missing-recency"].updated_at) == (str(codex_rollout._MAX_RECENCY_SECONDS + 1))

    def test_inventory_omits_invalid_ids_ambiguous_duplicates_and_unsafe_paths(self) -> None:
        safe_a = self.root / "safe-a.jsonl"
        safe_b = self.root / "safe-b.jsonl"
        link_target = self.root / "link-target.jsonl"
        for path in (safe_a, safe_b, link_target):
            path.write_text("metadata-only", encoding="utf-8")
        directory = self.root / "directory"
        directory.mkdir()
        final_link = self.root / "final-link.jsonl"
        parent_target = self.root / "parent-target"
        parent_target.mkdir()
        (parent_target / "nested.jsonl").write_text("metadata-only", encoding="utf-8")
        parent_link = self.root / "parent-link"
        links_available = True
        try:
            final_link.symlink_to(link_target)
            parent_link.symlink_to(parent_target, target_is_directory=True)
        except OSError:
            links_available = False

        rows: list[tuple[object, object, object, int]] = [
            ("bad-leading", "../escape.jsonl", 0, 300),
            ("bad-control-path", "bad\npath.jsonl", 0, 290),
            ("bad-long-path", "x" * (codex_rollout.MAX_ROLLOUT_PATH_CHARS + 1), 0, 280),
            ("", safe_a.name, 0, 270),
            (" leading-space", safe_a.name, 0, 260),
            ("trailing-space ", safe_a.name, 0, 250),
            ("control\nid", safe_a.name, 0, 240),
            ("\u2066format-id", safe_a.name, 0, 230),
            ("x" * (codex_rollout.MAX_THREAD_ID_CHARS + 1), safe_a.name, 0, 220),
            (123, safe_a.name, 0, 210),
            ("duplicate", safe_a.name, 0, 200),
            ("duplicate", safe_b.name, 1, 190),
            ("directory-path", directory.name, 0, 180),
            ("safe-a", safe_a.name, 0, 20),
            ("safe-b", safe_b.name, 0, 10),
        ]
        if links_available:
            rows.extend(
                [
                    ("final-link", final_link.name, 0, 170),
                    ("parent-link", f"{parent_link.name}/nested.jsonl", 0, 160),
                ]
            )
        database = self.root / "state_5.sqlite"
        connection = sqlite3.connect(database)
        connection.execute(
            "CREATE TABLE threads (id, rollout_path, archived, recency_at_ms INTEGER)"
        )
        connection.executemany("INSERT INTO threads VALUES (?, ?, ?, ?)", rows)
        connection.commit()
        connection.close()

        listed = self.inventory(limit=2)
        active = self.inventory(limit=20, archive_state=ArchiveFilter.ACTIVE)
        archived = self.inventory(limit=20, archive_state=ArchiveFilter.ARCHIVED)

        assert ([item.thread_id for item in listed.items]) == (["safe-a", "safe-b"])
        assert (listed.omitted_sources) == (len(rows) - 2)
        assert ("duplicate") not in ({item.thread_id for item in active.items})
        assert ("duplicate") not in ({item.thread_id for item in archived.items})

    def test_inventory_path_open_is_zero_byte_and_denials_are_unavailable(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        source = self.root / "source.jsonl"
        source.write_text("private body must not be read", encoding="utf-8")
        prefix = source.name.encode("utf-8")

        read_sizes: list[int] = []

        def zero_byte_read(_descriptor: int, size: int) -> bytes:
            read_sizes.append(size)
            return b""

        with monkeypatch.context() as patched:
            patched.setattr(codex_rollout.os, "read", zero_byte_read)
            available = codex_rollout._inventory_source_availability(
                self.root,
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
                self.root,
                "text",
                prefix,
                0,
            )
        assert (unavailable) == (SourceAvailability.UNAVAILABLE)

    def test_inventory_rejects_reparse_and_descriptor_identity_changes(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        source = self.root / "source.jsonl"
        source.write_text("metadata-only", encoding="utf-8")
        prefix = source.name.encode("utf-8")
        actual = source.lstat()
        reparse = SimpleNamespace(
            st_mode=stat.S_IFREG | 0o600,
            st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400),
        )
        with monkeypatch.context() as patched:
            patched.setattr(Path, "lstat", lambda _path: reparse)
            assert (codex_rollout._inventory_source_availability(self.root, "text", prefix, 0)) is None

        displaced = SimpleNamespace(
            st_mode=actual.st_mode,
            st_dev=actual.st_dev,
            st_ino=actual.st_ino + 1,
            st_file_attributes=0,
        )
        with monkeypatch.context() as patched:
            patched.setattr(codex_rollout.os, "fstat", lambda _descriptor: displaced)
            assert (codex_rollout._inventory_source_availability(self.root, "text", prefix, 0)) is None

    def test_inventory_is_bounded_and_filters_before_limit(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        for name in ("active-new", "active-old", "archived"):
            (self.root / f"{name}.jsonl").write_text(
                "metadata-only",
                encoding="utf-8",
            )
        database = self.root / "state_5.sqlite"
        connection = sqlite3.connect(database)
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
        connection.commit()
        connection.close()

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
        listing = self.inventory(
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

    def test_inventory_preserves_controls_for_paint_only_escaping(
        self,
    ) -> None:
        source = self.root / "control.jsonl"
        source.write_text("metadata-only", encoding="utf-8")
        title = "title\x00after\n\x1b[31m\u202e"
        first_message = "first\r\nmessage"
        database = self.root / "state_5.sqlite"
        connection = sqlite3.connect(database)
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
        connection.commit()
        connection.close()

        item = self.inventory(limit=1).items[0]

        assert (item.title) == (title)
        assert (item.first_user_message) == (first_message)
        assert not (item.title_truncated)
        assert not (item.first_user_message_truncated)

    def test_inventory_omits_invalid_sources_before_its_limit(self) -> None:
        recent = self.root / "recent.jsonl"
        older = self.root / "older.jsonl"
        recent.write_text("metadata-only", encoding="utf-8")
        older.write_text("metadata-only", encoding="utf-8")
        database = self.root / "state_5.sqlite"
        connection = sqlite3.connect(database)
        connection.execute(
            """
            CREATE TABLE threads (
                id TEXT,
                rollout_path TEXT,
                archived INTEGER,
                recency_at_ms INTEGER,
                cwd TEXT,
                title TEXT,
                first_user_message TEXT
            )
            """
        )
        connection.executemany(
            "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "unsafe",
                    "../escape.jsonl",
                    0,
                    3_000,
                    "/unsafe",
                    "unsafe-title",
                    "unsafe-message",
                ),
                (
                    "recent",
                    recent.name,
                    0,
                    2_000,
                    "/recent",
                    "recent-title",
                    "recent-message",
                ),
                (
                    "older",
                    older.name,
                    0,
                    1_000,
                    "/older",
                    "older-title",
                    "older-message",
                ),
            ],
        )
        connection.commit()
        connection.close()

        listing = self.inventory(limit=1)

        assert ([item.thread_id for item in listing.items]) == (["recent"])
        assert (listing.omitted_sources) == (1)
        assert (listing.inventory_truncated)

    def test_inventory_query_selects_only_bounded_display_columns(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        source = self.root / "source.jsonl"
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
        queries: list[str] = []

        class RecordingConnection:
            def execute(self, statement, *args):
                queries.append(str(statement))
                return raw_connection.execute(statement, *args)

            def close(self):
                raw_connection.close()

        recording_connection = RecordingConnection()
        monkeypatch.setattr(
            codex_rollout,
            "_state_connection",
            lambda *_args, **_kwargs: recording_connection,
        )
        listing = codex_rollout._inventory_rows(
            self.root,
            ThreadInventoryQuery(limit=1),
        )

        assert ([item.thread_id for item in listing.items]) == (["thread-rich"])
        sql = next(
            statement
            for statement in queries
            if "WITH inventory" in statement
        )
        for required in ("cwd", "title", "first_user_message"):
            assert (required) in (sql)
        for forbidden in ("preview", "reasoning", "tool_payload"):
            assert (forbidden) not in (sql)

    def test_inventory_requires_exact_id_and_rollout_path_columns(self) -> None:
        database = self.root / "state_5.sqlite"
        connection = sqlite3.connect(database)
        connection.execute("CREATE TABLE threads (thread_id TEXT, rolloutPath TEXT)")
        connection.commit()
        connection.close()

        with pytest.raises(SvcError) as raised:
            self.inventory()

        assert (raised.value.code) == ("thread-source-incompatible")

    def test_symlink_and_nonregular_sources_are_rejected(self) -> None:
        target = self.source(self.envelope("session_meta", {"id": "thread-safe"}))
        link = self.root / "link.jsonl"
        link.symlink_to(target)
        with pytest.raises(SvcError, match="symlink") as raised:
            self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(source=link))
        assert (raised.value.code) == ("thread-source-unsafe")

    def test_native_source_read_error_has_a_stable_provider_code(self) -> None:
        class FailingStream:
            def readline(self, _limit: int) -> bytes:
                raise OSError("fixture read failure")

        with pytest.raises(SvcError, match="cannot be read") as raised:
            codex_rollout._readline(FailingStream(), 1024, self.root / "rollout.jsonl")  # type: ignore[arg-type]
        assert (raised.value.code) == ("thread-source-unreadable")

    def test_malformed_final_record_is_refused(self) -> None:
        source = self.root / "malformed.jsonl"
        source.write_bytes(
            (json.dumps(self.envelope("session_meta", {"id": "thread-bad"})) + "\n" + "{not-json}\n").encode()
        )
        result, records = self.normalize(source)
        assert (result.result_status.value) == ("partial")
        assert (result.lossiness["dropped"]["invalid_json"]) > (0)
        assert (len(records)) == (1)

    def test_source_replacement_during_capture_is_detected(self) -> None:
        source = self.source(self.envelope("session_meta", {"id": "thread-mutate"}), self.envelope("message", {"role": "assistant", "content": "x"}))
        resolved = self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(source=source))

        def sink(record: dict[str, object]) -> bool:
            source.touch()
            return True

        result = self.provider.stream_normalize(resolved, sink, {})
        assert (result.source_status.value) == ("changed")
        assert (result.result_status.value) == ("partial")
