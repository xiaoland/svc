from __future__ import annotations

import copy
from io import BytesIO
import hashlib
import json
import pytest

from svc_cli.telemetry.trajectory import (
    DEFAULT_NORMALIZATION_POLICY,
    MAX_NATIVE_JSON_DEPTH,
    TrajectoryCollector,
    TrajectoryError,
    _validate_diagnostics,
    build_manifest,
    canonical_json_bytes,
    validate_manifest,
    zero_lossiness,
    validate_trajectory_bytes,
)


def ref(kind: str) -> str:
    return f"{kind}_{'a' * 64}"


def meta() -> dict[str, object]:
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
        "thread_ref": ref("thread"),
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


def bounded(value: str) -> dict[str, object]:
    return {
        "truncated": False,
        "observed_code_points": len(value),
        "retained_code_points": len(value),
        "strategy": "none",
    }


def message(index: int = 1, content: str = "hello") -> dict[str, object]:
    return {
        "type": "message",
        "record_id": f"r{index:06d}",
        "record_index": index,
        "timestamp": "2026-01-01T00:00:01Z",
        "source_ref": {"event_index": index, "line": index + 1},
        "role": "user",
        "content": content,
        "content_meta": bounded(content),
        "task_refs": [],
    }


class TestTrajectory:
    def _trajectory(self) -> bytes:
        return canonical_json_bytes(meta(), newline=True) + canonical_json_bytes(message(), newline=True)

    def _manifest(self, trajectory: bytes) -> dict[str, object]:
        return dict(build_manifest(
            trajectory_source=trajectory,
            source={
                "provider_id": "codex", "adapter_id": "codex-rollout-v1", "source_format": "rollout-v1",
                "thread_ref": ref("thread"), "source_status": "stable",
            },
            result_status="ready",
            capabilities={
                "reasoning": "absent", "tool_linkage": "absent", "context": "absent",
                "task_references": "available", "explicit_concurrency": "unavailable",
                "timestamps": "full", "terminal_events": "unavailable",
            },
            lossiness=zero_lossiness(),
            diagnostics=[],
            counts={
                "source_bytes_read": 10,
                "source_events_seen": 1,
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

    def test_collector_is_incremental_and_canonical(self) -> None:
        output = BytesIO()
        collector = TrajectoryCollector(output)
        assert (collector.emit(meta()))
        assert (collector.emit(message()))
        encoded = collector.finish()
        expected = canonical_json_bytes(meta(), newline=True) + canonical_json_bytes(message(), newline=True)
        assert (encoded.trajectory_bytes) is None
        assert (output.getvalue()) == (expected)
        assert (encoded.trajectory_size) == (len(expected))
        assert (encoded.trajectory_sha256) == (hashlib.sha256(expected).hexdigest())
        assert (encoded.records_by_type["message"]) == (1)

    def test_internal_collector_returns_bytes_and_caps_without_throwing(self) -> None:
        collector = TrajectoryCollector(policy=DEFAULT_NORMALIZATION_POLICY.__class__(records=1))
        assert (collector.emit(meta()))
        assert not (collector.emit(message()))
        assert (collector.limit_reason) == ("record_limit")
        assert (collector.finish().records) == (1)

    def test_malformed_record_raises_stable_error(self) -> None:
        collector = TrajectoryCollector()
        invalid = meta()
        invalid["record_id"] = "bad"
        with pytest.raises(TrajectoryError) as raised:
            collector.emit(invalid)
        assert (raised.value.code) == ("invalid-trajectory")

    def test_validate_rejects_duplicate_keys_noncanonical_and_excessive_depth(self) -> None:
        data = b'{"type":"meta","type":"meta"}\n'
        with pytest.raises(TrajectoryError) as raised:
            validate_trajectory_bytes(data)
        assert (raised.value.code) == ("invalid-json")

        canonical = canonical_json_bytes(meta(), newline=True)
        assert (validate_trajectory_bytes(canonical).trajectory_sha256) == (hashlib.sha256(canonical).hexdigest())
        noncanonical = json.dumps(meta(), ensure_ascii=False).encode() + b"\n"
        with pytest.raises(TrajectoryError):
            validate_trajectory_bytes(noncanonical)

        deep: object = {}
        for _ in range(MAX_NATIVE_JSON_DEPTH + 1):
            deep = {"nested": deep}
        with pytest.raises(TrajectoryError) as raised:
            validate_trajectory_bytes(canonical_json_bytes(deep, newline=True))
        assert raised.value.code == "json-depth-exceeded"

    def test_validate_requires_leading_meta_and_contiguous_ids(self) -> None:
        with pytest.raises(TrajectoryError):
            validate_trajectory_bytes(canonical_json_bytes(message(0), newline=True))
        broken = message(2)
        data = canonical_json_bytes(meta(), newline=True) + canonical_json_bytes(broken, newline=True)
        with pytest.raises(TrajectoryError):
            validate_trajectory_bytes(data)

    def test_event_and_tool_records_emit_with_expected_counts(self) -> None:
        call = {
            "type": "tool_call", "record_id": "r000001", "record_index": 1,
            "timestamp": "2026-01-01T00:00:01Z", "source_ref": {"event_index": 1},
            "tool_call_id": ref("call"), "name": "svc", "name_meta": bounded("svc"),
            "name_fingerprint": hashlib.sha256(b"svc-tool-name-v1\0svc").hexdigest(), "arguments_kind": "absent", "arguments": None,
            "arguments_meta": {"truncated": False, "observed_code_points": 0, "retained_code_points": 0, "strategy": "none"},
            "arguments_fingerprint": None,
        }
        event = {
            "type": "event", "record_id": "r000002", "record_index": 2,
            "timestamp": None, "source_ref": {"event_index": 2},
            "event_kind": "turn_abort", "outcome": "aborted",
        }
        collector = TrajectoryCollector()
        for item in (meta(), call, event):
            assert (collector.emit(item))
        result = collector.finish()
        assert result.tool_calls == 1
        assert result.records_by_type["event"] == 1

    def test_relationship_hash_starting_with_d_is_not_a_duplicate_suffix(
        self,
    ) -> None:
        record = message()
        record["actor_ref"] = "actor_" + ("d" * 64)
        collector = TrajectoryCollector()
        assert (collector.emit(meta()))
        assert (collector.emit(record))
        assert (collector.finish().records) == (2)

        invalid = message()
        invalid["actor_ref"] = (
            "actor_"
            + ("a" * 64)
            + "_d000001"
        )
        collector = TrajectoryCollector()
        assert (collector.emit(meta()))
        with pytest.raises(TrajectoryError):
            collector.emit(invalid)

    @pytest.mark.parametrize(
        "invalid_timestamp",
        (
            "2026-02-29T00:00:00Z",
            "2026-01-01T00:00:60Z",
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00Z",
        ),
    )
    def test_manifest_generated_at_requires_a_valid_utc_second_instant(
        self,
        invalid_timestamp: str,
    ) -> None:
        trajectory = self._trajectory()
        valid = self._manifest(trajectory)
        valid["generated_at"] = "2026-12-31T23:59:59.123456789Z"
        validate_manifest(valid)

        invalid = dict(valid)
        invalid["generated_at"] = invalid_timestamp
        with pytest.raises(TrajectoryError):
            validate_manifest(invalid)

    @pytest.mark.parametrize(
        ("section", "key", "value"),
        (
            ("policy", "redaction", "none"),
            ("source", "source_status", "displaced"),
        ),
    )
    def test_manifest_rejects_removed_wire_contracts(
        self,
        section: str,
        key: str,
        value: str,
    ) -> None:
        invalid = copy.deepcopy(self._manifest(self._trajectory()))
        invalid[section][key] = value
        with pytest.raises(TrajectoryError):
            validate_manifest(invalid)

    @pytest.mark.parametrize(
        "diagnostic_case",
        ("missing_source_ref", "unsorted", "duplicate", "unresolved_record_ref"),
    )
    def test_manifest_diagnostic_coordinates_are_ordered_and_resolvable(
        self,
        diagnostic_case: str,
    ) -> None:
        trajectory = self._trajectory()
        base = self._manifest(trajectory)

        if diagnostic_case == "missing_source_ref":
            invalid = copy.deepcopy(base)
            invalid["diagnostics"] = [{
                "code": "invalid-json-line",
                "severity": "warning",
                "action": "drop",
                "count": 1,
                "record_ref": None,
                "source_ref": None,
                "details": {},
            }]
            invalid["counts"]["diagnostics_emitted"] = 1
            with pytest.raises(TrajectoryError):
                validate_manifest(invalid)
            return

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
        invalid = copy.deepcopy(base)
        if diagnostic_case == "unsorted":
            invalid["diagnostics"] = [first, second]
        elif diagnostic_case == "duplicate":
            invalid["diagnostics"] = [second, dict(second)]
        else:
            invalid["diagnostics"] = [{
                "code": "orphan-tool-result",
                "severity": "warning",
                "action": "unavailable",
                "count": 1,
                "record_ref": "r999999",
                "source_ref": {"event_index": 1},
                "details": {},
            }]
        invalid["counts"]["diagnostics_emitted"] = len(invalid["diagnostics"])
        with pytest.raises(TrajectoryError):
            validate_manifest(invalid, trajectory=validate_trajectory_bytes(trajectory))

    @pytest.mark.parametrize(
        ("marker_details", "valid"),
        (
            ({"observed_count": 5, "limit_count": 3}, True),
            ({"observed_count": 5, "limit_count": 256}, False),
            ({"observed_count": 3, "limit_count": 3}, False),
        ),
    )
    def test_diagnostic_limit_marker_uses_declared_bound(
        self,
        marker_details: dict[str, int],
        valid: bool,
    ) -> None:
        regular = [
            {
                "code": "noise-record-dropped",
                "severity": "info",
                "action": "drop",
                "count": 1,
                "record_ref": None,
                "source_ref": {"event_index": index},
                "details": {"record_type": record_type},
            }
            for index, record_type in ((1, "ui"), (2, "world_state"))
        ]
        marker = {
            "code": "diagnostic-limit-reached",
            "severity": "warning",
            "action": "truncate",
            "count": 1,
            "record_ref": None,
            "source_ref": None,
            "details": marker_details,
        }
        if valid:
            validated = _validate_diagnostics(regular + [marker], diagnostic_limit=3)
            assert validated[-1]["details"] == marker_details
        else:
            with pytest.raises(TrajectoryError):
                _validate_diagnostics(regular + [marker], diagnostic_limit=3)

    def test_default_manifest_path_accepts_a_valid_limit_marker(self) -> None:
        manifest = copy.deepcopy(self._manifest(self._trajectory()))
        regular = [
            {
                "code": "message-truncated",
                "severity": "info",
                "action": "truncate",
                "count": 1,
                "record_ref": None,
                "source_ref": {
                    "event_index": index,
                    "line": index,
                    "component_index": 0,
                    "component": "message",
                },
                "details": {
                    "observed_code_points": index + 2,
                    "retained_code_points": 1,
                },
            }
            for index in range(255)
        ]
        regular.append(
            {
                "code": "diagnostic-limit-reached",
                "severity": "warning",
                "action": "truncate",
                "count": 1,
                "record_ref": None,
                "source_ref": None,
                "details": {
                    "observed_count": 300,
                    "limit_count": 256,
                },
            }
        )
        manifest["diagnostics"] = regular
        manifest["counts"]["diagnostics_emitted"] = 256
        validate_manifest(manifest)
