from __future__ import annotations

import copy
from io import BytesIO
import hashlib
import json

import pytest

from svc_cli.telemetry.trajectory import (
    MAX_NATIVE_JSON_DEPTH,
    TrajectoryCollector,
    TrajectoryError,
    build_manifest,
    canonical_json_bytes,
    validate_manifest,
    validate_trajectory_bytes,
    zero_lossiness,
)


def _ref(kind: str) -> str:
    return f"{kind}_{'a' * 64}"


def _bounded(value: str) -> dict[str, object]:
    return {
        "truncated": False,
        "observed_code_points": len(value),
        "retained_code_points": len(value),
        "strategy": "none",
    }


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
        "thread_ref": _ref("thread"),
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


def _message(index: int = 1, content: str = "hello") -> dict[str, object]:
    return {
        "type": "message",
        "record_id": f"r{index:06d}",
        "record_index": index,
        "timestamp": "2026-01-01T00:00:01Z",
        "source_ref": {"event_index": index, "line": index + 1},
        "role": "user",
        "content": content,
        "content_meta": _bounded(content),
        "task_refs": [],
    }


def _trajectory() -> bytes:
    return canonical_json_bytes(_meta(), newline=True) + canonical_json_bytes(
        _message(),
        newline=True,
    )


def _manifest(trajectory: bytes) -> dict[str, object]:
    return dict(
        build_manifest(
            trajectory_source=trajectory,
            source={
                "provider_id": "codex",
                "adapter_id": "codex-rollout-v1",
                "source_format": "rollout-v1",
                "thread_ref": _ref("thread"),
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
                "source_events_seen": 1,
                "records_emitted": 2,
                "trajectory_bytes": len(trajectory),
                "records_by_type": {
                    "meta": 1,
                    "message": 1,
                    "reasoning": 0,
                    "tool_call": 0,
                    "tool_result": 0,
                    "context": 0,
                    "event": 0,
                },
                "messages_by_role": {"user": 1, "assistant": 0},
                "tool_calls": 0,
                "tool_results": 0,
                "task_references": 0,
                "diagnostics_emitted": 0,
                "diagnostics_suppressed": 0,
            },
        )
    )


def test_collector_emits_one_canonical_stream() -> None:
    output = BytesIO()
    collector = TrajectoryCollector(output)
    assert collector.emit(_meta())
    assert collector.emit(_message())

    encoded = collector.finish()
    expected = _trajectory()

    assert encoded.trajectory_bytes is None
    assert output.getvalue() == expected
    assert encoded.trajectory_size == len(expected)
    assert encoded.trajectory_sha256 == hashlib.sha256(expected).hexdigest()
    assert encoded.records_by_type["message"] == 1


def test_trajectory_rejects_invalid_json_and_record_sequence() -> None:
    canonical = canonical_json_bytes(_meta(), newline=True)
    assert validate_trajectory_bytes(canonical).trajectory_sha256 == hashlib.sha256(
        canonical
    ).hexdigest()

    deep: object = {}
    for _ in range(MAX_NATIVE_JSON_DEPTH + 1):
        deep = {"nested": deep}
    invalid_streams = (
        b'{"type":"meta","type":"meta"}\n',
        json.dumps(_meta(), ensure_ascii=False).encode() + b"\n",
        canonical_json_bytes(deep, newline=True),
        canonical_json_bytes(_message(0), newline=True),
        canonical + canonical_json_bytes(_message(2), newline=True),
    )
    for data in invalid_streams:
        with pytest.raises(TrajectoryError):
            validate_trajectory_bytes(data)


def test_manifest_rejects_invalid_time_and_removed_contracts() -> None:
    trajectory = _trajectory()
    valid = _manifest(trajectory)
    valid["generated_at"] = "2026-12-31T23:59:59.123456789Z"
    validate_manifest(valid)

    for timestamp in (
        "2026-02-29T00:00:00Z",
        "2026-01-01T00:00:60Z",
        "2026-01-01T00:00:00+00:00",
        "2026-01-01T00:00Z",
    ):
        invalid = dict(valid)
        invalid["generated_at"] = timestamp
        with pytest.raises(TrajectoryError):
            validate_manifest(invalid)

    for section, key, value in (
        ("policy", "redaction", "none"),
        ("source", "source_status", "displaced"),
    ):
        invalid = copy.deepcopy(valid)
        invalid[section][key] = value
        with pytest.raises(TrajectoryError):
            validate_manifest(invalid)


def test_manifest_diagnostics_are_ordered_and_resolvable() -> None:
    trajectory = _trajectory()
    base = _manifest(trajectory)
    first = {
        "code": "noise-record-dropped",
        "severity": "info",
        "action": "drop",
        "count": 1,
        "record_ref": None,
        "source_ref": {"event_index": 2},
        "details": {"record_type": "ui"},
    }
    second = {
        **first,
        "source_ref": {"event_index": 1},
        "details": {"record_type": "world_state"},
    }
    invalid_diagnostics = (
        [first, second],
        [second, dict(second)],
        [
            {
                "code": "orphan-tool-result",
                "severity": "warning",
                "action": "unavailable",
                "count": 1,
                "record_ref": "r999999",
                "source_ref": {"event_index": 1},
                "details": {},
            }
        ],
    )
    for diagnostics in invalid_diagnostics:
        invalid = copy.deepcopy(base)
        invalid["diagnostics"] = diagnostics
        invalid["counts"]["diagnostics_emitted"] = len(diagnostics)
        with pytest.raises(TrajectoryError):
            validate_manifest(
                invalid,
                trajectory=validate_trajectory_bytes(trajectory),
            )
