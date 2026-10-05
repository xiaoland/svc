"""Validate source-owned framework versions without a CLI runtime dependency."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath


CORPUS_VERSION_SCHEMA_VERSION = 2
_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")


def require_version(value: object) -> str:
    if not isinstance(value, str) or _VERSION.fullmatch(value) is None:
        raise ValueError(f"Corpus version must be stable x.y.z SemVer: {value!r}")
    return value


@dataclass(frozen=True)
class CorpusMigration:
    status: str
    paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class CorpusRelease:
    version: str
    previous_version: str
    migration: CorpusMigration


@dataclass(frozen=True)
class CorpusVersionIndex:
    corpus_version: str
    releases: tuple[CorpusRelease, ...]


def _migration(value: object) -> CorpusMigration:
    if not isinstance(value, dict):
        raise ValueError("Corpus release migration must be an object")
    status = value.get("status")
    if status == "not-required" and set(value) == {"status"}:
        return CorpusMigration(status)
    if status != "guide" or set(value) != {"status", "paths"}:
        raise ValueError("Corpus migration must be not-required or guide with paths")
    raw_paths = value["paths"]
    if not isinstance(raw_paths, list) or not raw_paths:
        raise ValueError("Corpus migration guide must name at least one path")
    paths = []
    for raw in raw_paths:
        if not isinstance(raw, str):
            raise ValueError("Corpus migration path must be a string")
        path = PurePosixPath(raw)
        if (
            not raw.startswith("migrations/")
            or path.suffix != ".md"
            or path.as_posix() != raw
            or any(part.startswith(".") for part in path.parts)
            or "\\" in raw
        ):
            raise ValueError(
                f"Corpus migration path must be under migrations/: {raw!r}"
            )
        paths.append(raw)
    if len(paths) != len(set(paths)):
        raise ValueError("Corpus migration guide paths must be unique")
    return CorpusMigration(status, tuple(paths))


def parse_version_index(content: bytes) -> CorpusVersionIndex:
    try:
        value = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Corpus version index must be valid UTF-8 JSON") from error
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "corpus_version",
        "releases",
    }:
        raise ValueError("Corpus version index has unsupported fields")
    if value["schema_version"] != CORPUS_VERSION_SCHEMA_VERSION:
        raise ValueError("Unsupported Corpus version index schema")
    version = require_version(value["corpus_version"])
    raw_releases = value["releases"]
    if not isinstance(raw_releases, list):
        raise ValueError("Corpus version index releases must be a list")
    releases = []
    previous = None
    for raw in raw_releases:
        if not isinstance(raw, dict) or set(raw) != {
            "version",
            "previous_version",
            "migration",
        }:
            raise ValueError("Corpus release has unsupported fields")
        before = require_version(raw["previous_version"])
        after = require_version(raw["version"])
        if previous is not None and before != previous:
            raise ValueError(f"Corpus release chain is not contiguous at {after}")
        if tuple(map(int, after.split("."))) <= tuple(map(int, before.split("."))):
            raise ValueError(f"Corpus release {after} must advance {before}")
        releases.append(CorpusRelease(after, before, _migration(raw["migration"])))
        previous = after
    if previous is not None and previous != version:
        raise ValueError("Corpus version must match the last release")
    return CorpusVersionIndex(version, tuple(releases))
