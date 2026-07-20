from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from svc_cli.cli import EXIT_CONFLICT, EXIT_OK, main


class TelemetryCliTests(unittest.TestCase):
    def invoke(self, arguments: list[str]) -> tuple[int, dict[str, object], str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(arguments)
        serialized_stdout = stdout.getvalue()
        serialized_stderr = stderr.getvalue()
        serialized = serialized_stdout or serialized_stderr
        self.assertTrue(
            serialized,
            f"CLI returned {code} without a JSON response "
            f"(stdout characters={len(serialized_stdout)}, stderr characters={len(serialized_stderr)}).",
        )
        payload = json.loads(serialized)
        return code, payload, serialized_stderr

    @staticmethod
    def rollout(path: Path, thread_id: str, message: str) -> None:
        records = (
            {"timestamp": "2026-07-16T00:00:00Z", "type": "session_meta", "payload": {"id": thread_id}},
            {"timestamp": "2026-07-16T00:00:01Z", "type": "response_item", "payload": {"type": "message", "role": "user", "content": message}},
            {"timestamp": "2026-07-16T00:00:02Z", "type": "response_item", "payload": {"type": "reasoning", "encrypted_content": "opaque"}},
            {"timestamp": "2026-07-16T00:00:03Z", "type": "response_item", "payload": {"type": "function_call", "name": "safe"}},
        )
        path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

    def test_export_requires_acknowledgement_then_writes_a_local_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repository"
            root.mkdir()
            source = root / "rollout.jsonl"
            self.rollout(source, "thread-cli", "work in tasks/demo/packet.md")
            packet = root / "tasks" / "demo"
            packet.mkdir(parents=True)
            (packet / "packet.md").write_text("# Demo\n", encoding="utf-8")
            output_directory = Path(tmp) / "exports"
            output_directory.mkdir()
            output = output_directory / "evidence.zip"

            code, blocked, _ = self.invoke(
                ["telemetry", "agent-thread", "export", "--source", str(source), "--output", str(output), "--repo", str(root), "--json"]
            )
            self.assertEqual(code, EXIT_CONFLICT)
            self.assertEqual(blocked["error"]["code"], "sensitive-export-not-acknowledged")
            self.assertFalse(output.exists())

            code, exported, _ = self.invoke(
                [
                    "telemetry",
                    "agent-thread",
                    "export",
                    "--source",
                    str(source),
                    "--output",
                    str(output),
                    "--repo",
                    str(root),
                    "--include-sensitive",
                    "--json",
                ]
            )
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(exported["status"], "exported")
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.read("providers/codex/rollout.jsonl"), source.read_bytes())
                self.assertEqual(archive.read("task-packets/tasks/demo/packet.md"), b"# Demo\n")
                manifest = json.loads(archive.read("manifest.json"))
                self.assertEqual(manifest["thread"]["id"], "thread-cli")
                self.assertEqual(manifest["capabilities"]["reasoning"], "opaque")
                self.assertEqual(manifest["capabilities"]["tool_calls"], "present")

    def test_list_uses_safe_state_metadata_without_reading_transcript_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            source = home / "rollout.jsonl"
            self.rollout(source, "thread-list", "secret task body")
            connection = sqlite3.connect(home / "state_5.sqlite")
            connection.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT, updated_at TEXT)")
            connection.execute("INSERT INTO threads VALUES (?, ?, ?)", ("thread-list", source.name, "2026-07-16"))
            connection.commit()
            connection.close()

            code, payload, serialized_error = self.invoke(
                ["telemetry", "agent-thread", "list", "--codex-home", str(home), "--json"]
            )
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(payload["threads"], [{"provider_id": "codex", "thread_id": "thread-list", "source_state": "active", "created_at": None, "updated_at": "2026-07-16"}])
            self.assertNotIn("warnings", payload)
            self.assertNotIn("secret task body", serialized_error)
            self.assertNotIn("secret task body", json.dumps(payload))

    def test_list_omits_unsafe_rows_with_a_redacted_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            database = home / "state_5.sqlite"
            connection = sqlite3.connect(database)
            connection.execute(
                "CREATE TABLE threads (id TEXT, rollout_path TEXT, title TEXT, cwd TEXT, preview TEXT, message TEXT, reasoning TEXT, tool_payload TEXT)"
            )
            connection.execute(
                "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "private-thread-id",
                    "../private-rollout.jsonl",
                    "private-title",
                    "private-cwd",
                    "private-preview",
                    "private-message",
                    "private-reasoning",
                    "private-tool-payload",
                ),
            )
            connection.commit()
            connection.close()

            code, payload, serialized_error = self.invoke(
                ["telemetry", "agent-thread", "list", "--codex-home", str(home), "--json"]
            )
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(payload["status"], "listed")
            self.assertEqual(payload["threads"], [])
            self.assertEqual(payload["warnings"], [{"code": "thread-source-omitted", "count": 1}])
            serialized = serialized_error + json.dumps(payload)
            for private_value in (
                "private-thread-id",
                "private-rollout.jsonl",
                "private-title",
                "private-cwd",
                "private-preview",
                "private-message",
                "private-reasoning",
                "private-tool-payload",
            ):
                self.assertNotIn(private_value, serialized)

    def test_list_human_output_marks_a_degraded_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            database = home / "state_5.sqlite"
            connection = sqlite3.connect(database)
            connection.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT)")
            connection.execute("INSERT INTO threads VALUES (?, ?)", ("unsafe-thread", "../private-rollout.jsonl"))
            connection.commit()
            connection.close()
            stdout = io.StringIO()
            stderr = io.StringIO()

            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main(["telemetry", "agent-thread", "list", "--codex-home", str(home)])

            self.assertEqual(code, EXIT_OK)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("SVC telemetry agent-thread list: 0 thread(s)", stdout.getvalue())
            self.assertIn("Degraded: 1 source row(s) omitted", stdout.getvalue())
            self.assertNotIn("private-rollout.jsonl", stdout.getvalue())

    def test_list_missing_state_database_remains_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)

            code, payload, serialized_error = self.invoke(
                ["telemetry", "agent-thread", "list", "--codex-home", str(home), "--json"]
            )

            self.assertEqual(code, EXIT_CONFLICT)
            self.assertEqual(payload["error"]["code"], "thread-source-not-found")
            self.assertEqual(payload["error"]["details"], {})
            self.assertNotIn(str(home), serialized_error)

    def test_list_corrupt_state_database_remains_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "state_5.sqlite").write_bytes(b"not-a-sqlite-database")

            code, payload, serialized_error = self.invoke(
                ["telemetry", "agent-thread", "list", "--codex-home", str(home), "--json"]
            )

            self.assertEqual(code, EXIT_CONFLICT)
            self.assertEqual(payload["error"]["code"], "thread-source-incompatible")
            self.assertEqual(payload["error"]["details"], {})
            self.assertNotIn(str(home), serialized_error)


if __name__ == "__main__":
    unittest.main()
