"""Small builders for project configuration used across behavior tests."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path


def write_project_config(
    root: Path,
    *,
    dev_resources: Mapping[str, object] | None = None,
    run_entries: Mapping[str, object] | None = None,
) -> Path:
    document: dict[str, object] = {"schema_version": 5}
    if dev_resources is not None:
        document["dev"] = {"resources": dict(dev_resources)}
    if run_entries is not None:
        document["run"] = dict(run_entries)
    path = root / "svc.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def write_local_run_overlay(root: Path, entries: Mapping[str, object]) -> Path:
    path = root / "svc.local.json"
    path.write_text(
        json.dumps({"schema_version": 5, "run": dict(entries)}),
        encoding="utf-8",
    )
    return path
