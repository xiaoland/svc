"""Filesystem boundary for the two Agent analysis tools."""

from __future__ import annotations

from pathlib import Path

from ..telemetry.archive import rebuild_evidence_trajectory
from ..telemetry.evidence import EvidenceError, validate_evidence
from ..telemetry.evidence_v4 import validate_evidence_v4
from ..telemetry.providers import provider as local_provider
from .protocol import AnalysisProtocolError
from .query import query_evidence
from .read import read_evidence
from .query_v3 import query_evidence_v3
from .read_v3 import read_evidence_v3, read_evidence_v3_legacy
from .versions import analysis_route
from .models_v3 import QUERY_REQUEST_V3
from pydantic import ValidationError


def execute_query(input_path: Path, request: object) -> dict[str, object]:
    route = analysis_route(request, input_path)
    if route == "v3-on-v4":
        try:
            return query_evidence_v3(validate_evidence_v4(input_path), request)
        except EvidenceError as error:
            raise AnalysisProtocolError(error.code, error.message, error.details) from error
    if route == "v3-on-v3":
        try:
            typed = QUERY_REQUEST_V3.validate_python(request)
            legacy = validate_evidence(input_path)
        except ValidationError as error:
            raise AnalysisProtocolError("invalid-query-request", "Query v3 request is invalid.") from error
        except EvidenceError as error:
            raise AnalysisProtocolError(error.code, error.message, error.details) from error
        response: dict[str, object] = {
            "format": "svc.analysis.query/v3",
            "version": 3,
            "intent": typed.intent,
            "evidence_id": legacy.evidence_id,
            "status": "unavailable",
            "coverage": [],
            "issues": ["re-export-required"],
            "next_cursor": None,
        }
        if typed.intent == "overview":
            response.update({"roots": [], "executions": [], "relations": [], "counts": {}})
        elif typed.intent == "trace":
            response.update({"events": [], "content_refs": [], "native_refs": []})
        elif typed.intent == "profile":
            empty = {"known": [], "ambiguous_observations": 0, "unknown_observations": 0}
            response.update({"breakdown": typed.breakdown, "total": empty, "rows": []})
        else:
            response["refs"] = []
        return response
    try:
        evidence = validate_evidence(input_path)
    except EvidenceError as error:
        raise AnalysisProtocolError(error.code, error.message, error.details) from error
    evidence = rebuild_evidence_trajectory(evidence, local_provider())
    return query_evidence(evidence, request)


def execute_read(input_path: Path, request: object) -> dict[str, object]:
    route = analysis_route(request, input_path)
    if route == "v3-on-v4":
        try:
            return read_evidence_v3(validate_evidence_v4(input_path), request)
        except EvidenceError as error:
            raise AnalysisProtocolError(error.code, error.message, error.details) from error
    if route == "v3-on-v3":
        try:
            return read_evidence_v3_legacy(validate_evidence(input_path), request)
        except EvidenceError as error:
            raise AnalysisProtocolError(error.code, error.message, error.details) from error
    try:
        evidence = validate_evidence(input_path)
    except EvidenceError as error:
        raise AnalysisProtocolError(error.code, error.message, error.details) from error
    return read_evidence(evidence, request)


__all__ = ["execute_query", "execute_read"]
