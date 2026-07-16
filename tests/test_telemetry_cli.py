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
        payload = json.loads(stdout.getvalue()) if stdout.getvalue() else json.loads(stderr.getvalue())
        return code, payload, stderr.getvalue()

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
            self.assertNotIn("secret task body", serialized_error)
            self.assertNotIn("secret task body", json.dumps(payload))

    def test_list_failure_redacts_provider_local_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            database = home / "state_5.sqlite"
            connection = sqlite3.connect(database)
            connection.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT)")
            connection.execute("INSERT INTO threads VALUES (?, ?)", ("thread-outside", "/private/not-a-rollout.jsonl"))
            connection.commit()
            connection.close()

            code, payload, serialized_error = self.invoke(
                ["telemetry", "agent-thread", "list", "--codex-home", str(home), "--json"]
            )
            self.assertEqual(code, EXIT_CONFLICT)
            self.assertEqual(payload["error"]["code"], "thread-source-unsafe")
            self.assertEqual(payload["error"]["details"], {})
            self.assertNotIn("/private/not-a-rollout.jsonl", serialized_error)


if __name__ == "__main__":
    unittest.main()
