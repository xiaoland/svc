from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import accept_agent_thread as harness


def _wheel_inputs(directory: Path) -> tuple[Path, str, Path]:
    wheel = directory / "sustainable_vibe_coding-11.0.0-py3-none-any.whl"
    wheel.write_bytes(b"synthetic wheel bytes")
    wheelhouse = directory / "wheelhouse"
    wheelhouse.mkdir()
    shutil.copyfile(wheel, wheelhouse / wheel.name)
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    return wheel, digest, wheelhouse


def _canonical(value: object, *, newline: bool = False) -> bytes:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return encoded + (b"\n" if newline else b"")


def _text_metadata(
    value: str,
    *,
    observed: int | None = None,
    strategy: str = "none",
) -> dict[str, object]:
    return {
        "truncated": strategy != "none",
        "observed_code_points": len(value) if observed is None else observed,
        "retained_code_points": len(value),
        "strategy": strategy,
    }


def _write_fake_bundle(output: Path) -> dict[str, object]:
    thread_ref = "thread_" + ("1" * 64)
    workspace_ref = "workspace_" + ("2" * 64)
    call_ref = "call_" + ("3" * 64)
    workspace_label = "fixture-repository"
    message = (
        f"{harness._PRIVATE_SENTINELS[2]} work from {harness._BUNDLE_TASK_REFERENCE}"
    )
    tool_name = "acceptance-tool"
    arguments = '{"scope":"bundle"}'
    retained_tool_output = ("L" * 1_250) + ("R" * 1_250)
    observed_tool_output = 6_000 + len(harness._PRIVATE_SENTINELS[5])
    records = (
        {
            "type": "meta",
            "record_id": "r000000",
            "record_index": 0,
            "timestamp": None,
            "source_ref": {"event_index": None, "component": "meta"},
            "trajectory_schema": harness._TRAJECTORY_SCHEMA,
            "provider_id": "codex",
            "adapter_id": "codex-rollout-v1",
            "source_format": "rollout-v1",
            "thread_ref": thread_ref,
            "workspace": {
                "status": "present",
                "flavor": "posix",
                "label": workspace_label,
                "ref": workspace_ref,
                "label_truncated": False,
                "observed_code_points": len(workspace_label),
                "retained_code_points": len(workspace_label),
            },
            "content_profile": "bounded-normalized-v1",
        },
        {
            "type": "message",
            "record_id": "r000001",
            "record_index": 1,
            "timestamp": "2026-07-28T00:00:01Z",
            "source_ref": {
                "event_index": 1,
                "line": 1,
                "component_index": 0,
                "component": "message",
            },
            "role": "user",
            "content": message,
            "content_meta": _text_metadata(message),
            "task_refs": [harness._BUNDLE_TASK_REFERENCE],
        },
        {
            "type": "tool_call",
            "record_id": "r000002",
            "record_index": 2,
            "timestamp": "2026-07-28T00:00:04Z",
            "source_ref": {
                "event_index": 4,
                "line": 4,
                "component_index": 0,
                "component": "tool_call",
            },
            "tool_call_id": call_ref,
            "name": tool_name,
            "name_meta": _text_metadata(tool_name),
            "name_fingerprint": hashlib.sha256(
                b"svc-tool-name-v1\0" + tool_name.encode("utf-8")
            ).hexdigest(),
            "arguments_kind": "json",
            "arguments": arguments,
            "arguments_meta": _text_metadata(arguments),
            "arguments_fingerprint": hashlib.sha256(
                b"svc-tool-arguments-v1\0" + arguments.encode("utf-8")
            ).hexdigest(),
        },
        {
            "type": "tool_result",
            "record_id": "r000003",
            "record_index": 3,
            "timestamp": "2026-07-28T00:00:05Z",
            "source_ref": {
                "event_index": 5,
                "line": 5,
                "component_index": 0,
                "component": "tool_result",
            },
            "tool_call_id": call_ref,
            "content": retained_tool_output,
            "content_meta": _text_metadata(
                retained_tool_output,
                observed=observed_tool_output,
                strategy="head_tail",
            ),
            "status": "success",
            "link_status": "linked",
        },
    )
    trajectory = b"".join(_canonical(record, newline=True) for record in records)
    records_by_type = {
        record_type: sum(record["type"] == record_type for record in records)
        for record_type in harness._RECORD_TYPES
    }
    lossiness = {
        group: {key: 0 for key in keys} for group, keys in harness._LOSS_KEYS.items()
    }
    lossiness["dropped"]["provider_envelope"] = 6
    lossiness["dropped"]["rate_limit_noise"] = 1
    lossiness["truncated"]["tool_result"] = 1
    diagnostics = [
        {
            "code": "noise-record-dropped",
            "severity": "info",
            "action": "drop",
            "count": 6,
            "record_ref": None,
            "source_ref": {
                "event_index": 0,
                "line": 0,
                "component_index": 0,
                "component": "envelope",
            },
            "details": {"record_type": "envelope"},
        },
        {
            "code": "unsupported-record-dropped",
            "severity": "warning",
            "action": "drop",
            "count": 1,
            "record_ref": None,
            "source_ref": {
                "event_index": 3,
                "line": 3,
                "component_index": 0,
                "component": "envelope",
            },
            "details": {"record_type": "unknown"},
        },
        {
            "code": "tool-result-truncated",
            "severity": "info",
            "action": "truncate",
            "count": 1,
            "record_ref": None,
            "source_ref": {
                "event_index": 5,
                "line": 5,
                "component_index": 0,
                "component": "envelope",
            },
            "details": {
                "observed_code_points": observed_tool_output,
                "retained_code_points": len(retained_tool_output),
            },
        },
    ]
    counts = {
        "source_bytes_read": 8_192,
        "source_events_seen": 6,
        "records_emitted": len(records),
        "trajectory_bytes": len(trajectory),
        "records_by_type": records_by_type,
        "messages_by_role": {"user": 1, "assistant": 0},
        "tool_calls": 1,
        "tool_results": 1,
        "task_references": 1,
        "diagnostics_emitted": sum(item["count"] for item in diagnostics),
        "diagnostics_suppressed": 0,
    }
    source = {
        "provider_id": "codex",
        "adapter_id": "codex-rollout-v1",
        "source_format": "rollout-v1",
        "thread_ref": thread_ref,
        "source_status": "stable",
    }
    capabilities = {
        "reasoning": "opaque",
        "tool_linkage": "explicit",
        "context": "absent",
        "task_references": "available",
        "explicit_concurrency": "unavailable",
        "timestamps": "full",
        "terminal_events": "unavailable",
    }
    manifest: dict[str, object] = {
        "format": harness._BUNDLE_FORMAT,
        "schema_version": harness._BUNDLE_SCHEMA_VERSION,
        "trajectory": {
            "schema": harness._TRAJECTORY_SCHEMA,
            "member": "trajectory.jsonl",
            "sha256": hashlib.sha256(trajectory).hexdigest(),
            "bytes": len(trajectory),
            "records": len(records),
        },
        "bundle_id": "0" * 64,
        "exporter": {
            "name": "svc",
            "version": "11.0.0",
            "normalizer_name": "svc-agent-thread-normalizer",
            "normalizer_version": 1,
        },
        "generated_at": "2026-07-28T00:00:06Z",
        "source": source,
        "policy": harness._EXPECTED_POLICY,
        "result_status": "partial",
        "capabilities": capabilities,
        "counts": counts,
        "lossiness": lossiness,
        "diagnostics": diagnostics,
    }
    identity = {
        "normalizer_name": "svc-agent-thread-normalizer",
        "normalizer_version": 1,
        "source": source,
        "policy": harness._EXPECTED_POLICY,
        "result_status": "partial",
        "capabilities": capabilities,
        "counts": counts,
        "lossiness": lossiness,
        "diagnostics": diagnostics,
    }
    manifest["bundle_id"] = hashlib.sha256(
        b"svc-agent-thread-bundle-v2\0" + trajectory + b"\0" + _canonical(identity)
    ).hexdigest()

    def zip_info(name: str) -> zipfile.ZipInfo:
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.create_system = 3
        info.external_attr = (0o600 & 0xFFFF) << 16
        return info

    with zipfile.ZipFile(
        output,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        allowZip64=True,
    ) as archive:
        archive.writestr(
            zip_info("manifest.json"),
            _canonical(manifest, newline=True),
        )
        archive.writestr(zip_info("trajectory.jsonl"), trajectory)
    if os.name != "nt":
        output.chmod(0o600)
    return manifest


def _fake_analysis_payload(bundle: Path) -> dict[str, object]:
    with zipfile.ZipFile(bundle, mode="r") as archive:
        manifest = json.loads(archive.read("manifest.json"))
    dimensions = {
        name: {
            "status": "partial",
            "finding_ids": [],
            "unknown_ids": [],
        }
        for name in harness._ANALYSIS_DIMENSIONS
    }
    metrics = {
        "task_evidence": {
            "user_turn_count": 1,
            "user_turn_refs": [],
            "task_references": [],
        },
        "interaction_transitions": {
            "boundary_count": 1,
            "boundaries": [],
            "structured_approval_count": 0,
        },
        "constraint_evidence": {
            "context_record_count": 0,
            "task_reference_count": 1,
            "structured_approval_count": 0,
            "evidence_refs": [],
        },
        "tool_outcomes": {
            "calls": 1,
            "results": 1,
            "success": 1,
            "error": 0,
            "unknown": 0,
            "pending": 0,
            "orphan": 0,
            "late_linked": 0,
            "truncated_results": 1,
            "retry_groups": 0,
            "tools": [],
        },
        "loop_candidates": {
            "retry_group_count": 0,
            "loop_candidate_count": 0,
            "stall_candidate_count": 0,
            "recovery_candidate_count": 0,
            "groups": [],
        },
        "lanes": {
            "actor_count": 0,
            "lane_count": 0,
            "concurrency_group_count": 0,
            "parent_link_count": 0,
            "actors": [],
            "lanes": [],
            "concurrency_groups": [],
        },
        "terminal_coverage": {
            "status": "unknown",
            "terminal_evidence_refs": [],
            "tail_loss": True,
        },
        "svc_signals": {
            "task_references": 1,
            "svc_cli_calls": 0,
            "test_calls": 0,
            "build_calls": 0,
            "signals": [],
        },
        "context_changes": {
            "context_records": 0,
            "changes": 0,
            "by_kind": {
                "system": 0,
                "developer": 0,
                "tool_config": 0,
                "turn": 0,
            },
            "change_refs": [],
        },
        "coverage": {
            "records_total": 4,
            "records_by_type": manifest["counts"]["records_by_type"],
            "messages_by_role": manifest["counts"]["messages_by_role"],
            "timestamped_records": 3,
            "untimestamped_records": 0,
            "first_timestamp": "2026-07-28T00:00:01Z",
            "last_timestamp": "2026-07-28T00:00:05Z",
            "source_status": "stable",
            "bundle_result_status": "partial",
            "capabilities": manifest["capabilities"],
        },
    }
    return {
        "format": "svc-agent-thread-analysis",
        "schema_version": 1,
        "bundle_id": manifest["bundle_id"],
        "analyzer": harness._ANALYSIS_ANALYZER,
        "result_status": "partial",
        "dimensions": dimensions,
        "metrics": metrics,
        "findings": [],
        "unknowns": [],
        "lossiness": {
            "bundle": {
                "mode": "bounded_normalized",
                "source_status": "stable",
                "result_status": "partial",
                **manifest["lossiness"],
            },
            "analysis": {
                "limits_reached": [],
                "findings_omitted": 0,
                "unknowns_omitted": 0,
                "evidence_refs_omitted": 0,
                "metric_entries_omitted": 0,
            },
        },
    }


def _main_output(argv: list[str]) -> tuple[int, dict[str, object]]:
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = harness.main(argv)
    return code, json.loads(stream.getvalue())


def _fake_command(args, **_kwargs):
    values = [os.fspath(value) for value in args]
    if "pip" in values and "install" in values:
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    if "-c" in values:
        code = values[values.index("-c") + 1]
        if harness._SCHEMA_V1_PROBE_MARKER in code:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "code": "unsupported-agent-thread-bundle-schema",
                        "opened": ["manifest.json"],
                    }
                ),
                stderr="",
            )
        if harness._ANALYSIS_IMPORT_PROBE_MARKER in code:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "code": 0,
                        "root": True,
                        "textual_imported": False,
                        "tui_imported": False,
                    }
                ),
                stderr="",
            )
        if harness._UI_PROBE_MARKER in code:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "entered": 2,
                        "quits": ["q", "escape"],
                        "restored": True,
                        "sizes": [[80, 24], [30, 10]],
                        "views": 8,
                    }
                ),
                stderr="",
            )
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    name: (
                        "11.0.0"
                        if name == "sustainable-vibe-coding"
                        else "8.2.8"
                        if name == "textual"
                        else "1.0.0"
                    )
                    for name in harness._INSTALLED_DISTRIBUTIONS
                }
            ),
            stderr="",
        )
    if "agent-thread" in values and "list" in values:
        archive_state = values[values.index("--archive-state") + 1]
        if archive_state == "archived":
            identifiers = ["inv-archived-missing"]
        elif archive_state == "active":
            identifiers = ["inv-active-new"]
        else:
            identifiers = [
                "inv-active-new",
                "inv-archived",
                "inv-archived-missing",
                "inv-unknown",
            ]
        payload = {
            "threads": [
                {
                    "provider_id": "codex",
                    "thread_id": identifier,
                    "source_state": (
                        "missing"
                        if identifier in {"inv-unknown", "inv-archived-missing"}
                        else "archived"
                        if identifier == "inv-archived"
                        else "active"
                    ),
                    "created_at": None,
                    "updated_at": None,
                }
                for identifier in identifiers
            ],
            "warnings": (
                [{"code": "thread-source-omitted", "count": 1}]
                if archive_state == "all"
                else []
            ),
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")
    if "agent-thread" in values and "analyze" in values:
        bundle = Path(values[values.index("--input") + 1])
        payload = _fake_analysis_payload(bundle)
        return SimpleNamespace(
            returncode=0,
            stdout=_canonical(payload, newline=True).decode("utf-8"),
            stderr="",
        )
    if "agent-thread" in values and "export" in values:
        output = Path(values[values.index("--output") + 1])
        if output.exists():
            return SimpleNamespace(
                returncode=3,
                stdout="",
                stderr=json.dumps(
                    {
                        "schema_version": 1,
                        "error": {
                            "code": "output-exists",
                            "message": (
                                "Bundle output already exists and was not replaced."
                            ),
                            "details": {},
                        },
                    }
                ),
            )
        manifest = _write_fake_bundle(output)
        payload = {
            "schema_version": 1,
            "command": "telemetry agent-thread export",
            "status": "exported",
            "bundle": {
                "path": str(output),
                "bundle_id": manifest["bundle_id"],
                "trajectory": manifest["trajectory"],
            },
            "source": manifest["source"],
            "result_status": manifest["result_status"],
            "capabilities": manifest["capabilities"],
            "counts": manifest["counts"],
            "lossiness": manifest["lossiness"],
            "diagnostics": manifest["diagnostics"],
        }
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def _run_fake_successful_slice(
    monkeypatch: pytest.MonkeyPatch,
    slice_name: str,
    *,
    command=None,
):
    """Run one successful slice through the common isolated harness seam."""
    with tempfile.TemporaryDirectory() as temporary:
        wheel, digest, wheelhouse = _wheel_inputs(Path(temporary))
        created_roots: list[Path] = []

        def fake_venv(root: Path) -> Path:
            created_roots.append(root)
            return root / "fake-python"

        monkeypatch.setattr(harness, "_create_virtualenv", fake_venv)
        monkeypatch.setattr(harness, "_command", command or _fake_command)
        code, report = _main_output(
            [
                "--slice",
                slice_name,
                "--wheel",
                str(wheel),
                "--expected-sha256",
                digest,
                "--wheelhouse",
                str(wheelhouse),
            ]
        )
        assert len(created_roots) == 1
        assert not created_roots[0].exists(), (
            "harness must remove its own temporary root"
        )
    return code, report, digest


def test_argument_failures_emit_bounded_json_and_stable_code():
    code, report = _main_output(["--slice", "inventory"])
    assert code == 2
    assert report["exit_code"] == 2
    assert report["error"] == "arguments"
    assert "usage" not in json.dumps(report).lower()


def test_digest_mismatch_is_validation_failure_without_temp_creation():
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        wheel, _digest, wheelhouse = _wheel_inputs(directory)
        code, report = _main_output(
            [
                "--slice",
                "inventory",
                "--wheel",
                str(wheel),
                "--expected-sha256",
                "0" * 64,
                "--wheelhouse",
                str(wheelhouse),
            ]
        )
    assert code == 4
    assert report["error"] == "wheel-validation"
    assert report["cleanup"] == "not-started"


def test_sha_bound_staging_keeps_original_bytes_when_source_replaced_after_copy(
    monkeypatch: pytest.MonkeyPatch,
):
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        source = directory / "product.whl"
        replacement = directory / "replacement.whl"
        root = directory / "harness-root"
        root.mkdir()
        source.write_bytes(b"original wheel bytes")
        replacement.write_bytes(b"replacement wheel bytes")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        original_lstat = Path.lstat
        source_lstat_calls = 0

        def racing_lstat(path: Path):
            nonlocal source_lstat_calls
            info = original_lstat(path)
            if path == source:
                source_lstat_calls += 1
                if source_lstat_calls == 2:
                    os.replace(replacement, source)
            return info

        monkeypatch.setattr(Path, "lstat", racing_lstat)
        staged = harness._stage_wheel(source, digest, root)
        assert staged.read_bytes() == b"original wheel bytes"
        assert hashlib.sha256(staged.read_bytes()).hexdigest() == digest
        assert source.read_bytes() == b"replacement wheel bytes"


def test_wheelhouse_must_contain_binary_wheels_only():
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        wheel, digest, wheelhouse = _wheel_inputs(directory)
        (wheelhouse / "notes.txt").write_text("not a wheel")
        code, report = _main_output(
            [
                "--slice",
                "inventory",
                "--wheel",
                str(wheel),
                "--expected-sha256",
                digest,
                "--wheelhouse",
                str(wheelhouse),
            ]
        )
    assert code == 4
    assert report["error"] == "wheel-validation"


def test_command_runner_can_execute_a_fake_executable_without_a_shell():
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        if os.name == "nt":
            fake = directory / "fake-agent.cmd"
            fake.write_text('@echo {\\"status\\":\\"ok\\"}\n', encoding="utf-8")
        else:
            fake = directory / "fake-agent"
            fake.write_text(
                "#!/bin/sh\nprintf '%s' '{\"status\":\"ok\"}'\n", encoding="utf-8"
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        result = harness._command((fake, "fixture-value"))
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"status": "ok"}


@pytest.mark.parametrize("slice_name", ("inventory", "bundle", "analysis", "ui"))
def test_fake_executable_covers_each_isolated_slice(
    monkeypatch: pytest.MonkeyPatch,
    slice_name: str,
):
    code, report, digest = _run_fake_successful_slice(monkeypatch, slice_name)
    assert code == 0
    assert report["status"] == "passed"
    assert report["cases"] == {slice_name: "passed"}
    assert report["cleanup"] == "passed"
    assert "SVC_ACCEPT_PRIVATE" not in json.dumps(report)

    if slice_name == "inventory":
        assert report["wheel_sha256"] == digest
    elif slice_name == "bundle":
        assert "bundle_id" not in report
        assert "trajectory" not in report
    elif slice_name == "analysis":
        assert "textual" in report["installed"]
        assert "dimensions" not in report
    else:
        assert "views" not in report


def test_all_runs_inventory_bundle_analysis_then_ui(monkeypatch: pytest.MonkeyPatch):
    observed_commands: list[list[str]] = []

    def ordered_command(args, **kwargs):
        values = [os.fspath(value) for value in args]
        if "agent-thread" in values:
            observed_commands.append(values)
        return _fake_command(args, **kwargs)

    code, report, _digest = _run_fake_successful_slice(
        monkeypatch,
        "all",
        command=ordered_command,
    )
    assert code == 0
    assert report["cases"] == {
        "inventory": "passed",
        "bundle": "passed",
        "analysis": "passed",
        "ui": "passed",
    }
    assert [
        "list" if "list" in command else "analyze" if "analyze" in command else "export"
        for command in observed_commands
    ] == [
        "list",
        "list",
        "list",
        "export",
        "export",
        "export",
        "export",
        "analyze",
        "analyze",
        "export",
        "export",
    ]


def test_bundle_rejects_an_extra_archive_member_with_generic_case_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    with tempfile.TemporaryDirectory() as temporary:
        wheel, digest, wheelhouse = _wheel_inputs(Path(temporary))
        created_roots: list[Path] = []

        def fake_venv(root: Path) -> Path:
            created_roots.append(root)
            return root / "fake-python"

        def extra_member(args, **kwargs):
            result = _fake_command(args, **kwargs)
            values = [os.fspath(value) for value in args]
            if "agent-thread" in values and "export" in values:
                output = Path(values[values.index("--output") + 1])
                with zipfile.ZipFile(output, mode="a") as archive:
                    archive.writestr("raw.jsonl", b"private native bytes")
            return result

        monkeypatch.setattr(harness, "_create_virtualenv", fake_venv)
        monkeypatch.setattr(harness, "_command", extra_member)
        code, report = _main_output(
            [
                "--slice",
                "bundle",
                "--wheel",
                str(wheel),
                "--expected-sha256",
                digest,
                "--wheelhouse",
                str(wheelhouse),
            ]
        )
        assert not created_roots[0].exists()
    assert code == 6
    assert report["error"] == "case"
    assert report["cases"] == {"bundle": "failed"}
    assert "raw.jsonl" not in json.dumps(report)


def test_bundle_rejects_stdout_sentinel_with_generic_case_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    with tempfile.TemporaryDirectory() as temporary:
        wheel, digest, wheelhouse = _wheel_inputs(Path(temporary))
        created_roots: list[Path] = []

        def fake_venv(root: Path) -> Path:
            created_roots.append(root)
            return root / "fake-python"

        def leaking_command(args, **kwargs):
            result = _fake_command(args, **kwargs)
            values = [os.fspath(value) for value in args]
            if "agent-thread" in values and "export" in values:
                payload = json.loads(result.stdout)
                payload["leak"] = harness._PRIVATE_SENTINELS[2]
                return SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps(payload),
                    stderr="",
                )
            return result

        monkeypatch.setattr(harness, "_create_virtualenv", fake_venv)
        monkeypatch.setattr(harness, "_command", leaking_command)
        code, report = _main_output(
            [
                "--slice",
                "bundle",
                "--wheel",
                str(wheel),
                "--expected-sha256",
                digest,
                "--wheelhouse",
                str(wheelhouse),
            ]
        )
        assert not created_roots[0].exists()
    assert code == 6
    assert report["error"] == "case"
    assert report["cases"] == {"bundle": "failed"}
    assert "SVC_ACCEPT_PRIVATE" not in json.dumps(report)


def test_bundle_requires_schema_v1_probe_to_open_only_the_manifest(
    monkeypatch: pytest.MonkeyPatch,
):
    with tempfile.TemporaryDirectory() as temporary:
        wheel, digest, wheelhouse = _wheel_inputs(Path(temporary))
        created_roots: list[Path] = []

        def fake_venv(root: Path) -> Path:
            created_roots.append(root)
            return root / "fake-python"

        def unsafe_probe(args, **kwargs):
            values = [os.fspath(value) for value in args]
            if (
                "-c" in values
                and harness._SCHEMA_V1_PROBE_MARKER in values[values.index("-c") + 1]
            ):
                return SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "code": ("unsupported-agent-thread-bundle-schema"),
                            "opened": [
                                "manifest.json",
                                "providers/codex/rollout.jsonl",
                            ],
                        }
                    ),
                    stderr="",
                )
            return _fake_command(args, **kwargs)

        monkeypatch.setattr(harness, "_create_virtualenv", fake_venv)
        monkeypatch.setattr(harness, "_command", unsafe_probe)
        code, report = _main_output(
            [
                "--slice",
                "bundle",
                "--wheel",
                str(wheel),
                "--expected-sha256",
                digest,
                "--wheelhouse",
                str(wheelhouse),
            ]
        )
        assert not created_roots[0].exists()
    assert code == 6
    assert report["error"] == "case"
    assert report["cases"] == {"bundle": "failed"}
    assert "providers/codex" not in json.dumps(report)


def test_install_failure_returns_five_and_still_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
):
    with tempfile.TemporaryDirectory() as temporary:
        wheel, digest, wheelhouse = _wheel_inputs(Path(temporary))
        created_roots: list[Path] = []

        def fake_venv(root: Path) -> Path:
            created_roots.append(root)
            return root / "fake-python"

        def failed_install(args, **_kwargs):
            values = [os.fspath(value) for value in args]
            if "pip" in values and "install" in values:
                return SimpleNamespace(
                    returncode=1, stdout="private failure", stderr="private failure"
                )
            return _fake_command(args, **_kwargs)

        monkeypatch.setattr(harness, "_create_virtualenv", fake_venv)
        monkeypatch.setattr(harness, "_command", failed_install)
        code, report = _main_output(
            [
                "--slice",
                "inventory",
                "--wheel",
                str(wheel),
                "--expected-sha256",
                digest,
                "--wheelhouse",
                str(wheelhouse),
            ]
        )
        assert not created_roots[0].exists()
    assert code == 5
    assert report["error"] == "install"
    assert "private failure" not in json.dumps(report)


def test_installed_distribution_whitelist_rejects_workspace_leakage(
    monkeypatch: pytest.MonkeyPatch,
):
    leaked = {name: "1.0.0" for name in harness._INSTALLED_DISTRIBUTIONS}
    leaked["workspace-editable-private"] = "/private/workspace"
    monkeypatch.setattr(
        harness,
        "_command",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps(leaked),
            stderr="",
        ),
    )
    with tempfile.TemporaryDirectory() as temporary:
        with pytest.raises(harness.HarnessError) as raised:
            harness._installed_versions(
                Path(temporary) / "fake-python",
                Path(temporary),
                {},
            )
    assert raised.value.exit_code == 5
    assert raised.value.reason == "install"
    assert "workspace" not in raised.value.reason


def test_venv_precondition_returns_three_and_cleans_up(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as temporary:
        wheel, digest, wheelhouse = _wheel_inputs(Path(temporary))
        created_roots: list[Path] = []

        def missing_venv(root: Path) -> Path:
            created_roots.append(root)
            raise harness.HarnessError(3, "venv")

        monkeypatch.setattr(harness, "_create_virtualenv", missing_venv)
        code, report = _main_output(
            [
                "--slice",
                "inventory",
                "--wheel",
                str(wheel),
                "--expected-sha256",
                digest,
                "--wheelhouse",
                str(wheelhouse),
            ]
        )
        assert not created_roots[0].exists()
    assert code == 3
    assert report["error"] == "venv"
    assert report["cleanup"] == "passed"


def test_inventory_case_failure_returns_six_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
):
    with tempfile.TemporaryDirectory() as temporary:
        wheel, digest, wheelhouse = _wheel_inputs(Path(temporary))
        created_roots: list[Path] = []

        def fake_venv(root: Path) -> Path:
            created_roots.append(root)
            return root / "fake-python"

        def failed_case(args, **_kwargs):
            values = [os.fspath(value) for value in args]
            if "agent-thread" in values and "list" in values:
                return SimpleNamespace(returncode=1, stdout="private", stderr="private")
            return _fake_command(args, **_kwargs)

        monkeypatch.setattr(harness, "_create_virtualenv", fake_venv)
        monkeypatch.setattr(harness, "_command", failed_case)
        code, report = _main_output(
            [
                "--slice",
                "inventory",
                "--wheel",
                str(wheel),
                "--expected-sha256",
                digest,
                "--wheelhouse",
                str(wheelhouse),
            ]
        )
        assert not created_roots[0].exists()
    assert code == 6
    assert report["error"] == "case"
    assert report["cleanup"] == "passed"


def test_cleanup_failure_has_dedicated_exit_code(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as temporary:
        wheel, digest, wheelhouse = _wheel_inputs(Path(temporary))
        created_roots: list[Path] = []

        def fake_venv(root: Path) -> Path:
            created_roots.append(root)
            return root / "fake-python"

        def failed_cleanup(*_args, **_kwargs):
            raise OSError("cleanup failed")

        real_rmtree = shutil.rmtree
        monkeypatch.setattr(harness, "_create_virtualenv", fake_venv)
        monkeypatch.setattr(harness, "_command", _fake_command)
        with monkeypatch.context() as cleanup_patch:
            cleanup_patch.setattr(harness.shutil, "rmtree", failed_cleanup)
            code, report = _main_output(
                [
                    "--slice",
                    "inventory",
                    "--wheel",
                    str(wheel),
                    "--expected-sha256",
                    digest,
                    "--wheelhouse",
                    str(wheelhouse),
                ]
            )
        # The patched cleanup leaves only this narrow harness-owned root;
        # remove it through the unpatched module function before returning.
        real_rmtree(created_roots[0], ignore_errors=True)
    assert code == 7
    assert report["error"] == "cleanup"
    assert report["cleanup"] == "failed"
