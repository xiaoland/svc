from __future__ import annotations

import base64
import hashlib

import pytest

from svc_cli.analysis.protocol import AnalysisProtocolError
from svc_cli.analysis.read import read_evidence, read_schema
from svc_cli.telemetry.evidence import NativeIndexEntry, ValidatedEvidence
from svc_cli.telemetry.trajectory import ValidatedTrajectory


def evidence(
    *,
    partial: bool = False,
    empty: bool = False,
    frames_override: tuple[bytes, ...] | None = None,
) -> ValidatedEvidence:
    frames = frames_override if frames_override is not None else () if empty else (b"alpha", b"b" * 700, b"omega")
    native = b"".join(frames)
    entries: list[NativeIndexEntry] = []
    offset = 0
    for ordinal, frame in enumerate(frames):
        entries.append(
            NativeIndexEntry(
                native_record_id=f"n{ordinal:06d}",
                native_index=ordinal,
                byte_start=offset,
                byte_end=offset + len(frame),
                sha256=hashlib.sha256(frame).hexdigest(),
                representation="provider-bytes",
                frame_status=("incomplete" if partial and ordinal == len(frames) - 1 else "complete"),
                source_coordinate={
                    "event_index": ordinal,
                    "line": ordinal,
                    "byte_offset": offset,
                },
            )
        )
        offset += len(frame)
    return ValidatedEvidence(
        manifest={
            "capture": {
                "status": "partial" if partial else "complete",
                "unknown_remainder": partial,
                "representation": "provider-bytes",
            }
        },
        native=native,
        native_index=tuple(entries),
        trajectory=ValidatedTrajectory((), b"", hashlib.sha256(b"").hexdigest()),
        evidence_id="e" * 64,
    )


def payload_bytes(item: dict[str, object]) -> bytes:
    payload = item["payload"]
    assert isinstance(payload, dict)
    if payload["encoding"] == "utf-8":
        return str(payload["text"]).encode("utf-8")
    return base64.b64decode(str(payload["data"]))


def test_read_schema_explains_ref_continuation_and_fragment_fidelity() -> None:
    schema = read_schema()
    assert schema["format"] == "svc.analysis.read.schema/v1"
    assert schema["request"]["initial"]["start"]["record_kind"] == "native"
    assert schema["request"]["initial"]["additional_properties"] is False
    assert schema["request"]["continuation"]["required"] == ["cursor"]
    assert schema["request"]["continuation"]["additional_properties"] is False
    assert set(schema["response"]["payload_encoding"]) == {"utf-8", "base64"}
    assert schema["response"]["integrity"] == ["frame_sha256", "fragment_sha256"]
    assert schema["response_format"] == "svc.analysis.read/v1"
    assert schema["method_lookup"]["read_section"] == "Agent Task Analysis"


def test_pages_reassemble_native_exactly_with_budget_changes() -> None:
    source = evidence()
    request: dict[str, object] = {"max_items": 1, "max_bytes": 256}
    reconstructed = bytearray()
    seen_positions: list[tuple[int, int, int]] = []
    while True:
        response = read_evidence(source, request)
        assert response["status"] == "complete"
        for item in response["items"]:
            assert isinstance(item, dict)
            payload = item["payload"]
            assert isinstance(payload, dict)
            assert payload["encoding"] == "utf-8"
            assert payload["whole_record"] is (payload["fragment_starts_record"] and payload["fragment_ends_record"])
            assert item["representation"] == "provider-bytes"
            fragment = payload_bytes(item)
            assert hashlib.sha256(fragment).hexdigest() == payload["fragment_sha256"]
            seen_positions.append(
                (
                    int(item["native_index"]),
                    int(payload["fragment_start"]),
                    int(payload["fragment_end"]),
                )
            )
            reconstructed.extend(fragment)
        cursor = response["next_cursor"]
        if cursor is None:
            break
        request = {
            "cursor": cursor,
            "max_items": 2,
            "max_bytes": 300,
        }

    assert bytes(reconstructed) == source.native
    assert seen_positions == [
        (0, 0, 5),
        (1, 0, 300),
        (1, 300, 600),
        (1, 600, 700),
        (2, 0, 5),
    ]


def test_binary_fragment_uses_exact_base64_fallback() -> None:
    response = read_evidence(
        evidence(frames_override=(b"\xff\x00",)),
        {"max_items": 1, "max_bytes": 256},
    )
    item = response["items"][0]
    assert item["payload"]["encoding"] == "base64"
    assert payload_bytes(item) == b"\xff\x00"


def test_utf8_boundary_fragments_mix_encodings_and_reassemble_exactly() -> None:
    frames = (b"start", b"a" * 250 + "你".encode())
    source = evidence(frames_override=frames)
    request: dict[str, object] = {"max_items": 2, "max_bytes": 256}
    reconstructed = bytearray()
    encodings: list[object] = []
    while True:
        response = read_evidence(source, request)
        for item in response["items"]:
            encodings.append(item["payload"]["encoding"])
            reconstructed.extend(payload_bytes(item))
        cursor = response["next_cursor"]
        if cursor is None:
            break
        request = {"cursor": cursor, "max_items": 2, "max_bytes": 256}

    assert encodings == ["utf-8", "base64", "base64"]
    assert bytes(reconstructed) == b"".join(frames)

    final_payload = response["items"][-1]["payload"]
    assert final_payload["fragment_starts_record"] is False
    assert final_payload["fragment_ends_record"] is True
    assert final_payload["whole_record"] is False


def test_exact_start_with_preceding_uses_native_order() -> None:
    source = evidence()
    response = read_evidence(
        source,
        {
            "start": {
                "evidence_id": source.evidence_id,
                "record_kind": "native",
                "record_id": "n000002",
            },
            "preceding": 1,
            "max_items": 10,
            "max_bytes": 1024,
        },
    )
    assert [item["native_index"] for item in response["items"]] == [1, 2]


def test_malformed_cursor_and_reference_scope_are_stable_errors() -> None:
    source = evidence()
    with pytest.raises(AnalysisProtocolError) as malformed:
        read_evidence(source, {"cursor": "not-a-cursor"})
    assert malformed.value.code == "invalid-cursor"

    with pytest.raises(AnalysisProtocolError) as wrong_evidence:
        read_evidence(
            source,
            {
                "start": {
                    "evidence_id": "f" * 64,
                    "record_kind": "native",
                    "record_id": "n000000",
                }
            },
        )
    assert wrong_evidence.value.code == "reference-scope-mismatch"

    with pytest.raises(AnalysisProtocolError) as wrong_kind:
        read_evidence(
            source,
            {
                "start": {
                    "evidence_id": source.evidence_id,
                    "record_kind": "trajectory",
                    "record_id": "r000000",
                }
            },
        )
    assert wrong_kind.value.code == "reference-kind-mismatch"

    with pytest.raises(AnalysisProtocolError) as non_string:
        read_evidence(
            source,
            {
                "start": {
                    "evidence_id": source.evidence_id,
                    "record_kind": "native",
                    "record_id": 0,
                }
            },
        )
    assert non_string.value.code == "invalid-reference"


def test_capture_partial_is_independent_from_pagination_and_empty_unavailable() -> None:
    partial_source = evidence(partial=True)
    partial = read_evidence(partial_source, {"max_items": 1})
    assert partial["status"] == "partial"
    assert partial["next_cursor"] is not None
    assert partial["coverage"]["unknown_remainder"] is True

    unavailable = read_evidence(evidence(empty=True), {})
    assert unavailable["status"] == "unavailable"
    assert unavailable["items"] == []
    assert unavailable["next_cursor"] is None


def test_request_union_is_closed_and_budget_cannot_empty_loop() -> None:
    source = evidence()
    with pytest.raises(AnalysisProtocolError) as mixed:
        read_evidence(source, {"cursor": "x", "start": {}})
    assert mixed.value.code == "invalid-read-request"

    with pytest.raises(AnalysisProtocolError) as tiny:
        read_evidence(source, {"max_bytes": 1})
    assert tiny.value.code == "invalid-read-request"
