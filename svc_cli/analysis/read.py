"""Forward-only, exactly reassemblable reading of native evidence frames."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
from typing import Mapping

from ..telemetry.evidence import NativeIndexEntry, ValidatedEvidence
from .protocol import (
    ANALYSIS_CONTRACT_VERSION,
    AnalysisProtocolError,
    EvidenceRef,
    decode_cursor,
    encode_cursor,
    evidence_ref,
    method_reference,
    parse_ref,
    request_fingerprint,
)


READ_FORMAT = "svc.analysis.read/v1"
DEFAULT_MAX_ITEMS = 20
DEFAULT_MAX_BYTES = 65_536
MAX_ITEMS = 100
MAX_BYTES = 1_048_576
MIN_BYTES = 256
MAX_PRECEDING = 20


@dataclass(frozen=True, slots=True)
class ReadRequest:
    anchor: EvidenceRef | None
    preceding: int
    max_items: int
    max_bytes: int
    cursor: str | None = None


def _integer(
    value: object,
    *,
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise AnalysisProtocolError(
            "invalid-read-request",
            f"{name} must be an integer.",
        )
    if not minimum <= value <= maximum:
        raise AnalysisProtocolError(
            "invalid-read-request",
            f"{name} must be between {minimum} and {maximum}.",
        )
    return value


def parse_read_request(
    value: object,
    evidence: ValidatedEvidence,
) -> ReadRequest:
    if not isinstance(value, Mapping):
        raise AnalysisProtocolError(
            "invalid-read-request",
            "Read request must be a JSON object.",
        )
    keys = set(value)
    if "cursor" in value:
        if not keys <= {"cursor", "max_items", "max_bytes"}:
            raise AnalysisProtocolError(
                "invalid-read-request",
                "Cursor continuation accepts only cursor and page budgets.",
            )
        if not isinstance(value["cursor"], str):
            raise AnalysisProtocolError(
                "invalid-read-request",
                "cursor must be text.",
            )
        return ReadRequest(
            anchor=None,
            preceding=0,
            max_items=_integer(
                value.get("max_items"),
                name="max_items",
                default=DEFAULT_MAX_ITEMS,
                minimum=1,
                maximum=MAX_ITEMS,
            ),
            max_bytes=_integer(
                value.get("max_bytes"),
                name="max_bytes",
                default=DEFAULT_MAX_BYTES,
                minimum=MIN_BYTES,
                maximum=MAX_BYTES,
            ),
            cursor=value["cursor"],
        )
    if not keys <= {"start", "preceding", "max_items", "max_bytes"}:
        raise AnalysisProtocolError(
            "invalid-read-request",
            "Read request contains unsupported fields.",
        )
    anchor = (
        parse_ref(value["start"], evidence, expected_kind="native")
        if "start" in value
        else None
    )
    preceding = _integer(
        value.get("preceding"),
        name="preceding",
        default=0,
        minimum=0,
        maximum=MAX_PRECEDING,
    )
    if anchor is None and preceding:
        raise AnalysisProtocolError(
            "invalid-read-request",
            "preceding requires an exact start reference.",
        )
    return ReadRequest(
        anchor=anchor,
        preceding=preceding,
        max_items=_integer(
            value.get("max_items"),
            name="max_items",
            default=DEFAULT_MAX_ITEMS,
            minimum=1,
            maximum=MAX_ITEMS,
        ),
        max_bytes=_integer(
            value.get("max_bytes"),
            name="max_bytes",
            default=DEFAULT_MAX_BYTES,
            minimum=MIN_BYTES,
            maximum=MAX_BYTES,
        ),
    )


def _scope(anchor: Mapping[str, object] | None, preceding: int) -> str:
    return request_fingerprint(
        {
            "tool": "read",
            "ordering": "native-forward",
            "anchor": dict(anchor) if anchor is not None else None,
            "preceding": preceding,
        }
    )


def _initial_position(
    evidence: ValidatedEvidence,
    request: ReadRequest,
) -> tuple[int, int, Mapping[str, object] | None, int, str]:
    if request.cursor is not None:
        payload = decode_cursor(request.cursor, tool="read")
        required = {
            "version",
            "tool",
            "evidence_id",
            "scope",
            "anchor",
            "preceding",
            "next_ordinal",
            "next_offset",
        }
        if set(payload) != required:
            raise AnalysisProtocolError(
                "invalid-cursor",
                "Read cursor payload has an invalid shape.",
            )
        if payload["evidence_id"] != evidence.evidence_id:
            raise AnalysisProtocolError(
                "cursor-scope-mismatch",
                "Read cursor belongs to different evidence.",
            )
        anchor = payload["anchor"]
        preceding = payload["preceding"]
        if anchor is not None and not isinstance(anchor, Mapping):
            raise AnalysisProtocolError(
                "invalid-cursor",
                "Read cursor anchor has an invalid shape.",
            )
        if (
            isinstance(preceding, bool)
            or not isinstance(preceding, int)
            or not 0 <= preceding <= MAX_PRECEDING
            or payload["scope"] != _scope(anchor, preceding)
        ):
            raise AnalysisProtocolError(
                "cursor-scope-mismatch",
                "Read cursor request binding is invalid.",
            )
        ordinal = payload["next_ordinal"]
        offset = payload["next_offset"]
        if (
            isinstance(ordinal, bool)
            or not isinstance(ordinal, int)
            or isinstance(offset, bool)
            or not isinstance(offset, int)
            or ordinal < 0
            or offset < 0
        ):
            raise AnalysisProtocolError(
                "invalid-cursor",
                "Read cursor position is invalid.",
            )
        return ordinal, offset, anchor, preceding, str(payload["scope"])

    anchor_value = request.anchor.as_dict() if request.anchor else None
    if request.anchor is None:
        ordinal = 0
    else:
        by_id = {
            entry.native_record_id: entry.native_index
            for entry in evidence.native_index
        }
        if request.anchor.record_id not in by_id:
            raise AnalysisProtocolError(
                "reference-not-found",
                "Native start reference does not resolve in this evidence.",
            )
        ordinal = max(
            0,
            by_id[request.anchor.record_id] - request.preceding,
        )
    return (
        ordinal,
        0,
        anchor_value,
        request.preceding,
        _scope(anchor_value, request.preceding),
    )


def _fragment_item(
    evidence: ValidatedEvidence,
    entry: NativeIndexEntry,
    start: int,
    end: int,
) -> dict[str, object]:
    frame_size = entry.byte_end - entry.byte_start
    fragment = evidence.native[
        entry.byte_start + start : entry.byte_start + end
    ]
    payload: dict[str, object] = {
        "fragment_start": start,
        "fragment_end": end,
        "fragment_sha256": hashlib.sha256(fragment).hexdigest(),
        "fragment_starts_record": start == 0,
        "fragment_ends_record": end == frame_size,
        "whole_record": start == 0 and end == frame_size,
    }
    try:
        payload.update(
            {
                "encoding": "utf-8",
                "text": fragment.decode("utf-8"),
            }
        )
    except UnicodeDecodeError:
        payload.update(
            {
                "encoding": "base64",
                "data": base64.b64encode(fragment).decode("ascii"),
            }
        )
    return {
        "ref": evidence_ref(
            evidence,
            "native",
            entry.native_record_id,
        ),
        "native_index": entry.native_index,
        "byte_start": entry.byte_start,
        "byte_end": entry.byte_end,
        "representation": entry.representation,
        "frame_status": entry.frame_status,
        "source_coordinate": dict(entry.source_coordinate),
        "frame_sha256": entry.sha256,
        "payload": payload,
    }


def read_evidence(
    evidence: ValidatedEvidence,
    request_value: object,
) -> dict[str, object]:
    """Read one bounded page in canonical native order."""

    request = parse_read_request(request_value, evidence)
    ordinal, offset, anchor, preceding, scope = _initial_position(
        evidence,
        request,
    )
    if ordinal > len(evidence.native_index):
        raise AnalysisProtocolError(
            "invalid-cursor",
            "Read cursor ordinal is outside the evidence index.",
        )
    if ordinal < len(evidence.native_index):
        size = (
            evidence.native_index[ordinal].byte_end
            - evidence.native_index[ordinal].byte_start
        )
        if offset >= size:
            raise AnalysisProtocolError(
                "invalid-cursor",
                "Read cursor fragment offset is outside its native frame.",
            )
    elif offset:
        raise AnalysisProtocolError(
            "invalid-cursor",
            "Read cursor cannot carry an offset at end of evidence.",
        )

    items: list[dict[str, object]] = []
    remaining_bytes = request.max_bytes
    page_bytes = 0
    current_ordinal = ordinal
    current_offset = offset
    while (
        current_ordinal < len(evidence.native_index)
        and len(items) < request.max_items
        and remaining_bytes > 0
    ):
        entry = evidence.native_index[current_ordinal]
        frame_size = entry.byte_end - entry.byte_start
        end = min(frame_size, current_offset + remaining_bytes)
        items.append(
            _fragment_item(
                evidence,
                entry,
                current_offset,
                end,
            )
        )
        consumed = end - current_offset
        page_bytes += consumed
        remaining_bytes -= consumed
        if end == frame_size:
            current_ordinal += 1
            current_offset = 0
        else:
            current_offset = end

    more = current_ordinal < len(evidence.native_index)
    next_cursor = None
    if more:
        next_cursor = encode_cursor(
            {
                "version": ANALYSIS_CONTRACT_VERSION,
                "tool": "read",
                "evidence_id": evidence.evidence_id,
                "scope": scope,
                "anchor": dict(anchor) if anchor is not None else None,
                "preceding": preceding,
                "next_ordinal": current_ordinal,
                "next_offset": current_offset,
            }
        )
    capture = evidence.manifest["capture"]
    assert isinstance(capture, Mapping)
    if not evidence.native_index:
        status = "unavailable"
    else:
        status = "partial" if capture["status"] == "partial" else "complete"
    return {
        "format": READ_FORMAT,
        "schema_version": ANALYSIS_CONTRACT_VERSION,
        "status": status,
        "evidence_id": evidence.evidence_id,
        "method": method_reference(),
        "ordering": "native-forward",
        "items": items,
        "next_cursor": next_cursor,
        "coverage": {
            "capture_status": capture["status"],
            "unknown_remainder": capture["unknown_remainder"],
            "page_start_ordinal": ordinal,
            "page_start_offset": offset,
            "returned_items": len(items),
            "returned_bytes": page_bytes,
        },
    }


def read_schema() -> dict[str, object]:
    """Return compact discovery data; execution remains stricter than JSON Schema."""

    native_ref_shape = {
        "required": ["evidence_id", "record_kind", "record_id"],
        "record_kind": "native",
        "record_id_pattern": "n[0-9]{6}",
        "additional_properties": False,
    }
    return {
        "format": "svc.analysis.read.schema/v1",
        "schema_version": ANALYSIS_CONTRACT_VERSION,
        "method": method_reference(),
        "method_lookup": {
            "command": [
                "svc",
                "lookup",
                "--name",
                "^sections/working-protocol\\.md$",
                "--json",
            ],
            "read_section": "Agent Task Analysis",
        },
        "purpose": "Read contiguous provider-native evidence in forward order; never use an isolated match as a conclusion.",
        "request": {
            "initial": {
                "optional": ["start", "preceding", "max_items", "max_bytes"],
                "start": native_ref_shape,
                "note": "Omit start to begin at the first native record; preceding requires start.",
                "additional_properties": False,
            },
            "continuation": {
                "required": ["cursor"],
                "optional": ["max_items", "max_bytes"],
                "note": "Reuse next_cursor; the anchor and preceding count are already bound and must be omitted.",
                "additional_properties": False,
            },
            "bounds": {
                "preceding": [0, MAX_PRECEDING],
                "max_items": [1, MAX_ITEMS],
                "max_bytes": [MIN_BYTES, MAX_BYTES],
            },
        },
        "response": {
            "ordering": "native-forward",
            "payload_encoding": {
                "utf-8": "preferred exact text when the fragment decodes losslessly",
                "base64": "exact fallback for arbitrary bytes",
            },
            "fragment_offsets": "relative to the native frame; concatenate fragments by cursor order",
            "fragment_flags": {
                "fragment_starts_record": "this fragment begins at byte zero",
                "fragment_ends_record": "this fragment reaches the frame end",
                "whole_record": "this one fragment contains the entire frame",
            },
            "integrity": ["frame_sha256", "fragment_sha256"],
            "pagination": "next_cursor means more output, not partial evidence",
        },
        "status": {
            "complete": "The captured native range is complete.",
            "partial": "Captured bytes are readable but the source has a declared gap or incomplete final frame.",
            "unavailable": "No native records were captured.",
        },
        "response_format": READ_FORMAT,
    }


__all__ = [
    "READ_FORMAT",
    "ReadRequest",
    "parse_read_request",
    "read_evidence",
    "read_schema",
]
