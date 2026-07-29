from __future__ import annotations

import hashlib
import pytest

from svc_cli.telemetry.analysis import AnalysisError, analyze_trajectory, canonical_analysis_bytes, validate_analysis
from svc_cli.telemetry.trajectory import RECORD_TYPES, ValidatedBundle, build_manifest, canonical_json_bytes, validate_trajectory_bytes, zero_lossiness


def ref(kind: str, char: str = "a") -> str:
    return f"{kind}_{char * 64}"


def bound(value: str) -> dict[str, object]:
    return {"truncated": False, "observed_code_points": len(value), "retained_code_points": len(value), "strategy": "none"}


def make_bundle() -> ValidatedBundle:
    meta = {
        "type": "meta", "record_id": "r000000", "record_index": 0, "timestamp": None,
        "source_ref": {"event_index": None, "component": "meta"}, "trajectory_schema": "svc.trajectory/v1",
        "provider_id": "codex", "adapter_id": "codex-rollout-v1", "source_format": "rollout-v1", "thread_ref": ref("thread"),
        "workspace": {"status": "missing", "flavor": None, "label": None, "ref": None, "label_truncated": False, "observed_code_points": 0, "retained_code_points": 0},
        "content_profile": "bounded-normalized-v1",
    }
    message = {
        "type": "message", "record_id": "r000001", "record_index": 1, "timestamp": "2026-01-01T00:00:00Z", "source_ref": {"event_index": 1},
        "role": "user", "content": "work on tasks/v10/packet.md", "content_meta": bound("work on tasks/v10/packet.md"), "task_refs": ["tasks/v10/packet.md"],
    }
    trajectory = canonical_json_bytes(meta, newline=True) + canonical_json_bytes(message, newline=True)
    manifest = build_manifest(
        trajectory_source=trajectory,
        source={"provider_id": "codex", "adapter_id": "codex-rollout-v1", "source_format": "rollout-v1", "thread_ref": ref("thread"), "source_status": "stable"},
        result_status="ready",
        capabilities={"reasoning": "absent", "tool_linkage": "absent", "context": "absent", "task_references": "available", "explicit_concurrency": "unavailable", "timestamps": "full", "terminal_events": "unavailable"},
        lossiness=zero_lossiness(), diagnostics=[],
        counts={"source_bytes_read": len(trajectory), "source_events_seen": 2, "records_emitted": 2, "trajectory_bytes": len(trajectory), "records_by_type": {"meta": 1, "message": 1, "reasoning": 0, "tool_call": 0, "tool_result": 0, "context": 0, "event": 0}, "messages_by_role": {"user": 1, "assistant": 0}, "tool_calls": 0, "tool_results": 0, "task_references": 1, "diagnostics_emitted": 0, "diagnostics_suppressed": 0},
    )
    return ValidatedBundle(manifest, validate_trajectory_bytes(trajectory), manifest["bundle_id"])


def _record(index: int, record_type: str, **fields: object) -> dict[str, object]:
    return {"type": record_type, "record_id": f"r{index:06d}", "record_index": index, "timestamp": f"2026-01-01T00:00:{index:02d}Z", "source_ref": {"event_index": index}, **fields}


def make_scenario(*, approvals: int = 1, terminal: bool = True, loss: bool = False) -> ValidatedBundle:
    """Small AN-Q1..Q10 fixture: all structured evidence, no native text leakage."""
    thread = ref("thread", "b")
    turn = ref("turn", "c")
    lane = ref("lane", "e")
    actor = ref("actor", "f")
    parent = ref("actor", "a")
    records: list[dict[str, object]] = [{
        "type": "meta", "record_id": "r000000", "record_index": 0, "timestamp": None,
        "source_ref": {"event_index": None, "component": "meta"}, "trajectory_schema": "svc.trajectory/v1",
        "provider_id": "codex", "adapter_id": "codex-rollout-v1", "source_format": "rollout-v1", "thread_ref": thread,
        "workspace": {"status": "missing", "flavor": None, "label": None, "ref": None, "label_truncated": False, "observed_code_points": 0, "retained_code_points": 0},
        "content_profile": "bounded-normalized-v1",
    }]
    records.append(_record(1, "message", role="user", content="work", content_meta=bound("work"), task_refs=["tasks/v10/packet.md"]))
    records.append(_record(2, "context", context_kind="system", content="first", content_meta=bound("first"), attributes={}, attributes_meta={}, fingerprint=""))
    context_payload = {"context_kind": "system", "content": "first", "content_meta": bound("first"), "attributes": {}, "attributes_meta": {}}
    records[-1]["fingerprint"] = hashlib.sha256(b"svc-context-v1\0" + canonical_json_bytes(context_payload)).hexdigest()
    records.append(_record(3, "message", role="assistant", content="reply", content_meta=bound("reply"), task_refs=[]))
    name = "runner"
    name_fp = hashlib.sha256(b"svc-tool-name-v1\0" + name.encode()).hexdigest()
    arguments = '{"cmd":"pdm run svc lookup"}'
    arguments_fp = hashlib.sha256(b"svc-tool-arguments-v1\0" + arguments.encode()).hexdigest()
    for offset, status in ((4, "error"), (5, "error"), (6, "error")):
        call_id = ref("call", "a" if offset == 4 else "b" if offset == 5 else "c")
        records.append(_record(offset, "tool_call", tool_call_id=call_id, name=name, name_meta=bound(name), name_fingerprint=name_fp, arguments_kind="json", arguments=arguments, arguments_meta=bound(arguments), arguments_fingerprint=arguments_fp, turn_ref=turn, lane_ref=lane, actor_ref=actor, parent_actor_ref=parent))
        records.append(_record(offset + 7, "tool_result", tool_call_id=call_id, content=status, content_meta=bound(status), status=status, link_status="linked", turn_ref=turn, lane_ref=lane, actor_ref=actor))
    # Re-index the records after interleaving the repeated tool pairs.
    for index, item in enumerate(records):
        item["record_id"] = f"r{index:06d}"
        item["record_index"] = index
        if index:
            item["source_ref"] = {"event_index": index}
            item["timestamp"] = f"2026-01-01T00:00:{index:02d}Z"
    next_index = len(records)
    for index in range(approvals):
        records.append(_record(next_index + index, "event", event_kind="approval", outcome="granted", turn_ref=turn))
    next_index = len(records)
    records.append(_record(next_index, "message", role="user", content="follow-up", content_meta=bound("follow-up"), task_refs=[]))
    next_index = len(records)
    records.append(_record(next_index, "context", context_kind="system", content="second", content_meta=bound("second"), attributes={}, attributes_meta={}, fingerprint=""))
    context_payload = {"context_kind": "system", "content": "second", "content_meta": bound("second"), "attributes": {}, "attributes_meta": {}}
    records[-1]["fingerprint"] = hashlib.sha256(b"svc-context-v1\0" + canonical_json_bytes(context_payload)).hexdigest()
    if terminal:
        records.append(_record(len(records), "event", event_kind="turn_complete", outcome="completed", turn_ref=turn))
    for index, item in enumerate(records):
        item["record_id"] = f"r{index:06d}"
        item["record_index"] = index
    trajectory = b"".join(canonical_json_bytes(item, newline=True) for item in records)
    counts = {"source_bytes_read": len(trajectory), "source_events_seen": len(records), "records_emitted": len(records), "trajectory_bytes": len(trajectory), "records_by_type": {key: sum(item["type"] == key for item in records) for key in RECORD_TYPES}, "messages_by_role": {role: sum(item.get("role") == role for item in records if item["type"] == "message") for role in ("user", "assistant")}, "tool_calls": sum(item["type"] == "tool_call" for item in records), "tool_results": sum(item["type"] == "tool_result" for item in records), "task_references": 1, "diagnostics_emitted": 0, "diagnostics_suppressed": 0}
    capabilities = {"reasoning": "absent", "tool_linkage": "explicit", "context": "full", "task_references": "available", "explicit_concurrency": "available", "timestamps": "full", "terminal_events": "available"}
    lossiness = zero_lossiness()
    result_status = "ready"
    if loss:
        lossiness["partial_reasons"]["record_limit"] = 1
        result_status = "partial"
    manifest = build_manifest(trajectory_source=trajectory, source={"provider_id": "codex", "adapter_id": "codex-rollout-v1", "source_format": "rollout-v1", "thread_ref": thread, "source_status": "stable"}, result_status=result_status, capabilities=capabilities, lossiness=lossiness, diagnostics=[], counts=counts)
    return ValidatedBundle(manifest, validate_trajectory_bytes(trajectory), manifest["bundle_id"])


class TestAnalysis:
    def test_an_q1_to_q10_structured_fixture(self) -> None:
        payload = analyze_trajectory(make_scenario()).payload
        assert (payload["dimensions"]["task_evidence"]["status"]) == ("available")
        assert (payload["metrics"]["task_evidence"]["user_turn_count"]) == (2)
        assert (payload["dimensions"]["interaction_transitions"]["status"]) == ("available")
        assert (payload["metrics"]["interaction_transitions"]["structured_approval_count"]) == (1)
        assert (payload["metrics"]["constraint_evidence"]["context_record_count"]) == (2)
        assert (payload["metrics"]["tool_outcomes"]["error"]) == (3)
        assert (payload["metrics"]["loop_candidates"]["loop_candidate_count"]) == (1)
        assert (payload["metrics"]["loop_candidates"]["stall_candidate_count"]) == (1)
        assert (payload["metrics"]["lanes"]["lane_count"]) == (1)
        assert (payload["metrics"]["terminal_coverage"]["status"]) == ("completed")
        assert (payload["metrics"]["svc_signals"]["svc_cli_calls"]) == (3)
        assert (payload["metrics"]["svc_signals"]["signals"][1]["count"]) == (3)
        assert (payload["metrics"]["context_changes"]["changes"]) == (1)
        assert (payload["dimensions"]["coverage"]["status"]) == ("available")

    def test_an_q7_missing_terminal_and_an_q10_partial_loss(self) -> None:
        missing = analyze_trajectory(make_scenario(terminal=False)).payload
        assert (missing["dimensions"]["terminal_coverage"]["status"]) == ("unavailable")
        assert (missing["metrics"]["terminal_coverage"]["status"]) == ("unknown")
        assert (any(item["code"] == "terminal-evidence-unavailable" for item in missing["unknowns"]))
        partial = analyze_trajectory(make_scenario(loss=True)).payload
        assert (partial["result_status"]) == ("partial")
        assert (partial["dimensions"]["coverage"]["status"]) == ("partial")
        assert (any(item["code"] == "coverage-partial" for item in partial["unknowns"]))
        assert (partial["metrics"]["terminal_coverage"]["tail_loss"])

    def test_an_capability_missing_dimensions_are_explicit(self) -> None:
        payload = analyze_trajectory(make_bundle()).payload
        assert (payload["dimensions"]["interaction_transitions"]["status"]) == ("unavailable")
        assert (payload["dimensions"]["tool_outcomes"]["status"]) == ("unavailable")
        assert (payload["dimensions"]["lanes"]["status"]) == ("unavailable")
        assert (payload["dimensions"]["terminal_coverage"]["status"]) == ("unavailable")
        assert (payload["dimensions"]["context_changes"]["status"]) == ("unavailable")

    def test_an_per_dimension_cap_and_limit_unknown(self) -> None:
        result = analyze_trajectory(make_scenario(approvals=30)).payload
        interaction = result["dimensions"]["interaction_transitions"]
        assert (interaction["status"]) == ("partial")
        assert (any(item["code"] == "analysis-limit-reached" and item["dimension"] == "interaction_transitions" for item in result["unknowns"]))
        assert ("finding") in (result["lossiness"]["analysis"]["limits_reached"])

    def test_an_validator_adversarial_and_output_bound(self) -> None:
        payload = dict(analyze_trajectory(make_scenario()).payload)
        findings = list(payload["findings"])
        findings[0] = dict(findings[0], details={"status": "leak"})
        payload["findings"] = findings
        with pytest.raises(AnalysisError):
            validate_analysis(payload)
        with pytest.raises(AnalysisError):
            canonical_analysis_bytes({"x": "x" * (2 * 1024 * 1024)})

    def test_exact_root_and_determinism(self) -> None:
        bundle = make_bundle()
        first = analyze_trajectory(bundle)
        second = analyze_trajectory(bundle)
        assert (first.json_bytes) == (second.json_bytes)
        assert (set(first.payload)) == ({"format", "schema_version", "bundle_id", "analyzer", "result_status", "dimensions", "metrics", "findings", "unknowns", "lossiness"})
        assert (len(first.json_bytes)) <= (2 * 1024 * 1024)
        assert (first.payload["metrics"]["task_evidence"]["task_references"][0]["path"]) == ("tasks/v10/packet.md")

    def test_schema_validator_rejects_wrong_ids_and_cross_bundle_refs(self) -> None:
        payload = dict(analyze_trajectory(make_bundle()).payload)
        validate_analysis(payload)
        findings = list(payload["findings"])
        if findings:
            findings[0] = dict(findings[0])
            refs = list(findings[0]["evidence_refs"])
            refs[0] = dict(refs[0], bundle_id="b" * 64)
            findings[0]["evidence_refs"] = refs
            payload["findings"] = findings
            with pytest.raises(AnalysisError):
                validate_analysis(payload)

    def test_bare_trajectory_is_not_an_analysis_authority(self) -> None:
        bundle = make_bundle()
        with pytest.raises(AnalysisError):
            analyze_trajectory(bundle.trajectory)  # type: ignore[arg-type]
