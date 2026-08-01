from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import pytest

from svc_cli.analysis.protocol import (
    AnalysisProtocolError,
    decode_cursor,
    encode_cursor,
)
from svc_cli.analysis.read import read_schema
from svc_cli.analysis.service import execute_read
from tests.agent_thread_contract import write_evidence_bundle


def _payload_bytes(item: dict[str, object]) -> bytes:
    payload = item["payload"]
    assert isinstance(payload, dict)
    if payload["encoding"] == "utf-8":
        return str(payload["text"]).encode("utf-8")
    return base64.b64decode(str(payload["data"]))


def test_schema_and_cursor_pages_preserve_exact_utf8_and_binary_bytes(
    tmp_path: Path,
) -> None:
    frames = (b"alpha", b"a" * 250 + "你".encode(), b"\xff\x00", b"omega")
    bundle = write_evidence_bundle(tmp_path, "mixed", frames)
    schema = read_schema()
    request: dict[str, object] = {"max_items": 2, "max_bytes": 256}
    reconstructed = bytearray()
    encodings: set[object] = set()
    first_cursor: object = None

    while True:
        response = execute_read(bundle.path, request)
        assert response["status"] == "complete"
        assert response["method"] == schema["method"]
        for item in response["items"]:
            payload = item["payload"]
            fragment = _payload_bytes(item)
            encodings.add(payload["encoding"])
            assert hashlib.sha256(fragment).hexdigest() == payload["fragment_sha256"]
            assert (
                item["frame_sha256"]
                == hashlib.sha256(frames[item["native_index"]]).hexdigest()
            )
            assert payload["whole_record"] is (
                payload["fragment_starts_record"] and payload["fragment_ends_record"]
            )
            reconstructed.extend(fragment)
        cursor = response["next_cursor"]
        if first_cursor is None:
            first_cursor = cursor
        if cursor is None:
            break
        request = {"cursor": cursor, "max_items": 3, "max_bytes": 300}

    assert schema["format"] == "svc.analysis.read.schema/v1"
    assert schema["request"]["initial"]["additional_properties"] is False
    assert schema["request"]["continuation"]["required"] == ["cursor"]
    assert set(schema["response"]["payload_encoding"]) == {"utf-8", "base64"}
    assert schema["method_lookup"]["read_section"] == "Agent Task Analysis"
    assert first_cursor is not None
    cursor_payload = decode_cursor(first_cursor)
    assert set(cursor_payload) == {
        "version",
        "tool",
        "evidence_id",
        "scope",
        "next_ordinal",
        "next_offset",
    }
    assert cursor_payload["scope"] == {
        "anchor": None,
        "preceding": 0,
        "ordering": "native-forward",
    }
    assert encodings == {"utf-8", "base64"}
    assert bytes(reconstructed) == bundle.native


def test_exact_preceding_and_capture_status_bound_the_read(tmp_path: Path) -> None:
    frames = (b"alpha", b"context", b"omega")
    bundle = write_evidence_bundle(
        tmp_path,
        "partial",
        frames,
        incomplete_last=True,
    )
    response = execute_read(
        bundle.path,
        {
            "start": {
                "evidence_id": bundle.evidence_id,
                "record_kind": "native",
                "record_id": "n000002",
            },
            "preceding": 1,
            "max_items": 10,
            "max_bytes": 1024,
        },
    )
    assert [item["native_index"] for item in response["items"]] == [1, 2]
    assert response["status"] == "partial"
    assert response["coverage"]["unknown_remainder"] is True

    empty = write_evidence_bundle(tmp_path, "empty", ())
    unavailable = execute_read(empty.path, {})
    assert unavailable["status"] == "unavailable"
    assert unavailable["items"] == []
    assert unavailable["next_cursor"] is None


def test_cursor_and_reference_scope_errors_keep_the_request_union_closed(
    tmp_path: Path,
) -> None:
    bundle = write_evidence_bundle(tmp_path, "errors", (b"alpha", b"omega"))
    first = execute_read(bundle.path, {"max_items": 1, "max_bytes": 256})
    cursor_payload = decode_cursor(first["next_cursor"])
    other = write_evidence_bundle(tmp_path, "other", (b"different",))

    invalid_cases = (
        (other.path, {"cursor": first["next_cursor"]}, "cursor-scope-mismatch"),
        (bundle.path, {"cursor": "not-a-cursor"}, "invalid-cursor"),
        (bundle.path, {"cursor": "x", "start": {}}, "invalid-read-request"),
        (bundle.path, {"max_bytes": 1}, "invalid-read-request"),
        (bundle.path, {"max_items": True}, "invalid-read-request"),
        (
            bundle.path,
            {"cursor": encode_cursor({**cursor_payload, "next_offset": True})},
            "invalid-cursor",
        ),
        (
            bundle.path,
            {
                "start": {
                    "evidence_id": other.evidence_id,
                    "record_kind": "native",
                    "record_id": "n000000",
                }
            },
            "reference-scope-mismatch",
        ),
        (
            bundle.path,
            {
                "start": {
                    "evidence_id": bundle.evidence_id,
                    "record_kind": "trajectory",
                    "record_id": "r000000",
                }
            },
            "reference-kind-mismatch",
        ),
    )
    for source, request, expected_code in invalid_cases:
        with pytest.raises(AnalysisProtocolError) as raised:
            execute_read(source, request)
        assert raised.value.code == expected_code
