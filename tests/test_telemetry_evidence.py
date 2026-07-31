from __future__ import annotations

from io import BytesIO
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from svc_cli.telemetry.evidence import (
    EvidenceError,
    build_evidence_id,
    build_evidence_manifest,
    build_native_index,
    validate_evidence,
    validate_evidence_members,
    write_evidence,
)
from svc_cli.telemetry.trajectory import build_manifest, canonical_json_bytes, zero_lossiness


def _meta() -> dict[str, object]:
    return {
        "type": "meta",
        "record_id": "r000000",
        "record_index": 0,
        "timestamp": None,
        "source_ref": {"event_index": None, "component": "meta"},
        "trajectory_schema": "svc.trajectory/v1",
        "provider_id": "codex",
        "adapter_id": "codex-rollout-v1",
        "source_format": "rollout-v1",
        "thread_ref": "thread_" + "a" * 64,
        "workspace": {
            "status": "missing",
            "flavor": None,
            "label": None,
            "ref": None,
            "label_truncated": False,
            "observed_code_points": 0,
            "retained_code_points": 0,
        },
        "content_profile": "bounded-normalized-v1",
    }


def _message() -> dict[str, object]:
    return {
        "type": "message",
        "record_id": "r000001",
        "record_index": 1,
        "timestamp": "2026-01-01T00:00:01Z",
        "source_ref": {
            "event_index": 1,
            "line": 1,
            "byte_offset": 5,
            "native_record_id": "n000001",
        },
        "role": "user",
        "content": "hello",
        "content_meta": {
            "truncated": False,
            "observed_code_points": 5,
            "retained_code_points": 5,
            "strategy": "none",
        },
        "task_refs": [],
    }


def _projection(trajectory: bytes) -> dict[str, object]:
    return dict(build_manifest(
        trajectory_source=trajectory,
        source={
            "provider_id": "codex",
            "adapter_id": "codex-rollout-v1",
            "source_format": "rollout-v1",
            "thread_ref": "thread_" + "a" * 64,
            "source_status": "stable",
        },
        result_status="ready",
        capabilities={
            "reasoning": "absent",
            "tool_linkage": "absent",
            "context": "absent",
            "task_references": "available",
            "explicit_concurrency": "unavailable",
            "timestamps": "full",
            "terminal_events": "unavailable",
        },
        lossiness=zero_lossiness(),
        diagnostics=[],
        counts={
            "source_bytes_read": 10,
            "source_events_seen": 2,
            "records_emitted": 2,
            "trajectory_bytes": len(trajectory),
            "records_by_type": {"meta": 1, "message": 1, "reasoning": 0, "tool_call": 0, "tool_result": 0, "context": 0, "event": 0},
            "messages_by_role": {"user": 1, "assistant": 0},
            "tool_calls": 0,
            "tool_results": 0,
            "task_references": 0,
            "diagnostics_emitted": 0,
            "diagnostics_suppressed": 0,
        },
    ))


def _fixture() -> tuple[dict[str, object], bytes, bytes, bytes]:
    trajectory = canonical_json_bytes(_meta(), newline=True) + canonical_json_bytes(_message(), newline=True)
    projection = _projection(trajectory)
    native = b"meta\nmessage\n"
    native_index = build_native_index(
        native,
        [
            (0, 5, {"event_index": 0, "line": 0, "byte_offset": 0}, "complete"),
            (5, len(native), {"event_index": 1, "line": 1, "byte_offset": 5}, "complete"),
        ],
    )
    manifest = dict(
        build_evidence_manifest(
            native=native,
            native_index=native_index,
            projection=projection,
            trajectory=trajectory,
        )
    )
    return manifest, native, native_index, trajectory


def test_schema_v3_round_trip_has_exact_members_and_native_coverage(tmp_path: Path) -> None:
    manifest, native, native_index, trajectory = _fixture()
    target = tmp_path / "evidence.zip"
    result = write_evidence(target, manifest, native, native_index, trajectory)
    assert result.evidence_id == manifest["evidence_id"]
    with zipfile.ZipFile(target) as archive:
        assert archive.namelist() == ["manifest.json", "native.bin", "native-index.jsonl", "trajectory.jsonl"]
        assert archive.read("native.bin") == native
        assert archive.read("native-index.jsonl") == native_index
        assert all(((info.external_attr >> 16) & 0o777) == 0o644 for info in archive.infolist())
    validated = validate_evidence(target)
    assert validated.native == native
    assert [entry.native_record_id for entry in validated.native_index] == ["n000000", "n000001"]
    assert validated.trajectory.records[1]["source_ref"]["native_record_id"] == "n000001"


def test_native_index_requires_exact_cover_and_digest() -> None:
    manifest, native, native_index, trajectory = _fixture()
    lines = [json.loads(line) for line in native_index.splitlines()]
    lines[1]["byte_start"] = lines[1]["byte_start"] + 1
    broken_index = b"".join(canonical_json_bytes(line, newline=True) for line in lines)
    broken_manifest = dict(manifest)
    broken_manifest["native_index"] = {
        **manifest["native_index"],
        "sha256": hashlib.sha256(broken_index).hexdigest(),
        "bytes": len(broken_index),
    }
    with pytest.raises(EvidenceError) as raised:
        validate_evidence_members(broken_manifest, native, broken_index, trajectory)
    assert raised.value.code == "invalid-native-index"


def test_trajectory_refs_must_resolve_complete_native_frames() -> None:
    manifest, native, native_index, trajectory = _fixture()
    record = json.loads(trajectory.splitlines()[1])
    del record["source_ref"]["native_record_id"]
    missing_ref = canonical_json_bytes(_meta(), newline=True) + canonical_json_bytes(record, newline=True)
    missing_manifest = dict(manifest)
    missing_manifest["projection"] = _projection(missing_ref)
    missing_manifest["evidence_id"] = build_evidence_id(missing_manifest, native, native_index, missing_ref)
    with pytest.raises(EvidenceError) as raised:
        validate_evidence_members(missing_manifest, native, native_index, missing_ref)
    assert raised.value.code == "native-reference-missing"

    incomplete_index = build_native_index(
        native,
        [
            (0, 5, {"event_index": 0, "line": 0, "byte_offset": 0}, "complete"),
            (5, len(native), {"event_index": 1, "line": 1, "byte_offset": 5}, "incomplete"),
        ],
    )
    incomplete_manifest = dict(manifest)
    incomplete_manifest["native_index"] = {
        **manifest["native_index"],
        "sha256": hashlib.sha256(incomplete_index).hexdigest(),
        "bytes": len(incomplete_index),
    }
    incomplete_manifest["capture"] = {
        "status": "partial",
        "unknown_remainder": True,
        "representation": "provider-bytes",
    }
    incomplete_manifest["evidence_id"] = build_evidence_id(
        incomplete_manifest, native, incomplete_index, trajectory
    )
    with pytest.raises(EvidenceError) as raised:
        validate_evidence_members(incomplete_manifest, native, incomplete_index, trajectory)
    assert raised.value.code == "native-reference-incomplete"


def test_incomplete_final_native_frame_derives_partial_capture_metadata() -> None:
    _manifest, _native, _native_index, trajectory = _fixture()
    native = b"meta\nmessage\ntail"
    native_index = build_native_index(
        native,
        [
            (0, 5, {"event_index": 0, "line": 0, "byte_offset": 0}, "complete"),
            (5, 13, {"event_index": 1, "line": 1, "byte_offset": 5}, "complete"),
            (13, len(native), {"event_index": 2, "line": 2, "byte_offset": 13}, "incomplete"),
        ],
    )
    manifest = build_evidence_manifest(
        native=native,
        native_index=native_index,
        projection=_projection(trajectory),
        trajectory=trajectory,
    )
    assert manifest["capture"] == {
        "status": "partial",
        "unknown_remainder": True,
        "representation": "provider-bytes",
    }


def test_schema_v2_is_rejected_before_reading_other_members(tmp_path: Path) -> None:
    target = tmp_path / "old.zip"
    old_manifest = {"format": "svc-agent-thread-bundle", "schema_version": 2}
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("manifest.json", canonical_json_bytes(old_manifest, newline=True))
        archive.writestr("native.bin", b"not-read")
        archive.writestr("native-index.jsonl", b"not-read")
        archive.writestr("trajectory.jsonl", b"not-read")

    opened: list[str] = []

    def member_open(archive: zipfile.ZipFile, info: zipfile.ZipInfo):
        opened.append(info.filename)
        return archive.open(info, "r")

    with pytest.raises(EvidenceError) as raised:
        validate_evidence(target, member_open=member_open)
    assert raised.value.code == "unsupported-agent-thread-bundle-schema"
    assert opened == ["manifest.json"]
