from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import os
import stat

from svc_cli.cli import main
from svc_cli.telemetry.agent_threads import (
    ArchiveState,
    ThreadInventoryListing,
    ThreadInventoryRow,
)
from svc_cli.telemetry.evidence import validate_evidence


def invoke(arguments: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(arguments)
    return code, stdout.getvalue(), stderr.getvalue()


def rollout(path: Path) -> None:
    records = (
        {
            "timestamp": "2026-01-01T00:00:00Z",
            "type": "session_meta",
            "payload": {"id": "thread-cli", "cwd": "/work/svc"},
        },
        {
            "timestamp": "2026-01-01T00:00:01Z",
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": "finished",
            },
        },
    )
    path.write_text(
        "\n".join(json.dumps(item, separators=(",", ":")) for item in records) + "\n",
        encoding="utf-8",
    )


def test_export_reports_schema_v3_without_privacy_ack_or_repo(tmp_path: Path) -> None:
    source = tmp_path / "rollout.jsonl"
    output = tmp_path / "evidence.zip"
    rollout(source)
    code, stdout, stderr = invoke(
        [
            "telemetry",
            "agent-thread",
            "export",
            "--source",
            str(source),
            "--output",
            str(output),
            "--json",
        ]
    )
    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["schema_version"] == 3
    assert payload["evidence"]["schema_version"] == 3
    assert payload["capture"]["status"] == "complete"
    assert isinstance(payload["diagnostic_groups"], int)
    assert "diagnostics" not in payload
    assert validate_evidence(output).manifest["schema_version"] == 3


def test_export_final_mode_follows_process_umask(tmp_path: Path) -> None:
    if os.name == "nt":
        return
    source = tmp_path / "rollout.jsonl"
    output = tmp_path / "umask.zip"
    rollout(source)
    previous = os.umask(0o027)
    try:
        code, _, _ = invoke(
            [
                "telemetry",
                "agent-thread",
                "export",
                "--source",
                str(source),
                "--output",
                str(output),
                "--json",
            ]
        )
    finally:
        os.umask(previous)
    assert code == 0
    assert stat.S_IMODE(output.stat().st_mode) == 0o640


def test_analysis_schema_and_execution_are_json_only(tmp_path: Path) -> None:
    source = tmp_path / "rollout.jsonl"
    bundle = tmp_path / "evidence.zip"
    rollout(source)
    assert (
        invoke(
            [
                "telemetry",
                "agent-thread",
                "export",
                "--source",
                str(source),
                "--output",
                str(bundle),
                "--json",
            ]
        )[0]
        == 0
    )

    code, stdout, stderr = invoke(["analysis", "query", "--schema"])
    assert code == 0 and stderr == ""
    assert json.loads(stdout)["method"]["section"] == "Agent Task Analysis"

    request = tmp_path / "query.json"
    request.write_text('{"intent":"overview"}', encoding="utf-8")
    code, stdout, stderr = invoke(
        [
            "analysis",
            "query",
            "--input",
            str(bundle),
            "--request",
            str(request),
        ]
    )
    assert code == 0 and stderr == ""
    result = json.loads(stdout)
    assert result["intent"] == "overview"
    assert result["status"] == "complete"

    read_request = tmp_path / "read.json"
    read_request.write_text('{"max_items":1}', encoding="utf-8")
    code, stdout, stderr = invoke(
        [
            "analysis",
            "read",
            "--input",
            str(bundle),
            "--request",
            str(read_request),
        ]
    )
    assert code == 0 and stderr == ""
    assert json.loads(stdout)["items"][0]["ref"]["record_id"] == "n000000"


def test_analysis_parse_and_request_errors_are_structured_json(tmp_path: Path) -> None:
    code, stdout, stderr = invoke(["analysis", "query", "--unknown"])
    assert code == 2 and stdout == ""
    assert json.loads(stderr)["code"] == "invalid-cli-usage"

    request = tmp_path / "bad.json"
    request.write_text('{"intent":"overview","intent":"match"}', encoding="utf-8")
    code, stdout, stderr = invoke(
        [
            "analysis",
            "query",
            "--input",
            str(tmp_path / "missing.zip"),
            "--request",
            str(request),
        ]
    )
    assert code == 2 and stdout == ""
    assert json.loads(stderr)["code"] == "invalid-analysis-request-json"


def test_removed_old_analysis_and_legacy_flags_are_unreachable(tmp_path: Path) -> None:
    code, _, _ = invoke(["telemetry", "agent-thread", "analyze"])
    assert code == 2
    source = tmp_path / "source.jsonl"
    rollout(source)
    code, _, _ = invoke(
        [
            "telemetry",
            "agent-thread",
            "export",
            "--source",
            str(source),
            "--output",
            str(tmp_path / "x.zip"),
            "--legacy-listing",
        ]
    )
    assert code == 2


def test_list_projects_provider_inventory_fields(monkeypatch) -> None:
    class Provider:
        provider_id = "codex"

        def list_inventory(self, context, query):
            return ThreadInventoryListing(
                (
                    ThreadInventoryRow(
                        provider_id="codex",
                        thread_id="thread-1",
                        archive_state=ArchiveState.ACTIVE,
                        workspace="/work/svc",
                        title="Implement analysis",
                        first_user_message="Start",
                    ),
                )
            )

    monkeypatch.setattr("svc_cli.telemetry.service.local_provider", lambda: Provider())
    code, stdout, stderr = invoke(["telemetry", "agent-thread", "list", "--json"])
    assert code == 0 and stderr == ""
    row = json.loads(stdout)["threads"][0]
    assert row["provider_id"] == "codex"
    assert row["thread_id"] == "thread-1"
    assert row["archive_state"] == "active"
    assert row["title"] == "Implement analysis"
    assert row["workspace"] == "/work/svc"
    assert "source_availability" not in row
    assert "source_warning_code" not in row
    assert "omitted_sources" not in json.loads(stdout)
