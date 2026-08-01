from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

from tools import accept_agent_thread as harness


def _wheel_inputs(directory: Path) -> tuple[Path, str, Path]:
    wheel = directory / "sustainable_vibe_coding-12.0.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "sustainable_vibe_coding-12.0.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: sustainable-vibe-coding\nVersion: 12.0.0\n",
        )
        archive.writestr(
            "sustainable_vibe_coding-12.0.0.dist-info/WHEEL",
            "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
        archive.writestr(
            "sustainable_vibe_coding-12.0.0.dist-info/RECORD",
            "",
        )
    wheelhouse = directory / "wheelhouse"
    wheelhouse.mkdir()
    wheelhouse.joinpath(wheel.name).write_bytes(wheel.read_bytes())
    return wheel, hashlib.sha256(wheel.read_bytes()).hexdigest(), wheelhouse


def _main_output(arguments: list[str]) -> tuple[int, dict[str, object]]:
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = harness.main(arguments)
    return code, json.loads(stream.getvalue())


def test_harness_reports_argument_and_digest_failures(tmp_path: Path) -> None:
    code, report = _main_output(["--slice", "inventory"])
    assert (code, report["error"], report["cleanup"]) == (
        2,
        "arguments",
        "not-started",
    )

    wheel, _digest, wheelhouse = _wheel_inputs(tmp_path)
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
    assert (code, report["error"], report["cleanup"]) == (
        4,
        "wheel-validation",
        "not-started",
    )


def test_independent_consumer_reconstructs_native_frames(tmp_path: Path) -> None:
    native = b"first\nsecond\n"
    rows = [
        {
            "native_record_id": "n000000",
            "byte_start": 0,
            "byte_end": 6,
            "frame_status": "complete",
            "source_coordinate": {
                "event_index": 0,
                "line": 0,
                "byte_offset": 0,
            },
        },
        {
            "native_record_id": "n000001",
            "byte_start": 6,
            "byte_end": len(native),
            "frame_status": "complete",
            "source_coordinate": {
                "event_index": 1,
                "line": 1,
                "byte_offset": 6,
            },
        },
    ]
    index = b"".join(harness._canonical(row, newline=True) for row in rows)
    manifest = {
        "format": "svc-agent-thread-evidence",
        "schema_version": 3,
        "evidence_id": harness._evidence_id(native, index),
        "source": {
            "provider_id": "codex",
            "adapter_id": "codex-rollout-v1",
            "source_format": "rollout-v1",
            "thread_id": "accept-thread",
            "source_status": "stable",
        },
        "capture": {
            "status": "complete",
            "unknown_remainder": False,
            "read_interrupted": False,
        },
    }
    target = tmp_path / "evidence.zip"
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr(
            "manifest.json",
            harness._canonical(manifest, newline=True),
        )
        archive.writestr("native.bin", native)
        archive.writestr("native-index.jsonl", index)

    checked_manifest, entries, checked_native = harness._validate_evidence_zip(target)

    assert checked_manifest["evidence_id"] == manifest["evidence_id"]
    assert checked_native == native
    assert (
        b"".join(native[item["byte_start"] : item["byte_end"]] for item in entries)
        == native
    )


def test_all_runs_installed_slices_in_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    wheel, digest, wheelhouse = _wheel_inputs(tmp_path)
    observed: list[str] = []

    monkeypatch.setattr(harness, "_create_venv", lambda root: root / "fake-python")
    monkeypatch.setattr(harness, "_install", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        harness,
        "_installed_versions",
        lambda *args, **kwargs: {"sustainable-vibe-coding": "12.0.0"},
    )
    monkeypatch.setattr(harness, "_run_source_probe", lambda *args, **kwargs: None)
    for case in ("inventory", "evidence", "query", "read"):
        monkeypatch.setattr(
            harness,
            f"_run_{case}_case",
            lambda *args, _case=case, **kwargs: observed.append(_case),
        )

    code, report = _main_output(
        [
            "--slice",
            "all",
            "--wheel",
            str(wheel),
            "--expected-sha256",
            digest,
            "--wheelhouse",
            str(wheelhouse),
        ]
    )

    assert code == 0
    assert observed == ["inventory", "evidence", "query", "read"]
    assert report["cases"] == {case: "passed" for case in observed}
    assert report["cleanup"] == "passed"


def test_source_probe_rejects_tree_leakage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        harness,
        "_command",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "module": "/workspace/svc_cli/__init__.py",
                    "leaked": True,
                    "removed": [],
                    "textual": False,
                }
            ),
            stderr="",
        ),
    )

    with pytest.raises(harness._CaseFailure):
        harness._run_source_probe(tmp_path / "python", tmp_path, {})
