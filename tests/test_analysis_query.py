from __future__ import annotations

import hashlib
import json

import pytest

from svc_cli.analysis.protocol import AnalysisProtocolError
from svc_cli.analysis.query import query_evidence, query_schema
from svc_cli.analysis.read import read_evidence
from svc_cli.telemetry.evidence import NativeIndexEntry, ValidatedEvidence
from svc_cli.telemetry.trajectory import ValidatedTrajectory, zero_lossiness


def evidence(
    *,
    projection_status: str = "ready",
    malformed: bool = False,
) -> ValidatedEvidence:
    values: list[bytes] = [
        b'{"type":"session_meta","payload":{"id":"thread"}}\n',
        b'{"type":"response_item","payload":{"type":"message","role":"user","content":"fix parser"}}\n',
        b'{"type":"response_item","payload":{"type":"message","role":"assistant","content":"done"}}\n',
        b'{"type":"response_item","payload":{"type":"function_call","name":"apply_patch","call_id":"c"}}\n',
    ]
    if malformed:
        values[2] = b"{not-json}\n"
    native = b"".join(values)
    entries: list[NativeIndexEntry] = []
    offset = 0
    for ordinal, frame in enumerate(values):
        entries.append(
            NativeIndexEntry(
                native_record_id=f"n{ordinal:06d}",
                native_index=ordinal,
                byte_start=offset,
                byte_end=offset + len(frame),
                sha256=hashlib.sha256(frame).hexdigest(),
                representation="provider-bytes",
                frame_status="complete",
                source_coordinate={
                    "event_index": ordinal,
                    "line": ordinal,
                    "byte_offset": offset,
                },
            )
        )
        offset += len(frame)
    records: tuple[dict[str, object], ...] = (
        {
            "type": "meta",
            "record_id": "r000000",
            "source_ref": {"event_index": None, "component": "meta"},
        },
        {
            "type": "message",
            "record_id": "r000001",
            "role": "user",
            "source_ref": {
                "event_index": 1,
                "native_record_id": "n000001",
            },
        },
        {
            "type": "message",
            "record_id": "r000002",
            "role": "assistant",
            "source_ref": {
                "event_index": 2,
                "native_record_id": "n000002",
            },
        },
        {
            "type": "tool_call",
            "record_id": "r000003",
            "name": "apply_patch",
            "turn_ref": "turn_" + "a" * 64,
            "source_ref": {
                "event_index": 3,
                "native_record_id": "n000003",
            },
        },
    )
    loss = zero_lossiness()
    if projection_status == "partial":
        loss["dropped"]["unsupported_record"] = 1
    return ValidatedEvidence(
        manifest={
            "capture": {
                "status": "complete",
                "unknown_remainder": False,
                "representation": "provider-bytes",
            },
            "projection": {
                "source": {
                    "provider_id": "codex",
                    "adapter_id": "codex-rollout-v1",
                    "source_format": "rollout-v1",
                    "thread_ref": "thread_" + "b" * 64,
                    "source_status": "stable",
                },
                "result_status": projection_status,
                "capabilities": {
                    "reasoning": "absent",
                    "tool_linkage": "explicit",
                    "context": "absent",
                    "task_references": "available",
                    "explicit_concurrency": "unavailable",
                    "timestamps": "full",
                    "terminal_events": "unavailable",
                },
                "lossiness": loss,
            },
        },
        native=native,
        native_index=tuple(entries),
        trajectory=ValidatedTrajectory(
            records,
            b"",
            hashlib.sha256(b"").hexdigest(),
        ),
        evidence_id="e" * 64,
    )


def test_query_schema_is_directly_actionable_for_an_agent() -> None:
    schema = query_schema()
    assert schema["format"] == "svc.analysis.query.schema/v1"
    assert set(schema["intents"]) == {"overview", "match"}
    match_contract = schema["intents"]["match"]
    assert match_contract["initial"]["required"] == ["intent", "predicates"]
    assert match_contract["initial"]["additional_properties"] is False
    assert match_contract["continuation"]["required"] == ["intent", "cursor"]
    assert match_contract["continuation"]["additional_properties"] is False
    assert match_contract["predicates"]["text"]["shape"]["case_sensitive"] is False
    assert match_contract["predicates"]["text"]["bounds"] == {
        "terms": [1, 8],
        "term_code_points": [1, 256],
    }
    assert match_contract["predicates"]["native_range"]["reference"]["record_kind"] == "native"
    assert match_contract["predicates"]["native_range"]["reference"]["additional_properties"] is False
    assert schema["response_format"] == "svc.analysis.query/v1"
    assert schema["method_lookup"]["read_section"] == "Agent Task Analysis"


def test_overview_exposes_boundary_not_findings() -> None:
    result = query_evidence(evidence(), {"intent": "overview"})
    assert result["status"] == "complete"
    assert result["native_range"]["records"] == 4
    assert result["method"]["section"] == "Agent Task Analysis"
    assert "findings" not in result
    assert [item["record_type"] for item in result["structural_ranges"]] == [
        "meta",
        "message",
        "tool_call",
    ]


def test_match_intersects_structure_and_native_text_then_reads_exact_context() -> None:
    source = evidence()
    result = query_evidence(
        source,
        {
            "intent": "match",
            "predicates": {
                "record_types": ["message"],
                "roles": ["user"],
                "text": {
                    "terms": ["parser"],
                    "mode": "all",
                },
            },
        },
    )
    assert result["status"] == "complete"
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["ref"]["record_id"] == "n000001"
    assert item["matched_terms"] == ["parser"]

    raw = read_evidence(
        source,
        {"start": item["ref"], "max_items": 1},
    )
    payload = raw["items"][0]["payload"]
    assert "fix parser" in payload["text"]


def test_empty_complete_and_projection_or_native_coverage_partial() -> None:
    no_match = query_evidence(
        evidence(),
        {
            "intent": "match",
            "predicates": {
                "text": {"terms": ["absent"], "mode": "any"},
            },
        },
    )
    assert no_match["status"] == "complete"
    assert no_match["items"] == []

    projection_partial = query_evidence(
        evidence(projection_status="partial"),
        {
            "intent": "match",
            "predicates": {"record_types": ["event"]},
        },
    )
    assert projection_partial["status"] == "partial"

    native_partial = query_evidence(
        evidence(malformed=True),
        {
            "intent": "match",
            "predicates": {
                "text": {"terms": ["absent"], "mode": "any"},
            },
        },
    )
    assert native_partial["status"] == "partial"


def test_unavailable_capability_is_not_a_negative_finding() -> None:
    result = query_evidence(
        evidence(),
        {
            "intent": "match",
            "predicates": {"record_types": ["reasoning"]},
        },
    )
    assert result["status"] == "unavailable"
    assert result["items"] == []


def test_match_cursor_continues_deterministically() -> None:
    source = evidence()
    first = query_evidence(
        source,
        {
            "intent": "match",
            "predicates": {"record_types": ["message"]},
            "max_items": 1,
        },
    )
    assert [item["ref"]["record_id"] for item in first["items"]] == ["n000001"]
    second = query_evidence(
        source,
        {
            "intent": "match",
            "cursor": first["next_cursor"],
            "max_items": 10,
        },
    )
    assert [item["ref"]["record_id"] for item in second["items"]] == ["n000002"]
    assert second["next_cursor"] is None

    with pytest.raises(AnalysisProtocolError) as malformed:
        query_evidence(
            source,
            {
                "intent": "match",
                "cursor": "not-a-cursor",
            },
        )
    assert malformed.value.code == "invalid-cursor"


@pytest.mark.parametrize(
    "query_request",
    (
        {},
        {"intent": "overview", "extra": True},
        {"intent": "match", "predicates": {}},
        {
            "intent": "match",
            "predicates": {"text": {"terms": ["x"], "mode": "regex"}},
        },
        {
            "intent": "match",
            "predicates": {"sql": "select *"},
        },
    ),
)
def test_query_union_and_predicates_are_closed(query_request: object) -> None:
    with pytest.raises(AnalysisProtocolError) as raised:
        query_evidence(evidence(), query_request)
    assert raised.value.code == "invalid-query-request"
