"""Explicit analysis API and evidence compatibility routing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Mapping
import zipfile

from .protocol import AnalysisProtocolError


AnalysisRoute = Literal["v2-on-v3", "v3-on-v3", "v3-on-v4"]


def requested_analysis_version(request: object) -> int:
    if not isinstance(request, Mapping):
        raise AnalysisProtocolError("invalid-query-request", "Analysis request must be an object.")
    version = request.get("version", 2)
    if type(version) is not int or version not in {2, 3}:
        raise AnalysisProtocolError("unsupported-analysis-version", "Analysis version must be 2 or 3.")
    return version


def evidence_schema_version(path: Path) -> int:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            raw = archive.read("manifest.json")
        value = json.loads(raw)
        version = value.get("schema_version") if isinstance(value, dict) else None
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        raise AnalysisProtocolError("bundle-invalid", "Evidence manifest cannot be read.") from error
    if type(version) is not int:
        raise AnalysisProtocolError("invalid-evidence-manifest", "Evidence schema version is missing.")
    return version


def analysis_route(request: object, path: Path) -> AnalysisRoute:
    api = requested_analysis_version(request)
    evidence = evidence_schema_version(path)
    if evidence in {1, 2}:
        raise AnalysisProtocolError(
            "unsupported-agent-thread-bundle-schema",
            "Schema-v1/v2 bundles require recollection.",
        )
    if evidence not in {3, 4}:
        raise AnalysisProtocolError("unsupported-agent-thread-bundle-schema", "Evidence schema is unsupported.")
    if api == 2 and evidence == 4:
        raise AnalysisProtocolError(
            "analysis-version-incompatible",
            "Analysis v2 cannot consume evidence v4; use an explicit version 3 request.",
        )
    if api == 2:
        return "v2-on-v3"
    return "v3-on-v3" if evidence == 3 else "v3-on-v4"


__all__ = ["analysis_route", "evidence_schema_version", "requested_analysis_version"]
