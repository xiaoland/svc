from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import zipfile

import pytest

from svc_cli.analysis.protocol import (
    AnalysisProtocolError,
    decode_cursor,
    encode_cursor,
)
from svc_cli.analysis.query import query_evidence, query_schema
from svc_cli.analysis.service import execute_query
from svc_cli.telemetry.evidence import validate_evidence
from svc_cli.telemetry.trajectory import canonical_json_bytes
from tests.agent_thread_contract import message_record, write_evidence_bundle


def _bundle(
    tmp_path: Path,
    name: str,
    *,
    projection_status: str = "ready",
    malformed_native: bool = False,
    assistant_content: str = "parser done",
) -> Path:
    frames = (
        b'{"type":"session_meta","payload":{"id":"thread"}}\n',
        b'{"type":"response_item","payload":{"type":"message","role":"user","content":"fix parser"}}\n',
        (
            b"{not-json}\n"
            if malformed_native
            else canonical_json_bytes(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": assistant_content,
                    },
                },
                newline=True,
            )
        ),
    )
    return write_evidence_bundle(
        tmp_path,
        name,
        frames,
        records=(
            message_record(1, "user", "fix parser"),
            message_record(2, "assistant", assistant_content),
        ),
        projection_status=projection_status,
    ).path


def test_schema_method_and_overview_form_one_navigation_contract(
    tmp_path: Path,
) -> None:
    schema = query_schema()
    overview = execute_query(_bundle(tmp_path, "overview"), {"intent": "overview"})

    assert schema["format"] == "svc.analysis.query.schema/v1"
    assert set(schema["intents"]) == {"overview", "match"}
    assert schema["intents"]["match"]["predicates"]["combination"] == (
        "intersection across supplied predicates"
    )
    assert schema["intents"]["match"]["continuation"]["additional_properties"] is False
    assert schema["intents"]["match"]["initial"]["optional"] == ["max_items"]
    assert schema["intents"]["match"]["bounds"] == {"max_items": [1, 100]}
    assert schema["method_lookup"]["read_section"] == "Agent Task Analysis"
    assert overview["method"] == schema["method"]
    assert overview["status"] == "complete"
    assert overview["native_range"]["records"] == 3
    assert [item["record_type"] for item in overview["structural_ranges"]] == [
        "meta",
        "message",
    ]
    assert "findings" not in overview


def test_match_intersection_distinguishes_results_from_coverage_status(
    tmp_path: Path,
) -> None:
    complete = _bundle(tmp_path, "complete")
    match = execute_query(
        complete,
        {
            "intent": "match",
            "predicates": {
                "record_types": ["message"],
                "roles": ["user"],
                "text": {"terms": ["fix", "PARSER"], "mode": "all"},
            },
        },
    )
    assert match["status"] == "complete"
    assert [item["ref"]["record_id"] for item in match["items"]] == ["n000001"]
    assert match["items"][0]["matched_terms"] == ["fix", "PARSER"]

    no_match = execute_query(
        complete,
        {
            "intent": "match",
            "predicates": {"text": {"terms": ["absent"], "mode": "any"}},
        },
    )
    projection_partial = execute_query(
        _bundle(tmp_path, "projection-partial", projection_status="partial"),
        {"intent": "match", "predicates": {"record_types": ["event"]}},
    )
    native_partial = execute_query(
        _bundle(tmp_path, "native-partial", malformed_native=True),
        {
            "intent": "match",
            "predicates": {"text": {"terms": ["absent"], "mode": "any"}},
        },
    )
    unavailable = execute_query(
        complete,
        {"intent": "match", "predicates": {"record_types": ["reasoning"]}},
    )
    assert (no_match["status"], no_match["items"]) == ("complete", [])
    assert projection_partial["status"] == "partial"
    assert native_partial["status"] == "partial"
    assert (unavailable["status"], unavailable["items"]) == ("unavailable", [])


def test_cursor_continuation_is_scoped_and_requests_are_closed(tmp_path: Path) -> None:
    source = _bundle(tmp_path, "cursor")
    first = execute_query(
        source,
        {
            "intent": "match",
            "predicates": {"record_types": ["message"]},
            "max_items": 1,
        },
    )
    cursor_payload = decode_cursor(first["next_cursor"])
    assert set(cursor_payload) == {
        "version",
        "tool",
        "evidence_id",
        "scope",
        "next_ordinal",
    }
    assert cursor_payload["scope"] == {"record_types": ["message"]}
    second = execute_query(
        source,
        {"intent": "match", "cursor": first["next_cursor"], "max_items": 10},
    )
    assert [item["ref"]["record_id"] for item in first["items"]] == ["n000001"]
    assert [item["ref"]["record_id"] for item in second["items"]] == ["n000002"]
    assert second["next_cursor"] is None

    other = _bundle(tmp_path, "other", assistant_content="different result")
    invalid_cases = (
        (
            other,
            {"intent": "match", "cursor": first["next_cursor"]},
            "cursor-scope-mismatch",
        ),
        (source, {"intent": "match", "cursor": "not-a-cursor"}, "invalid-cursor"),
        (source, {"intent": "overview", "extra": True}, "invalid-query-request"),
        (
            source,
            {
                "intent": "match",
                "predicates": {"record_types": ["message"]},
                "max_bytes": 65_536,
            },
            "invalid-query-request",
        ),
        (
            source,
            {
                "intent": "match",
                "predicates": {"record_types": ["message"]},
                "max_items": True,
            },
            "invalid-query-request",
        ),
        (source, {"intent": "match", "predicates": {}}, "invalid-query-request"),
        (
            source,
            {
                "intent": "match",
                "predicates": {"text": {"terms": ["x"], "mode": "regex"}},
            },
            "invalid-query-request",
        ),
        (
            source,
            {
                "intent": "match",
                "cursor": encode_cursor({**cursor_payload, "next_ordinal": True}),
            },
            "invalid-cursor",
        ),
    )
    for bundle, request, expected_code in invalid_cases:
        with pytest.raises(AnalysisProtocolError) as raised:
            execute_query(bundle, request)
        assert raised.value.code == expected_code


def test_missing_projection_is_explicitly_unavailable(tmp_path: Path) -> None:
    source = _bundle(tmp_path, "no-projection")
    evidence = validate_evidence(source)
    evidence = replace(evidence, trajectory=None)

    overview = query_evidence(evidence, {"intent": "overview"})
    match = query_evidence(
        evidence,
        {
            "intent": "match",
            "predicates": {"text": {"terms": ["parser"], "mode": "any"}},
        },
    )

    assert overview["status"] == "unavailable"
    assert overview["projection"]["result_status"] == "projection-unavailable"
    assert overview["source"] == evidence.manifest.source.model_dump(mode="json")
    assert match["status"] == "unavailable"
    assert match["items"] == []
    assert match["coverage"]["projection_status"] == "projection-unavailable"

    core_only = tmp_path / "core-only.zip"
    with zipfile.ZipFile(source) as archive, zipfile.ZipFile(core_only, "w") as core:
        for member in ("manifest.json", "native.bin", "native-index.jsonl"):
            core.writestr(member, archive.read(member))
    rebuilt = execute_query(core_only, {"intent": "overview"})
    assert rebuilt["status"] == "complete"
    assert rebuilt["projection"]["result_status"] == "ready"
