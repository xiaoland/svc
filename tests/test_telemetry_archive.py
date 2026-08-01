from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

from svc_cli.errors import SvcError
from svc_cli.telemetry.agent_threads import ProviderContext, ThreadSelection
from svc_cli.telemetry.archive import write_agent_thread_evidence
from svc_cli.telemetry.evidence import EVIDENCE_MEMBERS, validate_evidence
from svc_cli.telemetry.providers.codex_rollout import CodexRolloutProvider


def _rollout(path: Path, *, valid: bool = True) -> bytes:
    records = (
        {
            "timestamp": "2026-01-01T00:00:00Z",
            "type": "session_meta",
            "payload": {"id": "thread-v3"},
        },
        {
            "timestamp": "2026-01-01T00:00:01Z",
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": "done",
            },
        },
    )
    content = (
        b"{}\n"
        if not valid
        else (
            "\n".join(json.dumps(item, separators=(",", ":")) for item in records)
            + "\n"
        ).encode()
    )
    path.write_bytes(content)
    return content


def _export(source: Path, output: Path) -> dict[str, object]:
    return write_agent_thread_evidence(
        CodexRolloutProvider(),
        ProviderContext(home=source.parent),
        ThreadSelection(source=source),
        output,
    )


def test_export_preserves_one_native_authority(tmp_path: Path) -> None:
    source = tmp_path / "rollout.jsonl"
    native = _rollout(source)
    output = tmp_path / "evidence.zip"

    manifest = _export(source, output)
    evidence = validate_evidence(output)

    assert evidence.native == native == source.read_bytes()
    assert evidence.evidence_id == manifest["evidence_id"]
    assert [
        record["source_ref"].get("native_record_id")
        for record in evidence.trajectory.records
    ] == [None, "n000001"]
    with zipfile.ZipFile(output) as archive:
        assert tuple(archive.namelist()) == EVIDENCE_MEMBERS


def test_export_never_overwrites_a_valid_bundle(tmp_path: Path) -> None:
    source = tmp_path / "rollout.jsonl"
    native = _rollout(source)
    output = tmp_path / "evidence.zip"
    _export(source, output)

    with pytest.raises(FileExistsError):
        _export(source, output)

    assert validate_evidence(output).native == native


def test_provider_failure_leaves_no_artifact(tmp_path: Path) -> None:
    source = tmp_path / "invalid.jsonl"
    _rollout(source, valid=False)
    output = tmp_path / "evidence.zip"

    with pytest.raises(SvcError):
        _export(source, output)

    assert not output.exists()
