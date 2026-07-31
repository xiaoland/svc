"""Shared, machine-first protocol primitives for Agent analysis tools."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Mapping

from ..release import catalog
from ..telemetry.evidence import ValidatedEvidence
from ..telemetry.trajectory import canonical_json_bytes


ANALYSIS_CONTRACT_VERSION = 1
METHOD_ID = "svc.agent-task-analysis"
METHOD_PATH = "sections/working-protocol.md"
METHOD_SECTION = "Agent Task Analysis"
_CURSOR_DOMAIN = b"svc-analysis-cursor-v1\0"


class AnalysisProtocolError(ValueError):
    """Stable request, reference, and cursor error."""

    def __init__(
        self,
        code: str,
        message: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = MappingProxyType(dict(details or {}))

    def as_dict(self) -> dict[str, object]:
        value: dict[str, object] = {
            "code": self.code,
            "message": self.message,
        }
        if self.details:
            value["details"] = dict(self.details)
        return value


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    evidence_id: str
    record_kind: str
    record_id: str

    def as_dict(self) -> dict[str, str]:
        return {
            "evidence_id": self.evidence_id,
            "record_kind": self.record_kind,
            "record_id": self.record_id,
        }


def method_reference() -> dict[str, str]:
    """Resolve the analysis method to the exact packaged/source catalog digest."""

    entry = next(
        (item for item in catalog().entries if item.path == METHOD_PATH),
        None,
    )
    if entry is None:
        raise AnalysisProtocolError(
            "analysis-method-unavailable",
            "The packaged Agent Task Analysis method is unavailable.",
            {"path": METHOD_PATH},
        )
    return {
        "id": METHOD_ID,
        "path": METHOD_PATH,
        "section": METHOD_SECTION,
        "sha256": entry.sha256,
    }


def evidence_ref(
    evidence: ValidatedEvidence,
    record_kind: str,
    record_id: str,
) -> dict[str, str]:
    return EvidenceRef(
        evidence.evidence_id,
        record_kind,
        record_id,
    ).as_dict()


def parse_ref(
    value: object,
    evidence: ValidatedEvidence,
    *,
    expected_kind: str | None = None,
) -> EvidenceRef:
    if not isinstance(value, Mapping) or set(value) != {
        "evidence_id",
        "record_kind",
        "record_id",
    }:
        raise AnalysisProtocolError(
            "invalid-reference",
            "Evidence reference has an invalid shape.",
        )
    evidence_id = value["evidence_id"]
    record_kind = value["record_kind"]
    record_id = value["record_id"]
    if not (
        isinstance(evidence_id, str)
        and isinstance(record_kind, str)
        and isinstance(record_id, str)
    ):
        raise AnalysisProtocolError(
            "invalid-reference",
            "Evidence reference fields must be strings.",
        )
    reference = EvidenceRef(
        evidence_id,
        record_kind,
        record_id,
    )
    if reference.evidence_id != evidence.evidence_id:
        raise AnalysisProtocolError(
            "reference-scope-mismatch",
            "Evidence reference belongs to a different evidence snapshot.",
        )
    if expected_kind is not None and reference.record_kind != expected_kind:
        raise AnalysisProtocolError(
            "reference-kind-mismatch",
            f"Evidence reference must identify a {expected_kind} record.",
        )
    return reference


def request_fingerprint(value: Mapping[str, object]) -> str:
    return hashlib.sha256(
        b"svc-analysis-request-v1\0" + canonical_json_bytes(value)
    ).hexdigest()


def encode_cursor(payload: Mapping[str, object]) -> str:
    body = canonical_json_bytes(payload)
    envelope = {
        "payload": dict(payload),
        "sha256": hashlib.sha256(_CURSOR_DOMAIN + body).hexdigest(),
    }
    encoded = base64.urlsafe_b64encode(canonical_json_bytes(envelope))
    return encoded.rstrip(b"=").decode("ascii")


def decode_cursor(value: object, *, tool: str) -> Mapping[str, object]:
    if not isinstance(value, str) or not value or len(value) > 8192:
        raise AnalysisProtocolError(
            "invalid-cursor",
            "Cursor must be bounded non-empty text.",
        )
    try:
        padding = "=" * (-len(value) % 4)
        raw = base64.b64decode(
            (value + padding).encode("ascii"),
            altchars=b"-_",
            validate=True,
        )
        envelope = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AnalysisProtocolError(
            "invalid-cursor",
            "Cursor is not a valid analysis continuation.",
        ) from error
    if (
        not isinstance(envelope, Mapping)
        or set(envelope) != {"payload", "sha256"}
        or not isinstance(envelope["payload"], Mapping)
        or not isinstance(envelope["sha256"], str)
    ):
        raise AnalysisProtocolError(
            "invalid-cursor",
            "Cursor envelope has an invalid shape.",
        )
    body = canonical_json_bytes(envelope["payload"])
    expected = hashlib.sha256(_CURSOR_DOMAIN + body).hexdigest()
    if envelope["sha256"] != expected:
        raise AnalysisProtocolError(
            "invalid-cursor",
            "Cursor integrity check failed.",
        )
    payload = dict(envelope["payload"])
    if (
        payload.get("version") != ANALYSIS_CONTRACT_VERSION
        or payload.get("tool") != tool
    ):
        raise AnalysisProtocolError(
            "cursor-scope-mismatch",
            "Cursor belongs to a different analysis contract or tool.",
        )
    return payload


__all__ = [
    "ANALYSIS_CONTRACT_VERSION",
    "AnalysisProtocolError",
    "EvidenceRef",
    "decode_cursor",
    "encode_cursor",
    "evidence_ref",
    "method_reference",
    "parse_ref",
    "request_fingerprint",
]
