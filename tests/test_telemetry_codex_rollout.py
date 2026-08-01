from __future__ import annotations

import json
import sqlite3
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

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
        _, result, _, records = self.capture(source, bounds)
        return result, records

    def capture(
        self,
        source: Path,
        bounds: dict[str, int] | None = None,
    ) -> tuple[object, object, bytes, list[dict[str, object]]]:
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
        return capture, result, native.getvalue(), records


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
        capture, _, native, records = rollout_case.capture(source)

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
        capture, _, native, records = rollout_case.capture(
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
        capture, _, native, records = rollout_case.capture(
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
        source = rollout_case.source(
            self.envelope("session_meta", {"id": "thread-one"}),
            self.envelope("session_meta", {"id": "thread-two"}),
        )
        with pytest.raises(SvcError) as raised:
            rollout_case.normalize(source)
        assert (raised.value.code) == ("thread-source-incompatible")

    def test_task_references_in_tools_and_reasoning_are_not_eligible(
        self,
        rollout_case: RolloutCase,
    ) -> None:
        source = rollout_case.source(
            self.envelope("session_meta", {"id": "thread-boundary"}),
            self.envelope(
                "response_item",
                {
                    "type": "message",
                    "role": "user",
                    "content": "include tasks/eligible/packet.md",
                },
            ),
            self.envelope(
                "response_item",
                {"type": "reasoning", "summary": "ignore tasks/reasoning/packet.md"},
            ),
            self.envelope(
                "response_item",
                {
                    "type": "function_call",
                    "name": "tool",
                    "call_id": "c",
                    "arguments": "ignore tasks/tool-call/packet.md",
                },
            ),
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

    def test_state_connection_is_a_direct_read_only_transaction(
        self,
        rollout_case: RolloutCase,
    ) -> None:
        db = rollout_case.root / "state_5.sqlite"
        connection = sqlite3.connect(db)
        connection.execute("CREATE TABLE threads (id TEXT)")
        connection.execute("INSERT INTO threads VALUES ('thread-db')")
        connection.commit()
        connection.close()

        readonly = codex_rollout._state_connection(db)
        try:
            assert readonly.in_transaction
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                readonly.execute("INSERT INTO threads VALUES ('mutated')")
        finally:
            readonly.close()

    def test_corrupt_state_database_has_a_structured_error(
        self,
        rollout_case: RolloutCase,
    ) -> None:
        database = rollout_case.root / "state_5.sqlite"
        database.write_bytes(b"not-a-sqlite-database")

        with pytest.raises(SvcError) as raised:
            rollout_case.provider.resolve(
                ProviderContext(home=rollout_case.root),
                ThreadSelection(thread_id="thread-db"),
            )

        assert (raised.value.code) == ("thread-source-incompatible")

    def test_missing_source_has_a_structured_not_found_error(
        self,
        rollout_case: RolloutCase,
    ) -> None:
        source = rollout_case.root / "missing.jsonl"

        with pytest.raises(SvcError) as raised:
            rollout_case.provider.resolve(
                ProviderContext(home=rollout_case.root),
                ThreadSelection(source=source),
            )

        assert raised.value.code == "thread-source-not-found"

    def test_native_capture_declares_descriptor_content_change(
        self,
        rollout_case: RolloutCase,
    ) -> None:
        source = rollout_case.source(
            self.envelope("session_meta", {"id": "thread-mutate"}),
            self.envelope(
                "message",
                {"role": "assistant", "content": "x"},
            ),
        )
        initial = source.read_bytes()

        class TruncatingOutput(BytesIO):
            def write(inner_self, value: bytes) -> int:
                source.write_bytes(initial[:1])
                return super().write(value)

        resolved = rollout_case.provider.resolve(
            ProviderContext(home=rollout_case.root),
            ThreadSelection(source=source),
        )
        output = TruncatingOutput()
        capture = rollout_case.provider.capture_native(resolved, output, {})

        assert output.getvalue() == initial
        assert capture.source_status.value == "changed"
        assert capture.is_partial is True

    def test_native_capture_retains_prefix_when_source_read_is_interrupted(
        self,
        monkeypatch: pytest.MonkeyPatch,
        rollout_case: RolloutCase,
    ) -> None:
        source = rollout_case.source(
            self.envelope("session_meta", {"id": "thread-interrupted"}),
            self.envelope("message", {"role": "assistant", "content": "x"}),
        )
        resolved = rollout_case.provider.resolve(
            ProviderContext(home=rollout_case.root),
            ThreadSelection(source=source),
        )
        original_open = codex_rollout._open_source

        class InterruptedStream:
            def __init__(inner_self, stream) -> None:
                inner_self.stream = stream
                inner_self.reads = 0

            def read(inner_self, size: int) -> bytes:
                inner_self.reads += 1
                if inner_self.reads > 1:
                    raise OSError("fixture interruption")
                return inner_self.stream.read(min(size, 20))

            def fileno(inner_self) -> int:
                return inner_self.stream.fileno()

            def close(inner_self) -> None:
                inner_self.stream.close()

        def interrupted_open(path: Path):
            stream, info = original_open(path)
            return InterruptedStream(stream), info

        monkeypatch.setattr(codex_rollout, "_open_source", interrupted_open)
        output = BytesIO()
        capture = rollout_case.provider.capture_native(resolved, output, {})
        result = rollout_case.provider.stream_normalize_captured(
            resolved,
            output,
            capture,
            lambda _record: True,
            {},
        )

        assert output.getvalue() == source.read_bytes()[:20]
        assert capture.read_interrupted is True
        assert capture.unknown_remainder is True
        assert capture.frames[-1]["frame_status"] == "incomplete"
        assert result.lossiness["partial_reasons"]["input_limit"] == 0
        diagnostic_codes = {item["code"] for item in result.diagnostics}
        assert "source-read-interrupted" in diagnostic_codes
        assert "input-limit-reached" not in diagnostic_codes
