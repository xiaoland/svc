"""Exact and forward material reading for evidence v4."""

from __future__ import annotations

import base64
import hashlib
from typing import Any

from ..telemetry.evidence_v4 import ValidatedEvidenceV4
from ..telemetry.trajectory_v2 import canonical_json_bytes
from .models_v3 import (
    ContinueReadRequestV3,
    ExactReadRequestV3,
    READ_REQUEST_V3,
    ReadRequestV3,
)
from .protocol import AnalysisProtocolError, decode_cursor, encode_cursor


def _require_ref(
    evidence: ValidatedEvidenceV4, evidence_id: str, kind: str, record_id: str
) -> None:
    if evidence_id != evidence.evidence_id:
        raise AnalysisProtocolError(
            "reference-scope-mismatch", "Reference belongs to different evidence."
        )
    if kind in {"content", "blob"}:
        allowed = {"blob"}
    else:
        allowed = {"native"}
    descriptor = next(
        (item for item in evidence.manifest.materials if item.name == record_id), None
    )
    if descriptor is None:
        raise AnalysisProtocolError(
            "reference-not-found", "Read reference does not resolve."
        )
    if descriptor.kind not in allowed:
        raise AnalysisProtocolError(
            "reference-kind-mismatch", "Read reference kind disagrees with material."
        )


def _scope(
    evidence: ValidatedEvidenceV4, request: ReadRequestV3
) -> tuple[tuple[str, ...], int, int, str]:
    if isinstance(request, ContinueReadRequestV3):
        cursor = decode_cursor(request.cursor)
        if cursor.get("version") != 3 or cursor.get("tool") != "read":
            raise AnalysisProtocolError(
                "cursor-version-mismatch",
                "Read cursor requires a fresh original request.",
            )
        if cursor.get("evidence_id") != evidence.evidence_id:
            raise AnalysisProtocolError(
                "cursor-scope-mismatch", "Read cursor belongs to different evidence."
            )
        names = cursor.get("materials")
        index = cursor.get("index")
        offset = cursor.get("offset")
        ordering = cursor.get("ordering")
        if (
            not isinstance(names, list)
            or not all(isinstance(item, str) for item in names)
            or type(index) is not int
            or type(offset) is not int
            or index < 0
            or offset < 0
            or ordering not in {"exact", "native-forward"}
        ):
            raise AnalysisProtocolError(
                "invalid-cursor", "Read cursor has an invalid shape."
            )
        material_names = tuple(names)
        if any(name not in evidence.materials for name in material_names):
            raise AnalysisProtocolError(
                "cursor-scope-mismatch", "Read cursor materials no longer resolve."
            )
        return material_names, index, offset, ordering

    reference = (
        request.ref if isinstance(request, ExactReadRequestV3) else request.start
    )
    _require_ref(evidence, reference.evidence_id, reference.kind, reference.id)
    if isinstance(request, ExactReadRequestV3):
        return (reference.id,), 0, 0, "exact"
    native = tuple(
        item.name for item in evidence.manifest.materials if item.kind == "native"
    )
    try:
        start = native.index(reference.id)
    except ValueError as error:
        raise AnalysisProtocolError(
            "reference-not-found", "Native start ref does not resolve."
        ) from error
    return native[start:], 0, 0, "native-forward"


def _fragment(
    evidence: ValidatedEvidenceV4,
    name: str,
    value: bytes,
    start: int,
    end: int,
) -> dict[str, Any]:
    fragment = value[start:end]
    payload: dict[str, Any]
    try:
        payload = {"encoding": "utf-8", "text": fragment.decode("utf-8")}
    except UnicodeDecodeError:
        payload = {
            "encoding": "base64",
            "data": base64.b64encode(fragment).decode("ascii"),
        }
    return {
        "ref": {
            "evidence_id": evidence.evidence_id,
            "kind": next(
                item.kind for item in evidence.manifest.materials if item.name == name
            ),
            "id": name,
        },
        "fragment_start": start,
        "fragment_end": end,
        "fragment_sha256": hashlib.sha256(fragment).hexdigest(),
        "material_sha256": hashlib.sha256(value).hexdigest(),
        "starts_material": start == 0,
        "ends_material": end == len(value),
        "payload": payload,
    }


def _cursor(
    evidence_id: str, names: tuple[str, ...], index: int, offset: int, ordering: str
) -> str:
    return encode_cursor(
        {
            "version": 3,
            "tool": "read",
            "evidence_id": evidence_id,
            "materials": names,
            "index": index,
            "offset": offset,
            "ordering": ordering,
        }
    )


def _response(
    evidence: ValidatedEvidenceV4,
    items: list[dict[str, Any]],
    names: tuple[str, ...],
    index: int,
    offset: int,
    ordering: str,
) -> dict[str, Any]:
    next_cursor = (
        None
        if index >= len(names)
        else _cursor(evidence.evidence_id, names, index, offset, ordering)
    )
    return {
        "format": "svc.analysis.read/v3",
        "version": 3,
        "evidence_id": evidence.evidence_id,
        "status": "complete",
        "ordering": ordering,
        "items": items,
        "next_cursor": next_cursor,
    }


def read_evidence_v3(
    evidence: ValidatedEvidenceV4, request_value: object
) -> dict[str, Any]:
    try:
        request = READ_REQUEST_V3.validate_python(request_value)
    except Exception as error:
        raise AnalysisProtocolError(
            "invalid-read-request", "Read v3 request is invalid."
        ) from error
    names, index, offset, ordering = _scope(evidence, request)
    if index > len(names) or (index == len(names) and offset):
        raise AnalysisProtocolError(
            "invalid-cursor", "Read cursor position is outside its scope."
        )
    max_items = 1 if isinstance(request, ExactReadRequestV3) else request.max_items
    items: list[dict[str, Any]] = []
    while index < len(names) and len(items) < max_items:
        value = evidence.materials[names[index]]
        if offset >= len(value):
            raise AnalysisProtocolError(
                "invalid-cursor", "Read cursor offset is outside its material."
            )
        end = len(value)
        items.append(_fragment(evidence, names[index], value, offset, end))
        index += 1
        offset = 0
        response = _response(evidence, items, names, index, offset, ordering)
        while len(canonical_json_bytes(response)) > request.max_bytes:
            last = items.pop()
            index -= 1
            start = int(last["fragment_start"])
            value = evidence.materials[names[index]]
            high = int(last["fragment_end"])
            low = start + 1
            fitting: tuple[int, dict[str, Any], dict[str, Any]] | None = None
            while low <= high:
                middle = (low + high) // 2
                candidate = _fragment(evidence, names[index], value, start, middle)
                proposed = _response(
                    evidence,
                    [*items, candidate],
                    names,
                    index if middle < len(value) else index + 1,
                    middle if middle < len(value) else 0,
                    ordering,
                )
                if len(canonical_json_bytes(proposed)) <= request.max_bytes:
                    fitting = (middle, candidate, proposed)
                    low = middle + 1
                else:
                    high = middle - 1
            if fitting is None:
                raise AnalysisProtocolError(
                    "read-page-budget-too-small",
                    "Read response envelope exceeds max_bytes.",
                )
            end, candidate, response = fitting
            items.append(candidate)
            if end < len(value):
                offset = end
            else:
                index += 1
                offset = 0
            return response
    response = _response(evidence, items, names, index, offset, ordering)
    if len(canonical_json_bytes(response)) > request.max_bytes:
        raise AnalysisProtocolError(
            "read-page-budget-too-small", "Read response envelope exceeds max_bytes."
        )
    return response


__all__ = ["read_evidence_v3"]
