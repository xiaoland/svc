from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from svc_cli.errors import SvcError
from svc_cli.telemetry.agent_threads import ProviderContext, ThreadSelection
from svc_cli.telemetry.providers import CodexRolloutProvider
from svc_cli.telemetry.providers import codex_rollout


class CodexRolloutProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.provider = CodexRolloutProvider()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def source(self, *records: dict[str, object], trailing_newline: bool = True) -> Path:
        path = self.root / "rollout.jsonl"
        text = "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
        path.write_text(text + ("\n" if trailing_newline else ""), encoding="utf-8")
        return path

    @staticmethod
    def envelope(record_type: str, payload: object, timestamp: str = "2026-01-01T00:00:00Z") -> dict[str, object]:
        return {"timestamp": timestamp, "type": record_type, "payload": payload}

    def test_explicit_source_preserves_bytes_and_indexes_without_payloads(self) -> None:
        source = self.source(
            self.envelope("session_meta", {"id": "thread-1"}),
            self.envelope("message", {"role": "user", "content": "hello tasks/v10/packet.md"}),
            self.envelope("reasoning", {"encrypted_content": "opaque-secret"}),
            self.envelope("reasoning", {"summary": "safe summary"}),
            self.envelope("custom_tool_call", {"arguments": "do-not-copy-to-index"}),
            self.envelope("function_output", {"output": "do-not-copy-to-index"}),
            self.envelope("future_record", {"unknown": "value"}),
        )
        resolved = self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(source=source))
        raw, index = BytesIO(), BytesIO()
        evidence = self.provider.stream_capture(resolved, raw, index)

        self.assertEqual(raw.getvalue(), source.read_bytes())
        indexed = json.loads(index.getvalue())
        self.assertNotIn("payload", indexed)
        self.assertEqual([record["type"] for record in indexed["records"]], ["session_meta", "message", "reasoning", "reasoning", "custom_tool_call", "function_output", "future_record"])
        self.assertEqual(evidence.capabilities["reasoning"], "opaque")
        self.assertEqual(evidence.capabilities["tool_calls"], "present")
        self.assertEqual([occurrence.text for occurrence in evidence.occurrences], ["tasks/v10/packet.md"])
        self.assertEqual(resolved.artifact.archive_path, "rollout.jsonl")

    def test_malformed_nonfinal_record_is_retained_with_a_warning(self) -> None:
        source = self.root / "malformed-middle.jsonl"
        source.write_bytes(
            (
                json.dumps(self.envelope("session_meta", {"id": "thread-middle"}))
                + "\n{not-json}\n"
                + json.dumps(self.envelope("message", {"role": "assistant", "content": "finished"}))
                + "\n"
            ).encode("utf-8")
        )
        resolved = self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(source=source))
        raw, index = BytesIO(), BytesIO()
        evidence = self.provider.stream_capture(resolved, raw, index)
        self.assertEqual(raw.getvalue(), source.read_bytes())
        self.assertEqual(evidence.record_counts["malformed"], 1)
        self.assertIn("malformed-record", [warning.code for warning in evidence.warnings])

    def test_oversized_unknown_record_is_retained_streamingly(self) -> None:
        source = self.source(
            self.envelope("session_meta", {"id": "thread-large"}),
            self.envelope(
                "future_record",
                {"blob": "x" * (codex_rollout.MAX_INDEX_RECORD_BYTES * 2 + 257)},
            ),
        )
        resolved = self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(source=source))
        raw, index = BytesIO(), BytesIO()
        evidence = self.provider.stream_capture(resolved, raw, index)
        self.assertEqual(raw.getvalue(), source.read_bytes())
        self.assertGreater(evidence.source_bytes, 8 * 1024 * 1024)
        self.assertIn("record-too-large", [warning.code for warning in evidence.warnings])
        self.assertEqual(json.loads(index.getvalue())["records"][-1]["type"], "oversize")

    def test_task_references_in_tools_and_reasoning_are_not_eligible(self) -> None:
        source = self.source(
            self.envelope("session_meta", {"id": "thread-boundary"}),
            self.envelope("message", {"role": "user", "content": "include tasks/eligible/packet.md"}),
            self.envelope("reasoning", {"summary": "ignore tasks/reasoning/packet.md"}),
            self.envelope("function_call", {"arguments": "ignore tasks/tool-call/packet.md"}),
            self.envelope("function_output", {"output": "ignore tasks/tool-output/packet.md"}),
        )
        resolved = self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(source=source))
        evidence = self.provider.stream_capture(resolved, BytesIO(), BytesIO())
        self.assertEqual([item.text for item in evidence.occurrences], ["tasks/eligible/packet.md"])

    def test_response_item_payload_types_are_classified(self) -> None:
        source = self.source(
            self.envelope("session_meta", {"id": "thread-response"}),
            self.envelope("response_item", {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "nested tasks/packet.md"}]}),
            self.envelope("response_item", {"type": "reasoning", "encrypted_content": "opaque"}),
            self.envelope("response_item", {"type": "function_call", "name": "tool"}),
        )
        resolved = self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(source=source))
        evidence = self.provider.stream_capture(resolved, BytesIO(), BytesIO())
        self.assertEqual(evidence.capabilities["messages"], "present")
        self.assertEqual(evidence.capabilities["reasoning"], "opaque")
        self.assertEqual(evidence.capabilities["tool_calls"], "present")
        self.assertEqual([item.text for item in evidence.occurrences], ["tasks/packet.md"])

    def test_agent_message_event_is_eligible_for_lexical_task_association(self) -> None:
        source = self.source(
            self.envelope("session_meta", {"id": "thread-agent-message"}),
            self.envelope("event_msg", {"type": "agent_message", "message": "see tasks/v10/40-export-agent-thread/packet.md。"}),
        )
        resolved = self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(source=source))
        evidence = self.provider.stream_capture(resolved, BytesIO(), BytesIO())
        self.assertEqual(evidence.capabilities["messages"], "present")
        self.assertEqual([item.text for item in evidence.occurrences], ["tasks/v10/40-export-agent-thread/packet.md"])
        self.assertEqual(evidence.occurrences[0].field_path, "payload.message")

    def test_conflicting_session_metadata_is_rejected_during_source_resolution(self) -> None:
        source = self.source(
            self.envelope("session_meta", {"id": "thread-one"}),
            self.envelope("session_meta", {"id": "thread-two"}),
        )
        with self.assertRaisesRegex(SvcError, "conflicting session metadata") as raised:
            self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(source=source))
        self.assertEqual(raised.exception.code, "thread-source-incompatible")

    def test_conflicting_session_metadata_is_rejected_during_capture(self) -> None:
        source = self.source(self.envelope("session_meta", {"id": "thread-one"}))
        resolved = self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(source=source))
        source.write_bytes(
            (json.dumps(self.envelope("session_meta", {"id": "thread-one"})) + "\n"
             + json.dumps(self.envelope("session_meta", {"id": "thread-two"})) + "\n").encode()
        )
        with self.assertRaisesRegex(SvcError, "conflicting session metadata") as raised:
            self.provider.stream_capture(resolved, BytesIO(), BytesIO())
        self.assertEqual(raised.exception.code, "thread-source-incompatible")

    def test_task_candidates_are_bounded_and_overlong_candidates_warn(self) -> None:
        overlong = "tasks/" + ("x" * codex_rollout.MAX_TASK_CANDIDATE_CHARS)
        source = self.source(
            self.envelope("session_meta", {"id": "thread-bounded"}),
            self.envelope("message", {"role": "user", "content": f"keep tasks/short/packet.md drop {overlong}"}),
        )
        resolved = self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(source=source))
        evidence = self.provider.stream_capture(resolved, BytesIO(), BytesIO())
        self.assertEqual([item.text for item in evidence.occurrences], ["tasks/short/packet.md"])
        warning = next(item for item in evidence.warnings if item.code == "task-candidate-too-long")
        self.assertEqual(warning.details["max_chars"], codex_rollout.MAX_TASK_CANDIDATE_CHARS)
        self.assertEqual(warning.details["candidate_chars"], len(overlong))

    def test_occurrence_cap_is_reported(self) -> None:
        records = [self.envelope("session_meta", {"id": "thread-cap"})]
        records.extend(
            self.envelope("message", {"role": "user", "content": f"tasks/{index}/packet.md"})
            for index in range(codex_rollout.MAX_OCCURRENCES + 1)
        )
        source = self.source(*records)
        resolved = self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(source=source))
        evidence = self.provider.stream_capture(resolved, BytesIO(), BytesIO())
        self.assertEqual(len(evidence.occurrences), codex_rollout.MAX_OCCURRENCES)
        warning = next(item for item in evidence.warnings if item.code == "occurrences-truncated")
        self.assertEqual(warning.details["suppressed"], 1)

    def test_list_and_exact_state_resolution_are_metadata_only(self) -> None:
        source = self.source(self.envelope("session_meta", {"id": "thread-db"}), self.envelope("message", {"role": "user", "content": "private"}))
        db = self.root / "state_5.sqlite"
        connection = sqlite3.connect(db)
        connection.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT, created_at TEXT, updated_at TEXT, state TEXT)")
        connection.execute("INSERT INTO threads VALUES (?, ?, ?, ?, ?)", ("thread-db", source.name, "1", "2", "active"))
        connection.commit()
        connection.close()
        listed = self.provider.list_metadata(ProviderContext(home=self.root), 5)
        self.assertEqual(listed.descriptors[0].thread_id, "thread-db")
        self.assertEqual(listed.descriptors[0].created_at, "1")
        self.assertEqual(listed.omitted_sources, 0)
        self.assertFalse((self.root / "state_5.sqlite-wal").exists())
        self.assertFalse((self.root / "state_5.sqlite-shm").exists())
        resolved = self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(thread_id="thread-db"))
        self.assertEqual(resolved.thread_id, "thread-db")
        self.assertFalse((self.root / "state_5.sqlite-wal").exists())
        self.assertFalse((self.root / "state_5.sqlite-shm").exists())

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
            self.assertEqual((snapshot.parent / journal.name).read_bytes(), b"journal-fixture")
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_state_snapshot_identity_ignores_windows_ctime_read_noise(self) -> None:
        before = SimpleNamespace(st_dev=1, st_ino=2, st_size=3, st_mtime_ns=4, st_ctime_ns=5)
        after = SimpleNamespace(st_dev=1, st_ino=2, st_size=3, st_mtime_ns=4, st_ctime_ns=999)
        self.assertEqual(codex_rollout._state_signature(before), codex_rollout._state_signature(after))

    def test_state_connection_closes_a_connection_rejected_by_sqlite(self) -> None:
        database = self.root / "corrupt.sqlite"
        database.write_bytes(b"not-a-sqlite-database")
        connection = MagicMock()
        connection.execute.side_effect = sqlite3.DatabaseError("not a database")

        with patch.object(codex_rollout.sqlite3, "connect", return_value=connection):
            with self.assertRaises(SvcError) as raised:
                codex_rollout._state_connection(database)

        self.assertEqual(raised.exception.code, "thread-source-incompatible")
        connection.close.assert_called_once_with()

    def test_list_marks_a_missing_rollout_without_scanning_or_failing_all_metadata(self) -> None:
        db = self.root / "state_5.sqlite"
        connection = sqlite3.connect(db)
        connection.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT, updated_at TEXT)")
        connection.execute("INSERT INTO threads VALUES (?, ?, ?)", ("thread-missing", "sessions/missing.jsonl", "2"))
        connection.commit()
        connection.close()

        listed = self.provider.list_metadata(ProviderContext(home=self.root), 5)
        self.assertEqual(listed.descriptors[0].thread_id, "thread-missing")
        self.assertEqual(listed.descriptors[0].source_state, "missing")

    def test_list_is_metadata_only_and_defers_rollout_signature_to_export(self) -> None:
        source = self.root / "not-a-rollout.jsonl"
        source.write_text("private non-rollout body", encoding="utf-8")
        db = self.root / "state_5.sqlite"
        connection = sqlite3.connect(db)
        connection.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT)")
        connection.execute("INSERT INTO threads VALUES (?, ?)", ("thread-metadata-only", source.name))
        connection.commit()
        connection.close()

        listed = self.provider.list_metadata(ProviderContext(home=self.root), 5)
        self.assertEqual(listed.descriptors[0].thread_id, "thread-metadata-only")
        with self.assertRaises(SvcError) as raised:
            self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(thread_id="thread-metadata-only"))
        self.assertEqual(raised.exception.code, "thread-source-incompatible")

    def test_list_omits_unsafe_rows_without_spending_the_safe_result_limit(self) -> None:
        recent = self.root / "recent.jsonl"
        older = self.root / "older.jsonl"
        recent.write_text("metadata-only", encoding="utf-8")
        older.write_text("metadata-only", encoding="utf-8")
        database = self.root / "state_5.sqlite"
        connection = sqlite3.connect(database)
        connection.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT, updated_at TEXT)")
        connection.executemany(
            "INSERT INTO threads VALUES (?, ?, ?)",
            [
                ("unsafe-leading", "../escaped.jsonl", "4"),
                ("unresolvable-leading", "\x00unresolvable.jsonl", "3"),
                ("safe-recent", recent.name, "2"),
                ("safe-older", older.name, "1"),
            ],
        )
        connection.commit()
        connection.close()

        listed = self.provider.list_metadata(ProviderContext(home=self.root), 2)

        self.assertEqual([item.thread_id for item in listed.descriptors], ["safe-recent", "safe-older"])
        self.assertEqual(listed.omitted_sources, 2)
        with self.assertRaises(SvcError) as raised:
            self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(thread_id="unsafe-leading"))
        self.assertEqual(raised.exception.code, "thread-source-unsafe")

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

        listed = self.provider.list_metadata(ProviderContext(home=self.root), 1)

        self.assertEqual(listed.descriptors, ())
        self.assertEqual(listed.omitted_sources, 2)

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

        listed = self.provider.list_metadata(ProviderContext(home=self.root), 2)

        self.assertEqual([item.thread_id for item in listed.descriptors], ["alpha-safe", "zulu-safe"])
        self.assertEqual(listed.omitted_sources, 1)

    def test_symlink_and_nonregular_sources_are_rejected(self) -> None:
        target = self.source(self.envelope("session_meta", {"id": "thread-safe"}))
        link = self.root / "link.jsonl"
        link.symlink_to(target)
        with self.assertRaisesRegex(SvcError, "symlink") as raised:
            self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(source=link))
        self.assertEqual(raised.exception.code, "thread-source-unsafe")

    def test_native_source_read_error_has_a_stable_provider_code(self) -> None:
        class FailingStream:
            def readline(self, _limit: int) -> bytes:
                raise OSError("fixture read failure")

        with self.assertRaisesRegex(SvcError, "cannot be read") as raised:
            codex_rollout._readline(FailingStream(), 1024, self.root / "rollout.jsonl")  # type: ignore[arg-type]
        self.assertEqual(raised.exception.code, "thread-source-unreadable")

    def test_malformed_final_record_is_refused(self) -> None:
        source = self.root / "malformed.jsonl"
        source.write_bytes(
            (json.dumps(self.envelope("session_meta", {"id": "thread-bad"})) + "\n" + "{not-json}\n").encode()
        )
        resolved = self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(source=self.source(self.envelope("session_meta", {"id": "thread-bad"}))))
        resolved = resolved.__class__(resolved.provider_id, resolved.adapter_id, resolved.source_format, resolved.thread_id, resolved.source_state, resolved.artifact.__class__(source, resolved.artifact.archive_path, resolved.artifact.media_type))
        with self.assertRaisesRegex(SvcError, "malformed") as raised:
            self.provider.stream_capture(resolved, BytesIO(), BytesIO())
        self.assertEqual(raised.exception.code, "thread-source-mutated")

    def test_source_replacement_during_capture_is_detected(self) -> None:
        source = self.source(self.envelope("session_meta", {"id": "thread-mutate"}), self.envelope("message", {"role": "assistant", "content": "x"}))
        resolved = self.provider.resolve(ProviderContext(home=self.root), ThreadSelection(source=source))

        class MutatingSink(BytesIO):
            def write(inner, data: bytes) -> int:  # type: ignore[override]
                result = super().write(data)
                if source.exists():
                    source.touch()
                return result

        with self.assertRaisesRegex(SvcError, "changed during capture"):
            self.provider.stream_capture(resolved, MutatingSink(), BytesIO())


if __name__ == "__main__":
    unittest.main()
