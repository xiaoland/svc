"""Typed structural navigation over validated Agent-thread evidence."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable, Mapping

from ..telemetry.evidence import NativeIndexEntry, ValidatedEvidence
from ..telemetry.trajectory import RECORD_TYPES, canonical_json_bytes
from .protocol import (
    ANALYSIS_CONTRACT_VERSION,
    AnalysisProtocolError,
    decode_cursor,
    encode_cursor,
    evidence_ref,
    method_reference,
    parse_ref,
    request_fingerprint,
)


QUERY_FORMAT = "svc.analysis.query/v1"
DEFAULT_MAX_ITEMS = 50
DEFAULT_MAX_BYTES = 65_536
MAX_ITEMS = 100
MIN_BYTES = 8_192
MAX_BYTES = 1_048_576
MAX_TERMS = 8
MAX_TERM_CODE_POINTS = 256
_STRUCTURAL_KEYS = {
    "record_types",
    "roles",
    "tool_names",
    "relationship",
}
_PREDICATE_KEYS = _STRUCTURAL_KEYS | {"native_range", "text"}
_RELATIONSHIP_FIELDS = {
    "turn_ref",
    "actor_ref",
    "parent_actor_ref",
    "lane_ref",
    "concurrency_group",
}


@dataclass(frozen=True, slots=True)
class MatchRequest:
    predicates: Mapping[str, Any]
    max_items: int
    max_bytes: int
    cursor: str | None = None


def _bounded_integer(
    value: Any,
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
            "invalid-query-request",
            f"{name} must be an integer.",
        )
    if not minimum <= value <= maximum:
        raise AnalysisProtocolError(
            "invalid-query-request",
            f"{name} must be between {minimum} and {maximum}.",
        )
    return value


def _string_list(
    value: Any,
    *,
    name: str,
    allowed: set[str] | None = None,
    maximum: int = MAX_TERMS,
) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or len(value) > maximum
        or any(not isinstance(item, str) for item in value)
    ):
        raise AnalysisProtocolError(
            "invalid-query-request",
            f"{name} must contain between 1 and {maximum} strings.",
        )
    items = [str(item) for item in value]
    if (
        len(set(items)) != len(items)
        or any(
            not item
            or len(item) > MAX_TERM_CODE_POINTS
            or (allowed is not None and item not in allowed)
            for item in items
        )
    ):
        raise AnalysisProtocolError(
            "invalid-query-request",
            f"{name} contains invalid or duplicate values.",
        )
    return items


def _normalize_predicates(
    value: Any,
    evidence: ValidatedEvidence,
) -> dict[str, Any]:
    if (
        not isinstance(value, Mapping)
        or not value
        or not set(value) <= _PREDICATE_KEYS
    ):
        raise AnalysisProtocolError(
            "invalid-query-request",
            "match predicates must be a non-empty closed object.",
        )
    result: dict[str, Any] = {}
    if "record_types" in value:
        result["record_types"] = _string_list(
            value["record_types"],
            name="record_types",
            allowed=set(RECORD_TYPES) - {"meta"},
        )
    if "roles" in value:
        result["roles"] = _string_list(
            value["roles"],
            name="roles",
            allowed={"user", "assistant"},
        )
    if "tool_names" in value:
        result["tool_names"] = _string_list(
            value["tool_names"],
            name="tool_names",
        )
    if "relationship" in value:
        relationship = value["relationship"]
        if (
            not isinstance(relationship, Mapping)
            or set(relationship) != {"field", "value"}
            or relationship["field"] not in _RELATIONSHIP_FIELDS
            or not isinstance(relationship["value"], str)
            or not relationship["value"]
        ):
            raise AnalysisProtocolError(
                "invalid-query-request",
                "relationship must contain one supported field and value.",
            )
        result["relationship"] = dict(relationship)
    if "native_range" in value:
        native_range = value["native_range"]
        if (
            not isinstance(native_range, Mapping)
            or not native_range
            or not set(native_range) <= {"start", "end"}
        ):
            raise AnalysisProtocolError(
                "invalid-query-request",
                "native_range accepts a start and/or end native reference.",
            )
        result["native_range"] = {
            key: parse_ref(
                native_range[key],
                evidence,
                expected_kind="native",
            ).as_dict()
            for key in ("start", "end")
            if key in native_range
        }
    if "text" in value:
        text = value["text"]
        if (
            not isinstance(text, Mapping)
            or not {"terms", "mode"} <= set(text)
            or not set(text) <= {"terms", "mode", "case_sensitive"}
            or text["mode"] not in {"any", "all"}
            or not isinstance(text.get("case_sensitive", False), bool)
        ):
            raise AnalysisProtocolError(
                "invalid-query-request",
                "text requires terms and any|all mode.",
            )
        result["text"] = {
            "terms": _string_list(text["terms"], name="text.terms"),
            "mode": text["mode"],
            "case_sensitive": text.get("case_sensitive", False),
        }
    return result


def parse_match_request(
    value: Any,
    evidence: ValidatedEvidence,
) -> MatchRequest:
    if not isinstance(value, Mapping) or value.get("intent") != "match":
        raise AnalysisProtocolError(
            "invalid-query-request",
            "match request must declare intent=match.",
        )
    if "cursor" in value:
        if not set(value) <= {"intent", "cursor", "max_items", "max_bytes"}:
            raise AnalysisProtocolError(
                "invalid-query-request",
                "match continuation accepts only intent, cursor, and page budgets.",
            )
        if not isinstance(value["cursor"], str):
            raise AnalysisProtocolError(
                "invalid-query-request",
                "cursor must be text.",
            )
        return MatchRequest(
            predicates={},
            cursor=value["cursor"],
            max_items=_bounded_integer(
                value.get("max_items"),
                name="max_items",
                default=DEFAULT_MAX_ITEMS,
                minimum=1,
                maximum=MAX_ITEMS,
            ),
            max_bytes=_bounded_integer(
                value.get("max_bytes"),
                name="max_bytes",
                default=DEFAULT_MAX_BYTES,
                minimum=MIN_BYTES,
                maximum=MAX_BYTES,
            ),
        )
    if set(value) - {"intent", "predicates", "max_items", "max_bytes"}:
        raise AnalysisProtocolError(
            "invalid-query-request",
            "match request contains unsupported fields.",
        )
    if "predicates" not in value:
        raise AnalysisProtocolError(
            "invalid-query-request",
            "match request requires predicates.",
        )
    return MatchRequest(
        predicates=_normalize_predicates(value["predicates"], evidence),
        max_items=_bounded_integer(
            value.get("max_items"),
            name="max_items",
            default=DEFAULT_MAX_ITEMS,
            minimum=1,
            maximum=MAX_ITEMS,
        ),
        max_bytes=_bounded_integer(
            value.get("max_bytes"),
            name="max_bytes",
            default=DEFAULT_MAX_BYTES,
            minimum=MIN_BYTES,
            maximum=MAX_BYTES,
        ),
    )


def _records_by_native(
    evidence: ValidatedEvidence,
) -> dict[str, list[Mapping[str, Any]]]:
    result: dict[str, list[Mapping[str, Any]]] = {}
    for record in evidence.trajectory.records:
        if record.get("type") == "meta":
            continue
        source_ref = record.get("source_ref")
        if isinstance(source_ref, Mapping):
            native_id = source_ref.get("native_record_id")
            if isinstance(native_id, str):
                result.setdefault(native_id, []).append(record)
    return result


def _native_bounds(
    evidence: ValidatedEvidence,
    predicates: Mapping[str, Any],
) -> tuple[int, int]:
    native_range = predicates.get("native_range")
    if not isinstance(native_range, Mapping):
        return 0, len(evidence.native_index) - 1
    by_id = {
        item.native_record_id: item.native_index
        for item in evidence.native_index
    }
    start = 0
    end = len(evidence.native_index) - 1
    if "start" in native_range:
        start_ref = native_range["start"]
        assert isinstance(start_ref, Mapping)
        record_id = str(start_ref["record_id"])
        if record_id not in by_id:
            raise AnalysisProtocolError(
                "reference-not-found",
                "native_range start does not resolve.",
            )
        start = by_id[record_id]
    if "end" in native_range:
        end_ref = native_range["end"]
        assert isinstance(end_ref, Mapping)
        record_id = str(end_ref["record_id"])
        if record_id not in by_id:
            raise AnalysisProtocolError(
                "reference-not-found",
                "native_range end does not resolve.",
            )
        end = by_id[record_id]
    if start > end:
        raise AnalysisProtocolError(
            "invalid-query-request",
            "native_range start follows its end.",
        )
    return start, end


def _structural_matches(
    records: Iterable[Mapping[str, Any]],
    predicates: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    matches: list[Mapping[str, Any]] = []
    for record in records:
        if "record_types" in predicates and record.get("type") not in predicates["record_types"]:
            continue
        if "roles" in predicates and record.get("role") not in predicates["roles"]:
            continue
        if "tool_names" in predicates and record.get("name") not in predicates["tool_names"]:
            continue
        relationship = predicates.get("relationship")
        if isinstance(relationship, Mapping) and record.get(
            str(relationship["field"])
        ) != relationship["value"]:
            continue
        matches.append(record)
    return matches


def _native_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for child in value.values():
            yield from _native_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _native_strings(child)


def _text_match(
    raw: bytes,
    predicate: Mapping[str, Any],
) -> tuple[bool, list[str], bool]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = item
        return result

    try:
        value = json.loads(
            raw.decode("utf-8").rstrip("\r\n"),
            object_pairs_hook=pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
        )
        strings = list(_native_strings(value))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        return False, [], False
    terms = predicate["terms"]
    assert isinstance(terms, list)
    case_sensitive = bool(predicate["case_sensitive"])
    haystacks = strings if case_sensitive else [item.casefold() for item in strings]
    matched = [
        term
        for term in terms
        if any(
            (term if case_sensitive else term.casefold()) in haystack
            for haystack in haystacks
        )
    ]
    passes = bool(matched) if predicate["mode"] == "any" else len(matched) == len(terms)
    return passes, matched, True


def _descriptor(
    evidence: ValidatedEvidence,
    entry: NativeIndexEntry,
    records: list[Mapping[str, Any]],
    matched_terms: list[str],
) -> tuple[dict[str, Any], bool]:
    retained = records[:8]
    record_types = sorted({str(item["type"]) for item in records})
    roles = sorted({str(item["role"]) for item in records if "role" in item})
    tool_names = sorted({str(item["name"]) for item in records if "name" in item})
    return (
        {
            "ref": evidence_ref(evidence, "native", entry.native_record_id),
            "native_index": entry.native_index,
            "frame_status": entry.frame_status,
            "source_coordinate": dict(entry.source_coordinate),
            "record_types": record_types,
            "roles": roles,
            "tool_names": tool_names,
            "trajectory_refs": [
                evidence_ref(evidence, "trajectory", str(item["record_id"]))
                for item in retained
            ],
            "matched_terms": matched_terms,
        },
        len(records) > len(retained),
    )


def overview(evidence: ValidatedEvidence) -> dict[str, Any]:
    projection = evidence.manifest["projection"]
    capture = evidence.manifest["capture"]
    assert isinstance(projection, Mapping) and isinstance(capture, Mapping)
    by_type: dict[str, list[Mapping[str, Any]]] = {}
    for record in evidence.trajectory.records:
        by_type.setdefault(str(record["type"]), []).append(record)
    ranges = []
    for record_type in RECORD_TYPES:
        records = by_type.get(record_type, [])
        if not records:
            continue
        ranges.append(
            {
                "record_type": record_type,
                "count": len(records),
                "first_ref": evidence_ref(
                    evidence,
                    "trajectory",
                    str(records[0]["record_id"]),
                ),
                "last_ref": evidence_ref(
                    evidence,
                    "trajectory",
                    str(records[-1]["record_id"]),
                ),
            }
        )
    if not evidence.native_index:
        status = "unavailable"
    elif capture["status"] == "partial" or projection["result_status"] == "partial":
        status = "partial"
    else:
        status = "complete"
    native_first = (
        evidence_ref(evidence, "native", evidence.native_index[0].native_record_id)
        if evidence.native_index
        else None
    )
    native_last = (
        evidence_ref(evidence, "native", evidence.native_index[-1].native_record_id)
        if evidence.native_index
        else None
    )
    return {
        "format": QUERY_FORMAT,
        "schema_version": ANALYSIS_CONTRACT_VERSION,
        "intent": "overview",
        "status": status,
        "evidence_id": evidence.evidence_id,
        "method": method_reference(),
        "source": projection["source"],
        "capture": dict(capture),
        "projection": {
            "result_status": projection["result_status"],
            "capabilities": projection["capabilities"],
            "lossiness": projection["lossiness"],
        },
        "ordering": "native-forward",
        "native_range": {
            "records": len(evidence.native_index),
            "first_ref": native_first,
            "last_ref": native_last,
        },
        "structural_ranges": ranges,
        "available_match_fields": [
            "record_types",
            "roles",
            "tool_names",
            "native_range",
            "relationship",
            "text",
        ],
        "next_cursor": None,
    }


def match(
    evidence: ValidatedEvidence,
    request_value: Any,
) -> dict[str, Any]:
    request = parse_match_request(request_value, evidence)
    if request.cursor is not None:
        cursor = decode_cursor(request.cursor, tool="query-match")
        required = {
            "version",
            "tool",
            "evidence_id",
            "scope",
            "predicates",
            "next_ordinal",
        }
        if set(cursor) != required or cursor["evidence_id"] != evidence.evidence_id:
            raise AnalysisProtocolError(
                "cursor-scope-mismatch",
                "Match cursor belongs to a different request or evidence.",
            )
        predicates = _normalize_predicates(cursor["predicates"], evidence)
        if cursor["scope"] != request_fingerprint(predicates):
            raise AnalysisProtocolError(
                "cursor-scope-mismatch",
                "Match cursor predicate binding is invalid.",
            )
        next_ordinal = cursor["next_ordinal"]
        if isinstance(next_ordinal, bool) or not isinstance(next_ordinal, int):
            raise AnalysisProtocolError("invalid-cursor", "Match cursor position is invalid.")
    else:
        predicates = dict(request.predicates)
        next_ordinal = _native_bounds(evidence, predicates)[0]
    start, end = _native_bounds(evidence, predicates)
    if not start <= next_ordinal <= end + 1:
        raise AnalysisProtocolError("invalid-cursor", "Match cursor position is outside its range.")
    by_native = _records_by_native(evidence)
    structural = bool(set(predicates) & _STRUCTURAL_KEYS)
    text_predicate = predicates.get("text")
    items: list[dict[str, Any]] = []
    output_bytes = 0
    coverage_partial = False
    descriptor_truncated = False
    ordinal = next_ordinal
    while ordinal <= end:
        entry = evidence.native_index[ordinal]
        records = by_native.get(entry.native_record_id, [])
        structural_records = (
            _structural_matches(records, predicates)
            if structural
            else records
        )
        passes = bool(structural_records) if structural else True
        matched_terms: list[str] = []
        if isinstance(text_predicate, Mapping):
            raw = evidence.native[entry.byte_start : entry.byte_end]
            text_passes, matched_terms, covered = _text_match(raw, text_predicate)
            coverage_partial |= not covered or entry.frame_status != "complete"
            passes = passes and text_passes and entry.frame_status == "complete"
        if passes:
            descriptor, truncated = _descriptor(
                evidence,
                entry,
                structural_records,
                matched_terms,
            )
            encoded_size = len(canonical_json_bytes(descriptor))
            if items and (
                len(items) >= request.max_items
                or output_bytes + encoded_size > request.max_bytes
            ):
                break
            if not items and encoded_size > request.max_bytes:
                raise AnalysisProtocolError(
                    "query-page-budget-too-small",
                    "max_bytes cannot hold one bounded match descriptor.",
                )
            items.append(descriptor)
            output_bytes += encoded_size
            descriptor_truncated |= truncated
            if len(items) >= request.max_items:
                ordinal += 1
                break
        ordinal += 1

    more = ordinal <= end
    next_cursor = None
    if more:
        next_cursor = encode_cursor(
            {
                "version": ANALYSIS_CONTRACT_VERSION,
                "tool": "query-match",
                "evidence_id": evidence.evidence_id,
                "scope": request_fingerprint(predicates),
                "predicates": predicates,
                "next_ordinal": ordinal,
            }
        )
    projection = evidence.manifest["projection"]
    capture = evidence.manifest["capture"]
    assert isinstance(projection, Mapping) and isinstance(capture, Mapping)
    projection_partial = structural and projection["result_status"] == "partial"
    capture_partial = capture["status"] == "partial"
    coverage_partial |= projection_partial or capture_partial or descriptor_truncated
    unavailable = False
    capabilities = projection["capabilities"]
    if isinstance(capabilities, Mapping):
        requested_types = predicates.get("record_types")
        if isinstance(requested_types, list) and requested_types == ["reasoning"] and capabilities.get("reasoning") in {"absent", "opaque"}:
            unavailable = True
    status = "unavailable" if unavailable else "partial" if coverage_partial else "complete"
    return {
        "format": QUERY_FORMAT,
        "schema_version": ANALYSIS_CONTRACT_VERSION,
        "intent": "match",
        "status": status,
        "evidence_id": evidence.evidence_id,
        "method": method_reference(),
        "ordering": "native-forward",
        "items": items,
        "next_cursor": next_cursor,
        "coverage": {
            "capture_status": capture["status"],
            "projection_status": projection["result_status"],
            "text_native_values": (
                "partial" if isinstance(text_predicate, Mapping) and coverage_partial else "complete"
                if isinstance(text_predicate, Mapping)
                else "not-requested"
            ),
            "descriptor_truncated": descriptor_truncated,
            "returned_items": len(items),
            "descriptor_bytes": output_bytes,
        },
    }


def query_evidence(
    evidence: ValidatedEvidence,
    request_value: Any,
) -> dict[str, Any]:
    if not isinstance(request_value, Mapping):
        raise AnalysisProtocolError(
            "invalid-query-request",
            "Query request must be a JSON object.",
        )
    intent = request_value.get("intent")
    if intent == "overview":
        if set(request_value) != {"intent"}:
            raise AnalysisProtocolError(
                "invalid-query-request",
                "overview accepts no additional fields.",
            )
        return overview(evidence)
    if intent == "match":
        return match(evidence, request_value)
    raise AnalysisProtocolError(
        "invalid-query-request",
        "Query intent must be overview or match.",
    )


def query_schema() -> dict[str, Any]:
    native_ref_shape = {
        "required": ["evidence_id", "record_kind", "record_id"],
        "record_kind": "native",
        "record_id_pattern": "n[0-9]{6}",
        "additional_properties": False,
    }
    return {
        "format": "svc.analysis.query.schema/v1",
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
        "composition": [
            "overview",
            "match to obtain native refs",
            "read contiguous native context before concluding",
        ],
        "intents": {
            "overview": {
                "request": {"intent": "overview"},
                "additional_properties": False,
            },
            "match": {
                "initial": {
                    "required": ["intent", "predicates"],
                    "optional": ["max_items", "max_bytes"],
                    "additional_properties": False,
                },
                "continuation": {
                    "required": ["intent", "cursor"],
                    "optional": ["max_items", "max_bytes"],
                    "note": "Reuse next_cursor; predicates are already bound and must be omitted.",
                    "additional_properties": False,
                },
                "predicates": {
                    "combination": "intersection across supplied predicates",
                    "record_types": {
                        "type": "non-empty unique string array",
                        "values": list(RECORD_TYPES[1:]),
                    },
                    "roles": {
                        "type": "non-empty unique string array",
                        "values": ["user", "assistant"],
                    },
                    "tool_names": {
                        "type": "non-empty unique string array",
                        "matching": "exact",
                    },
                    "relationship": {
                        "shape": {"field": "<relationship field>", "value": "<exact ref>"},
                        "fields": sorted(_RELATIONSHIP_FIELDS),
                    },
                    "native_range": {
                        "shape": {"start": "<native ref>", "end": "<native ref>"},
                        "minimum_fields": 1,
                        "semantics": "inclusive native-order endpoints",
                        "reference": native_ref_shape,
                    },
                    "text": {
                        "shape": {
                            "terms": ["<literal>"],
                            "mode": "any | all",
                            "case_sensitive": False,
                        },
                        "bounds": {
                            "terms": [1, MAX_TERMS],
                            "term_code_points": [1, MAX_TERM_CODE_POINTS],
                        },
                        "matching": "literal substrings in provider-native JSON string values",
                    },
                },
                "bounds": {
                    "max_items": [1, MAX_ITEMS],
                    "max_bytes": [MIN_BYTES, MAX_BYTES],
                },
            },
        },
        "status": {
            "complete": "The exact requested evidence range is answerable; an empty result is a trustworthy negative.",
            "partial": "Useful results exist but capture or projection loss limits the conclusion.",
            "unavailable": "The evidence lacks the requested capability; this is not a negative finding.",
        },
        "response_format": QUERY_FORMAT,
    }


__all__ = [
    "QUERY_FORMAT",
    "MatchRequest",
    "match",
    "overview",
    "parse_match_request",
    "query_evidence",
    "query_schema",
]
