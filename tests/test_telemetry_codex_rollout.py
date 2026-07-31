from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from svc_cli.errors import SvcError
from svc_cli.telemetry.agent_threads import (
    ProviderContext,
    ThreadSelection,
)
from svc_cli.telemetry.providers import CodexRolloutProvider
from svc_cli.telemetry.providers import codex_rollout


@dataclass(frozen=True)
class RolloutCase:
    root: Path
    provider: CodexRolloutProvider

    def source(self, *records: dict[str, object], trailing_newline: bool = True) -> Path:
        path = self.root / "rollout.jsonl"
        text = "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
        path.write_text(text + ("\n" if trailing_newline else ""), encoding="utf-8")
        return path

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
        self.provider.stream_normalize_captured(
            resolved,
            native,
            capture,
            lambda record: records.append(dict(record)) or True,
            bounds or {},
        )
        return capture, native.getvalue(), records


@pytest.fixture
def rollout_case() -> Iterator[RolloutCase]:
    with tempfile.TemporaryDirectory() as tmp:
        yield RolloutCase(root=Path(tmp), provider=CodexRolloutProvider())


class TestCodexRolloutProvider:
    @staticmethod
    def envelope(record_type: str, payload: object, timestamp: str = "2026-01-01T00:00:00Z") -> dict[str, object]:
        return {"timestamp": timestamp, "type": record_type, "payload": payload}

    def test_native_capture_exactly_frames_original_bytes_and_binds_projection(
        self,
        rollout_case: RolloutCase,
    ) -> None:
        source = rollout_case.source(
            self.envelope("session_meta", {"id": "thread-capture"}),
            self.envelope(
                "response_item",
                {"type": "message", "role": "user", "content": "raw"},
            ),
            trailing_newline=False,
        )
        capture, native, records = rollout_case.capture(source)

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
        rollout_case: RolloutCase,
    ) -> None:
        source = rollout_case.source(
            self.envelope("session_meta", {"id": "thread-cut"}),
            self.envelope(
                "response_item",
                {"type": "message", "role": "assistant", "content": "later"},
            ),
        )
        first_line = source.read_bytes().find(b"\n") + 1
        limit = first_line + 12
        capture, native, records = rollout_case.capture(
            source,
            {"source_bytes": limit},
        )

        assert len(native) == limit
        assert capture.unknown_remainder is True
        assert capture.frames[-1]["frame_status"] == "incomplete"
        assert capture.frames[-1]["byte_end"] == limit
        assert [record["type"] for record in records] == ["meta"]

    def test_projection_line_limit_does_not_remove_large_native_frame(
        self,
        rollout_case: RolloutCase,
    ) -> None:
        source = rollout_case.source(
            self.envelope("session_meta", {"id": "thread-large"}),
            self.envelope(
                "response_item",
                {"type": "message", "role": "user", "content": "x" * 256},
            ),
        )
        capture, native, records = rollout_case.capture(
            source,
            {"native_line_bytes": 80},
        )

        assert native == source.read_bytes()
        assert capture.frames[1]["frame_status"] == "complete"
        assert capture.frames[1]["byte_end"] - capture.frames[1]["byte_start"] > 80
        assert [record["type"] for record in records] == ["meta"]

    def test_native_capture_freezes_initial_extent_and_declares_source_growth(
        self,
        rollout_case: RolloutCase,
    ) -> None:
        source = rollout_case.source(
            self.envelope("session_meta", {"id": "thread-growth"}),
            self.envelope(
                "response_item",
                {"type": "message", "role": "user", "content": "initial"},
            ),
        )
        initial = source.read_bytes()

        class GrowingOutput(BytesIO):
            def __init__(inner_self) -> None:
                super().__init__()
                inner_self.grew = False

            def write(inner_self, value: bytes) -> int:
                if not inner_self.grew:
                    with source.open("ab") as appended:
                        appended.write(b'{"type":"late"}\n')
                    inner_self.grew = True
                return super().write(value)

        resolved = rollout_case.provider.resolve(
            ProviderContext(home=rollout_case.root),
            ThreadSelection(source=source),
        )
        output = GrowingOutput()
        capture = rollout_case.provider.capture_native(resolved, output, {})

        assert output.getvalue() == initial
        assert capture.source_status.value == "grew"
        assert capture.is_partial is True
        assert capture.unknown_remainder is False

    @pytest.mark.parametrize(
        ("payload", "record_type", "expected"),
        [
            pytest.param(
                {"type": "message", "role": "user", "content": "hello"},
                "message",
                {"role": "user", "content": "hello"},
                id="message-content",
            ),
            pytest.param(
                {"type": "reasoning", "summary": "bounded summary"},
                "reasoning",
                {"reasoning_kind": "summary", "content": "bounded summary"},
                id="reasoning-summary",
            ),
            pytest.param(
                {
                    "type": "function_call",
                    "name": "safe",
                    "call_id": "c1",
                    "arguments": {"x": 1},
                },
                "tool_call",
                {"name": "safe", "arguments": '{"x":1}'},
                id="tool-call-fields",
            ),
        ],
    )
    def test_codex_native_field_paths_map_to_canonical_records(
        self,
        payload: dict[str, object],
        record_type: str,
        expected: dict[str, str],
        rollout_case: RolloutCase,
    ) -> None:
        source = rollout_case.source(
            self.envelope(
                "session_meta",
                {"id": "thread-fields", "cwd": "/work/project"},
            ),
            self.envelope("response_item", payload),
        )

        result, records = rollout_case.normalize(source)

        assert result.result_status.value == "ready"
        assert records[0]["workspace"]["label"] == "project"
        projected = records[1]
        assert projected["type"] == record_type
        for key, value in expected.items():
            assert projected[key] == value

    @pytest.mark.parametrize(
        ("malformed_position", "expected_types"),
        [
            pytest.param("middle", ["meta", "message"], id="middle-line"),
            pytest.param("final", ["meta"], id="final-line"),
        ],
    )
    def test_malformed_record_is_dropped_with_partial_loss(
        self,
        malformed_position: str,
        expected_types: list[str],
        rollout_case: RolloutCase,
    ) -> None:
        lines = [
            json.dumps(self.envelope("session_meta", {"id": "thread-malformed"})),
        ]
        if malformed_position == "middle":
            lines.extend(
                [
                    "{not-json}",
                    json.dumps(
                        self.envelope(
                            "response_item",
                            {
                                "type": "message",
                                "role": "assistant",
                                "content": "finished",
                            },
                        )
                    ),
                ]
            )
        else:
            lines.append("{not-json}")
        source = rollout_case.root / f"malformed-{malformed_position}.jsonl"
        source.write_bytes(("\n".join(lines) + "\n").encode())

        result, records = rollout_case.normalize(source)

        assert result.result_status.value == "partial"
        assert result.lossiness["dropped"]["invalid_json"] == 1
        assert [record["type"] for record in records] == expected_types

    def test_conflicting_session_metadata_is_rejected(
        self,
        rollout_case: RolloutCase,
    ) -> None:
        source = rollout_case.source(self.envelope("session_meta", {"id": "thread-one"}), self.envelope("session_meta", {"id": "thread-two"}))
        with pytest.raises(SvcError, match="conflicting session metadata") as raised:
            rollout_case.normalize(source)
        assert (raised.value.code) == ("thread-source-incompatible")

    def test_task_references_in_tools_and_reasoning_are_not_eligible(
        self,
        rollout_case: RolloutCase,
    ) -> None:
        source = rollout_case.source(
            self.envelope("session_meta", {"id": "thread-boundary"}),
            self.envelope("response_item", {"type": "message", "role": "user", "content": "include tasks/eligible/packet.md"}),
            self.envelope("response_item", {"type": "reasoning", "summary": "ignore tasks/reasoning/packet.md"}),
            self.envelope("response_item", {"type": "function_call", "name": "tool", "call_id": "c", "arguments": "ignore tasks/tool-call/packet.md"}),
        )
        _, records = rollout_case.normalize(source)
        assert (records[1]["task_refs"]) == (["tasks/eligible/packet.md"])

    def test_exact_state_resolution_uses_id_and_defers_rollout_projection(
        self,
        rollout_case: RolloutCase,
    ) -> None:
        source = rollout_case.source(
            self.envelope("session_meta", {"id": "thread-db"}),
            self.envelope("message", {"role": "user", "content": "private"}),
        )
        database = rollout_case.root / "state_5.sqlite"
        connection = sqlite3.connect(database)
        connection.execute(
            "CREATE TABLE threads (id TEXT, rollout_path TEXT, created_at INTEGER, updated_at INTEGER, archived INTEGER)"
        )
        connection.execute(
            "INSERT INTO threads VALUES (?, ?, ?, ?, ?)",
            ("thread-db", source.name, 1, 2, 0),
        )
        connection.commit()
        connection.close()

        resolved = rollout_case.provider.resolve(
            ProviderContext(home=rollout_case.root),
            ThreadSelection(thread_id="thread-db"),
        )

        assert resolved.thread_id == "thread-db"
        assert resolved.source_path == source
        assert not (rollout_case.root / "state_5.sqlite-wal").exists()
        assert not (rollout_case.root / "state_5.sqlite-shm").exists()

    def test_state_snapshot_includes_rollback_journal(
        self,
        rollout_case: RolloutCase,
    ) -> None:
        db = rollout_case.root / "snapshot.sqlite"
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
        rollout_case: RolloutCase,
    ) -> None:
        database = rollout_case.root / "corrupt.sqlite"
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

    @pytest.mark.parametrize(
        ("source_kind", "message_fragment"),
        [
            pytest.param("symlink", "symlink", id="symlink"),
            pytest.param("directory", "regular file", id="directory"),
        ],
    )
    def test_symlink_and_nonregular_sources_are_rejected(
        self,
        source_kind: str,
        message_fragment: str,
        rollout_case: RolloutCase,
    ) -> None:
        target = rollout_case.source(self.envelope("session_meta", {"id": "thread-safe"}))
        if source_kind == "symlink":
            source = rollout_case.root / "link.jsonl"
            try:
                source.symlink_to(target)
            except OSError:
                pytest.skip("symlink creation is unavailable")
        else:
            source = rollout_case.root / "directory.jsonl"
            source.mkdir()

        with pytest.raises(SvcError, match=message_fragment) as raised:
            rollout_case.provider.resolve(
                ProviderContext(home=rollout_case.root),
                ThreadSelection(source=source),
            )
        assert raised.value.code == "thread-source-unsafe"

    def test_native_source_read_error_has_a_stable_provider_code(
        self,
        rollout_case: RolloutCase,
    ) -> None:
        class FailingStream:
            def readline(self, _limit: int) -> bytes:
                raise OSError("fixture read failure")

        with pytest.raises(SvcError, match="cannot be read") as raised:
            codex_rollout._readline(FailingStream(), 1024, rollout_case.root / "rollout.jsonl")  # type: ignore[arg-type]
        assert (raised.value.code) == ("thread-source-unreadable")

    def test_source_replacement_during_capture_is_detected(
        self,
        rollout_case: RolloutCase,
    ) -> None:
        source = rollout_case.source(self.envelope("session_meta", {"id": "thread-mutate"}), self.envelope("message", {"role": "assistant", "content": "x"}))
        resolved = rollout_case.provider.resolve(ProviderContext(home=rollout_case.root), ThreadSelection(source=source))

        def sink(record: dict[str, object]) -> bool:
            replacement = rollout_case.root / "replacement.jsonl"
            replacement.write_bytes(source.read_bytes())
            os.replace(replacement, source)
            return True

        result = rollout_case.provider.stream_normalize(resolved, sink, {})
        assert result.source_status.value == "displaced"
        assert result.result_status.value == "partial"
        assert result.lossiness["partial_reasons"]["source_displaced"] == 1
