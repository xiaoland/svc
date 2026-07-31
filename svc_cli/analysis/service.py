"""Filesystem boundary for the two Agent analysis tools."""

from __future__ import annotations

from pathlib import Path

from ..telemetry.evidence import EvidenceError, validate_evidence
from .protocol import AnalysisProtocolError
from .query import query_evidence
from .read import read_evidence


def execute_query(input_path: Path, request: object) -> dict[str, object]:
    try:
        evidence = validate_evidence(input_path)
    except EvidenceError as error:
        raise AnalysisProtocolError(error.code, error.message, error.details) from error
    return query_evidence(evidence, request)


def execute_read(input_path: Path, request: object) -> dict[str, object]:
    try:
        evidence = validate_evidence(input_path)
    except EvidenceError as error:
        raise AnalysisProtocolError(error.code, error.message, error.details) from error
    return read_evidence(evidence, request)


__all__ = ["execute_query", "execute_read"]
