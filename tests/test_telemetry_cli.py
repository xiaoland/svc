from __future__ import annotations

import io
import builtins
import json
import sqlite3
import tempfile
import pytest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from svc_cli.cli import EXIT_CONFLICT, EXIT_OK, main
from svc_cli.telemetry.agent_threads import (
    ArchiveFilter,
    ArchiveState,
    SourceAvailability,
    ThreadInventoryItem,
    ThreadInventoryListing,
)


class TestTelemetryCli:
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
            assert (code) == (EXIT_CONFLICT)
            assert (blocked["error"]["code"]) == ("sensitive-export-not-acknowledged")
            assert not (output.exists())

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
            assert (code) == (EXIT_OK)
            assert (exported["status"]) == ("exported")
            assert (exported["bundle"]["path"]) == (str(output))
            assert (exported["result_status"]) == ("ready")
            with zipfile.ZipFile(output) as archive:
                assert (archive.namelist()) == (["manifest.json", "trajectory.jsonl"])
                manifest = json.loads(archive.read("manifest.json"))
                trajectory = archive.read("trajectory.jsonl")
                assert (trajectory) != (source.read_bytes())
                assert (b"# Demo") not in (trajectory)
                assert (b"encrypted_content") not in (trajectory)
                assert (b"thread-cli") not in (archive.read("manifest.json"))
                assert (manifest["source"]["thread_ref"].startswith("thread_"))
                assert (manifest["capabilities"]["reasoning"]) == ("opaque")
                assert (manifest["capabilities"]["tool_linkage"]) == ("synthesized")

    def test_export_failure_redacts_source_and_output_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            root.mkdir()
            private_source = root / "PRIVATE_SOURCE_SENTINEL.jsonl"
            private_output = (
                Path(temporary)
                / "PRIVATE_MISSING_PARENT_SENTINEL"
                / "PRIVATE_OUTPUT_SENTINEL.zip"
            )

            code, payload, serialized_error = self.invoke(
                [
                    "telemetry",
                    "agent-thread",
                    "export",
                    "--source",
                    str(private_source),
                    "--output",
                    str(private_output),
                    "--repo",
                    str(root),
                    "--include-sensitive",
                    "--json",
                ]
            )

        assert (code) == (EXIT_CONFLICT)
        assert (payload["error"]["code"]) == ("invalid-export-request")
        assert (payload["error"]["details"]) == ({})
        serialized = serialized_error + json.dumps(payload)
        assert ("PRIVATE_SOURCE_SENTINEL") not in (serialized)
        assert ("PRIVATE_MISSING_PARENT_SENTINEL") not in (serialized)
        assert ("PRIVATE_OUTPUT_SENTINEL") not in (serialized)

    def test_analyze_json_is_provider_independent_and_matches_direct_input(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            root.mkdir()
            source = root / "rollout.jsonl"
            self.rollout(
                source,
                "thread-analysis",
                "work in tasks/demo/packet.md",
            )
            output_directory = Path(temporary) / "exports"
            output_directory.mkdir()
            output = output_directory / "evidence.zip"
            export_code, _, _ = self.invoke(
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
            assert (export_code) == (EXIT_OK)

            direct_code, direct, _ = self.invoke(
                [
                    "telemetry",
                    "agent-thread",
                    "analyze",
                    "--source",
                    str(source),
                    "--json",
                ]
            )
            source.unlink()
            original_import = builtins.__import__

            def reject_textual(name, *args, **kwargs):
                if name == "textual" or name.startswith("textual."):
                    raise AssertionError(
                        "analyze --json must not import Textual"
                    )
                return original_import(name, *args, **kwargs)

            with monkeypatch.context() as patched:
                patched.setattr(builtins, "__import__", reject_textual)
                bundle_code, bundled, _ = self.invoke(
                    [
                        "telemetry",
                        "agent-thread",
                        "analyze",
                        "--input",
                        str(output),
                        "--json",
                    ]
                )

        assert (direct_code) == (EXIT_OK)
        assert (bundle_code) == (EXIT_OK)
        assert (direct) == (bundled)
        assert (set(bundled)) == ({
                "format",
                "schema_version",
                "bundle_id",
                "analyzer",
                "result_status",
                "dimensions",
                "metrics",
                "findings",
                "unknowns",
                "lossiness",
            })
        assert (list(bundled["dimensions"])) == (sorted(bundled["dimensions"]))

    @pytest.mark.parametrize(
        ("arguments", "expected_code"),
        (
            (
                [
                    "telemetry",
                    "agent-thread",
                    "analyze",
                    "--json",
                ],
                "invalid-analysis-request",
            ),
            (
                [
                    "telemetry",
                    "agent-thread",
                    "analyze",
                    "--source",
                    "PRIVATE_SOURCE_SENTINEL.jsonl",
                    "--archive-state",
                    "active",
                    "--json",
                ],
                "invalid-analysis-request",
            ),
            (
                [
                    "telemetry",
                    "agent-thread",
                    "analyze",
                    "--input",
                    "PRIVATE_INPUT_SENTINEL.zip",
                    "--codex-home",
                    "PRIVATE_HOME_SENTINEL",
                    "--json",
                ],
                "invalid-analysis-request",
            ),
            (
                [
                    "telemetry",
                    "agent-thread",
                    "analyze",
                ],
                "analysis-tty-required",
            ),
            (
                [
                    "telemetry",
                    "agent-thread",
                    "analyze",
                    "--source",
                    "PRIVATE_SOURCE_SENTINEL.jsonl",
                ],
                "analysis-tty-required",
            ),
        )
    )
    def test_analyze_flag_and_tty_matrix_fails_before_input_access(
        self,
        arguments: list[str],
        expected_code: str,
    ) -> None:
        if "--json" not in arguments:
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main(arguments)
            assert (code) == (EXIT_CONFLICT)
            assert (stdout.getvalue()) == ("")
            serialized = stderr.getvalue()
            assert (expected_code) in (serialized)
            for sentinel in (
                "PRIVATE_SOURCE_SENTINEL",
                "PRIVATE_INPUT_SENTINEL",
                "PRIVATE_HOME_SENTINEL",
            ):
                assert (sentinel) not in (serialized)
            return

        code, payload, serialized_error = self.invoke(arguments)
        assert (code) == (EXIT_CONFLICT)
        assert (payload["error"]["code"]) == (expected_code)
        assert (payload["error"]["details"]) == ({})
        serialized = serialized_error + json.dumps(payload)
        for sentinel in (
            "PRIVATE_SOURCE_SENTINEL",
            "PRIVATE_INPUT_SENTINEL",
            "PRIVATE_HOME_SENTINEL",
        ):
            assert (sentinel) not in (serialized)

    def test_analyze_rejects_schema_v1_before_native_member_open(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary) / "schema-v1.zip"
            old_manifest = {
                "schema_version": 1,
                "exporter": {"name": "svc"},
                "provider": {},
                "thread": {},
                "artifact": {},
            }
            with zipfile.ZipFile(bundle, "w") as archive:
                archive.writestr(
                    "manifest.json",
                    json.dumps(old_manifest),
                )
                archive.writestr(
                    "providers/codex/rollout.jsonl",
                    "PRIVATE_NATIVE_SENTINEL",
                )
                archive.writestr(
                    "thread/index.json",
                    "PRIVATE_INDEX_SENTINEL",
                )
                archive.writestr(
                    "task-packets/tasks/x/packet.md",
                    "PRIVATE_TASK_SENTINEL",
                )

            code, payload, serialized_error = self.invoke(
                [
                    "telemetry",
                    "agent-thread",
                    "analyze",
                    "--input",
                    str(bundle),
                    "--json",
                ]
            )

        assert (code) == (EXIT_CONFLICT)
        assert (payload["error"]["code"]) == ("unsupported-agent-thread-bundle-schema")
        serialized = serialized_error + json.dumps(payload)
        for sentinel in (
            "PRIVATE_NATIVE_SENTINEL",
            "PRIVATE_INDEX_SENTINEL",
            "PRIVATE_TASK_SENTINEL",
        ):
            assert (sentinel) not in (serialized)

    def test_analyze_source_failure_redacts_private_provider_details(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = (
                Path(temporary)
                / "PRIVATE_ANALYZE_SOURCE_SENTINEL.jsonl"
            )

            code, payload, serialized_error = self.invoke(
                [
                    "telemetry",
                    "agent-thread",
                    "analyze",
                    "--source",
                    str(source),
                    "--json",
                ]
            )

        assert (code) == (EXIT_CONFLICT)
        assert (payload["error"]["code"]) == ("thread-source-not-found")
        assert (payload["error"]["details"]) == ({})
        serialized = serialized_error + json.dumps(payload)
        assert (str(source)) not in (serialized)
        assert ("PRIVATE_ANALYZE_SOURCE_SENTINEL") not in (serialized)

    def test_list_uses_safe_state_metadata_without_reading_transcript_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            source = home / "rollout.jsonl"
            self.rollout(source, "thread-list", "secret task body")
            connection = sqlite3.connect(home / "state_5.sqlite")
            connection.execute(
                "CREATE TABLE threads (id TEXT, rollout_path TEXT, updated_at INTEGER, archived INTEGER)"
            )
            connection.execute("INSERT INTO threads VALUES (?, ?, ?, ?)", ("thread-list", source.name, 1_721_088_000, 0))
            connection.commit()
            connection.close()

            code, payload, serialized_error = self.invoke(
                ["telemetry", "agent-thread", "list", "--codex-home", str(home), "--json"]
            )
            assert (code) == (EXIT_OK)
            assert (payload["threads"]) == ([
                    {
                        "provider_id": "codex",
                        "thread_id": "thread-list",
                        "source_state": "active",
                        "created_at": None,
                        "updated_at": "1721088000",
                    }
                ])
            assert ("warnings") not in (payload)
            assert ("secret task body") not in (serialized_error)
            assert ("secret task body") not in (json.dumps(payload))

    def test_list_passes_archive_filter_and_projects_inventory_safely(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        class FakeProvider:
            provider_id = "fake"

            def __init__(self) -> None:
                self.query = None

            def list_inventory(self, context, query):
                self.query = query
                return ThreadInventoryListing(
                    items=(
                        ThreadInventoryItem(
                            provider_id="fake",
                            thread_id="active-thread",
                            archive_state=ArchiveState.ACTIVE,
                            source_availability=SourceAvailability.AVAILABLE,
                            created_at="2026-07-16T00:00:00Z",
                            updated_at="2026-07-16T01:00:00Z",
                        ),
                        ThreadInventoryItem(
                            provider_id="fake",
                            thread_id="archived-thread",
                            archive_state=ArchiveState.ARCHIVED,
                            source_availability=SourceAvailability.MISSING,
                            created_at=None,
                            updated_at="2026-07-15T01:00:00Z",
                        ),
                        ThreadInventoryItem(
                            provider_id="fake",
                            thread_id="unavailable-thread",
                            archive_state=ArchiveState.ACTIVE,
                            source_availability=SourceAvailability.UNAVAILABLE,
                        ),
                        ThreadInventoryItem(
                            provider_id="fake",
                            thread_id="unknown-thread",
                            archive_state=ArchiveState.UNKNOWN,
                            source_availability=SourceAvailability.AVAILABLE,
                        ),
                    ),
                    omitted_sources=2,
                )

        fake = FakeProvider()
        monkeypatch.setattr(
            "svc_cli.telemetry.service.local_provider",
            lambda: fake,
        )
        code, payload, _ = self.invoke(
            [
                "telemetry",
                "agent-thread",
                "list",
                "--archive-state",
                "archived",
                "--limit",
                "7",
                "--json",
            ]
        )

        assert (code) == (EXIT_OK)
        assert (fake.query) is not None
        assert (fake.query.archive_state) == (ArchiveFilter.ARCHIVED)
        assert (fake.query.limit) == (7)
        assert (payload["provider"]) == ("fake")
        assert (payload["threads"]) == ([
                {
                    "provider_id": "fake",
                    "thread_id": "active-thread",
                    "source_state": "active",
                    "created_at": "2026-07-16T00:00:00Z",
                    "updated_at": "2026-07-16T01:00:00Z",
                },
                {
                    "provider_id": "fake",
                    "thread_id": "archived-thread",
                    "source_state": "missing",
                    "created_at": None,
                    "updated_at": "2026-07-15T01:00:00Z",
                },
                {
                    "provider_id": "fake",
                    "thread_id": "unavailable-thread",
                    "source_state": "unavailable",
                    "created_at": None,
                    "updated_at": None,
                },
                {
                    "provider_id": "fake",
                    "thread_id": "unknown-thread",
                    "source_state": "unknown",
                    "created_at": None,
                    "updated_at": None,
                },
            ])
        assert (payload["warnings"]) == ([{"code": "thread-source-omitted", "count": 2}])

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
            assert (code) == (EXIT_OK)
            assert (payload["status"]) == ("listed")
            assert (payload["threads"]) == ([])
            assert (payload["warnings"]) == ([{"code": "thread-source-omitted", "count": 1}])
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
                assert (private_value) not in (serialized)

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

            assert (code) == (EXIT_OK)
            assert (stderr.getvalue()) == ("")
            assert ("SVC telemetry agent-thread list: 0 thread(s)") in (stdout.getvalue())
            assert ("Degraded: 1 source row(s) omitted") in (stdout.getvalue())
            assert ("private-rollout.jsonl") not in (stdout.getvalue())

    def test_list_missing_state_database_remains_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)

            code, payload, serialized_error = self.invoke(
                ["telemetry", "agent-thread", "list", "--codex-home", str(home), "--json"]
            )

            assert (code) == (EXIT_CONFLICT)
            assert (payload["error"]["code"]) == ("thread-source-not-found")
            assert (payload["error"]["details"]) == ({})
            assert (str(home)) not in (serialized_error)

    def test_list_corrupt_state_database_remains_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "state_5.sqlite").write_bytes(b"not-a-sqlite-database")

            code, payload, serialized_error = self.invoke(
                ["telemetry", "agent-thread", "list", "--codex-home", str(home), "--json"]
            )

            assert (code) == (EXIT_CONFLICT)
            assert (payload["error"]["code"]) == ("thread-source-incompatible")
            assert (payload["error"]["details"]) == ({})
            assert (str(home)) not in (serialized_error)
