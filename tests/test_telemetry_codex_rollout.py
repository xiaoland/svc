from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Mapping

import pytest

from svc_cli.errors import SvcError
from svc_cli.telemetry.agent_threads import ProviderContext, ThreadSelection
from svc_cli.telemetry.archive import write_agent_thread_evidence
from svc_cli.telemetry.evidence import ValidatedEvidence, validate_evidence
from svc_cli.telemetry.providers import CodexRolloutProvider
from svc_cli.telemetry.providers import codex_rollout


@dataclass(frozen=True)
class RolloutCase:
    root: Path
    provider: CodexRolloutProvider

    @staticmethod
    def envelope(
        record_type: str,
        payload: object,
        timestamp: str = "2026-01-01T00:00:00Z",
    ) -> dict[str, object]:
        return {"timestamp": timestamp, "type": record_type, "payload": payload}

    def source(
        self,
        *records: dict[str, object],
        name: str = "rollout.jsonl",
        trailing_newline: bool = True,
    ) -> Path:
        path = self.root / name
        text = "\n".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            for record in records
        )
        path.write_text(
            text + ("\n" if trailing_newline else ""),
            encoding="utf-8",
        )
        return path

    def resolve(self, source: Path):
        return self.provider.resolve(
            ProviderContext(home=self.root),
            ThreadSelection(source=source),
        )

    def capture(
        self,
        source: Path,
        bounds: Mapping[str, int] | None = None,
        output: BytesIO | None = None,
    ):
        resolved = self.resolve(source)
        native = output or BytesIO()
        capture = self.provider.capture_native(resolved, native, bounds or {})
        return resolved, capture, native

    def project(
        self,
        resolved,
        capture,
        native: BytesIO,
        bounds: Mapping[str, int] | None = None,
    ):
        records: list[dict[str, Any]] = []
        result = self.provider.stream_normalize_captured(
            resolved,
            native,
            capture,
            lambda record: records.append(dict(record)) or True,
            bounds or {},
        )
        return result, records

    def export(self, source: Path, name: str = "evidence.zip") -> ValidatedEvidence:
        output = self.root / name
        write_agent_thread_evidence(
            self.provider,
            ProviderContext(home=self.root),
            ThreadSelection(source=source),
            output,
        )
        return validate_evidence(output)


@pytest.fixture
def rollout_case(tmp_path: Path) -> RolloutCase:
    return RolloutCase(tmp_path, CodexRolloutProvider())


class MutatingOutput(BytesIO):
    def __init__(self, mutate: Callable[[], None]) -> None:
        super().__init__()
        self.mutate = mutate
        self.mutated = False

    def write(self, value: bytes) -> int:
        if not self.mutated:
            self.mutate()
            self.mutated = True
        return super().write(value)


def meta(thread_id: str) -> dict[str, object]:
    return RolloutCase.envelope("session_meta", {"id": thread_id})


def response(kind: str, **payload: object) -> dict[str, object]:
    return RolloutCase.envelope("response_item", {"type": kind, **payload})


class TestCodexRolloutProvider:
    def test_public_pipeline_preserves_descriptor_native_index_and_projection(
        self,
        rollout_case: RolloutCase,
    ) -> None:
        source = rollout_case.source(
            meta("thread-capture"),
            response("message", role="user", content="raw"),
            trailing_newline=False,
        )

        resolved, capture, native = rollout_case.capture(source)
        native_bytes = native.getvalue()

        assert (
            resolved.provider_id,
            resolved.adapter_id,
            resolved.source_format,
            resolved.thread_id,
            resolved.source_path,
        ) == (
            "codex",
            "codex-rollout-v1",
            "rollout-v1",
            "thread-capture",
            source,
        )
        assert native_bytes == source.read_bytes()
        assert capture.native_bytes == len(native_bytes)
        assert capture.unknown_remainder is False
        assert [frame["frame_status"] for frame in capture.frames] == [
            "complete",
            "complete",
        ]
        assert [
            (frame["native_record_id"], frame["byte_start"], frame["byte_end"])
            for frame in capture.frames
        ] == [
            ("n000000", 0, native_bytes.find(b"\n") + 1),
            ("n000001", native_bytes.find(b"\n") + 1, len(native_bytes)),
        ]

        evidence = rollout_case.export(source)

        assert evidence.native == native_bytes
        assert [entry.as_dict() for entry in evidence.native_index] == [
            dict(frame) for frame in capture.frames
        ]
        assert [record["type"] for record in evidence.trajectory.records] == [
            "meta",
            "message",
        ]
        assert (
            evidence.trajectory.records[1]["source_ref"]["native_record_id"]
            == "n000001"
        )
        assert evidence.manifest["capture"] == {
            "status": "complete",
            "unknown_remainder": False,
            "representation": "provider-bytes",
        }
        assert evidence.manifest["native_index"]["records"] == 2

    def test_acquisition_cut_keeps_exact_prefix_and_declares_partial_projection(
        self,
        rollout_case: RolloutCase,
    ) -> None:
        source = rollout_case.source(
            meta("thread-cut"),
            response("message", role="assistant", content="later"),
        )
        source_bytes = source.read_bytes()
        limit = source_bytes.find(b"\n") + 13

        resolved, capture, native = rollout_case.capture(
            source,
            {"source_bytes": limit},
        )
        result, records = rollout_case.project(
            resolved,
            capture,
            native,
            {"source_bytes": limit},
        )

        assert native.getvalue() == source_bytes[:limit]
        assert capture.unknown_remainder
        assert capture.frames[-1]["frame_status"] == "incomplete"
        assert capture.frames[-1]["byte_end"] == limit
        assert [record["type"] for record in records] == ["meta"]
        assert result.result_status.value == "partial"
        assert result.lossiness["partial_reasons"]["input_limit"] == 1
        assert {item["code"] for item in result.diagnostics} >= {"input-limit-reached"}

    def test_descriptor_capture_reports_growth_and_content_change(
        self,
        rollout_case: RolloutCase,
    ) -> None:
        observed: list[tuple[str, bool, str, int]] = []
        for name, mutation in (
            ("grew", "append"),
            ("changed", "truncate"),
        ):
            source = rollout_case.source(
                meta(f"thread-{name}"),
                response("message", role="assistant", content="initial"),
                name=f"{name}.jsonl",
            )
            initial = source.read_bytes()

            def mutate_source(
                *,
                path: Path = source,
                initial_bytes: bytes = initial,
                mode: str = mutation,
            ) -> None:
                if mode == "append":
                    with path.open("ab") as stream:
                        stream.write(b'{"type":"late"}\n')
                else:
                    path.write_bytes(initial_bytes[:1])

            resolved, capture, native = rollout_case.capture(
                source,
                output=MutatingOutput(mutate_source),
            )
            result, _ = rollout_case.project(resolved, capture, native)
            observed.append(
                (
                    capture.source_status.value,
                    native.getvalue() == initial,
                    result.result_status.value,
                    result.lossiness["partial_reasons"][f"source_{name}"],
                )
            )

        assert observed == [
            ("grew", True, "partial", 1),
            ("changed", True, "partial", 1),
        ]

    def test_interrupted_read_retains_prefix_without_claiming_input_limit(
        self,
        monkeypatch: pytest.MonkeyPatch,
        rollout_case: RolloutCase,
    ) -> None:
        source = rollout_case.source(
            meta("thread-interrupted"),
            response("message", role="assistant", content="x"),
        )
        original_open = codex_rollout._open_source
        resolved = rollout_case.resolve(source)

        class InterruptedStream:
            def __init__(self, stream) -> None:
                self.stream = stream
                self.reads = 0

            def read(self, size: int) -> bytes:
                self.reads += 1
                if self.reads > 1:
                    raise OSError("fixture interruption")
                return self.stream.read(min(size, 20))

            def fileno(self) -> int:
                return self.stream.fileno()

            def close(self) -> None:
                self.stream.close()

        def interrupted_open(path: Path):
            stream, info = original_open(path)
            return InterruptedStream(stream), info

        monkeypatch.setattr(codex_rollout, "_open_source", interrupted_open)

        native = BytesIO()
        capture = rollout_case.provider.capture_native(resolved, native, {})
        result, _ = rollout_case.project(resolved, capture, native)

        assert native.getvalue() == source.read_bytes()[:20]
        assert capture.read_interrupted
        assert capture.unknown_remainder
        assert capture.frames[-1]["frame_status"] == "incomplete"
        assert result.lossiness["partial_reasons"]["source_read_interrupted"] == 1
        assert result.lossiness["partial_reasons"]["input_limit"] == 0
        assert {item["code"] for item in result.diagnostics} >= {
            "source-read-interrupted"
        }
        assert "input-limit-reached" not in {
            item["code"] for item in result.diagnostics
        }

    def test_public_resolution_and_projection_report_identity_conflicts(
        self,
        rollout_case: RolloutCase,
    ) -> None:
        conflict = rollout_case.source(
            meta("thread-one"),
            meta("thread-two"),
            name="conflict.jsonl",
        )
        resolved, capture, native = rollout_case.capture(conflict)
        with pytest.raises(SvcError) as raised:
            rollout_case.project(resolved, capture, native)
        assert raised.value.code == "thread-source-incompatible"

        selected = rollout_case.source(
            meta("actual-thread"),
            name="selected.jsonl",
        )
        database = sqlite3.connect(rollout_case.root / "state_5.sqlite")
        try:
            with database:
                database.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT)")
                database.execute(
                    "INSERT INTO threads VALUES (?, ?)",
                    ("selected-thread", selected.name),
                )
        finally:
            database.close()

        with pytest.raises(SvcError) as raised:
            rollout_case.provider.resolve(
                ProviderContext(home=rollout_case.root),
                ThreadSelection(thread_id="selected-thread"),
            )
        assert raised.value.code == "thread-source-incompatible"

        with pytest.raises(SvcError) as raised:
            rollout_case.resolve(rollout_case.root / "missing.jsonl")
        assert raised.value.code == "thread-source-not-found"
