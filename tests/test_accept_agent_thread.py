from __future__ import annotations

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
            "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
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
    import contextlib

    with contextlib.redirect_stdout(stream):
        code = harness.main(arguments)
    return code, json.loads(stream.getvalue())


def test_slice_contract_is_inventory_evidence_query_read_all() -> None:
    assert harness.SLICE_CHOICES == ("inventory", "evidence", "query", "read", "all")
    assert harness._selected("all") == harness.SLICE_CHOICES[:-1]


def test_argument_failure_is_bounded_json() -> None:
    code, report = _main_output(["--slice", "inventory"])
    assert code == 2
    assert report == {
        "cases": {},
        "cleanup": "not-started",
        "error": "arguments",
        "exit_code": 2,
        "harness_version": "2",
        "installed": {},
        "platform": report["platform"],
        "python": report["python"],
        "slice": "unknown",
        "status": "failed",
        "wheel_sha256": None,
    }


def test_digest_mismatch_is_validation_failure(tmp_path: Path) -> None:
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
    assert code == 4
    assert report["error"] == "wheel-validation"
    assert report["cleanup"] == "not-started"


@pytest.mark.parametrize("member", ["tasks/raw.txt", "svc_cli/textual/widget.py", "svc_cli/telemetry/analysis/__init__.py", "native.bin"])
def test_wheel_whitelist_rejects_tasks_textual_and_raw_artifacts(tmp_path: Path, member: str) -> None:
    wheel = tmp_path / "bad.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(member, "removed")
    with pytest.raises(harness.HarnessError) as raised:
        harness._validate_wheel_contents(wheel)
    assert raised.value.reason == "wheel-validation"


def test_wheel_whitelist_rejects_textual_dependency_metadata(tmp_path: Path) -> None:
    wheel = tmp_path / "bad-dependency.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("package-1.0.dist-info/METADATA", "Metadata-Version: 2.1\nRequires-Dist: textual>=8\n")
        archive.writestr("package-1.0.dist-info/WHEEL", "Wheel-Version: 1.0\n")
    with pytest.raises(harness.HarnessError) as raised:
        harness._validate_wheel_contents(wheel)
    assert raised.value.reason == "wheel-validation"


def test_bounded_child_output_rejects_oversized_content() -> None:
    ok = SimpleNamespace(returncode=0, stdout="{\"ok\":true}", stderr="")
    assert harness._bounded_output(ok, "case").strip() == ok.stdout
    huge = SimpleNamespace(returncode=0, stdout="x" * (harness._MAX_CHILD_OUTPUT_BYTES + 1), stderr="")
    with pytest.raises(harness._CaseFailure):
        harness._bounded_output(huge, "case")


def test_installed_distribution_whitelist_rejects_textual(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    installed = {name: "1.0.0" for name in harness._ALLOWED_DISTRIBUTIONS}
    installed["textual"] = "8.0.0"
    monkeypatch.setattr(
        harness,
        "_command",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps(installed),
            stderr="",
        ),
    )
    with pytest.raises(harness.HarnessError) as raised:
        harness._installed_versions(tmp_path / "python", tmp_path, {})
    assert raised.value.reason == "install"


def test_all_runs_new_cases_in_order_with_isolated_seams(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    wheel, digest, wheelhouse = _wheel_inputs(tmp_path)
    observed: list[str] = []

    monkeypatch.setattr(harness, "_create_venv", lambda root: root / "fake-python")
    monkeypatch.setattr(harness, "_install", lambda *args, **kwargs: None)
    monkeypatch.setattr(harness, "_installed_versions", lambda *args, **kwargs: {"sustainable-vibe-coding": "12.0.0"})
    monkeypatch.setattr(harness, "_run_source_probe", lambda *args, **kwargs: None)
    for case in ("inventory", "evidence", "query", "read"):
        monkeypatch.setattr(harness, f"_run_{case}_case", lambda *args, _case=case, **kwargs: observed.append(_case))

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
    assert report["status"] == "passed"
    assert report["wheel_sha256"] == digest
    assert report["cases"] == {case: "passed" for case in observed}
    assert observed == ["inventory", "evidence", "query", "read"]
    assert report["cleanup"] == "passed"


def test_source_probe_rejects_tree_leakage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    payload = {
        "module": "/workspace/svc_cli/__init__.py",
        "leaked": True,
        "removed": [],
        "textual": False,
    }
    monkeypatch.setattr(
        harness,
        "_command",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        ),
    )
    with pytest.raises(harness._CaseFailure):
        harness._run_source_probe(tmp_path / "python", tmp_path, {})
