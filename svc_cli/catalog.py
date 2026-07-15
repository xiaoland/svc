"""The small, validated catalog that names the packaged SVC corpus."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Iterable


CATALOG_SCHEMA_VERSION = 1
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def require_semver(value: object, label: str) -> str:
    if not isinstance(value, str) or not SEMVER_RE.fullmatch(value):
        raise ValueError(f"{label} must be stable x.y.z SemVer: {value!r}")
    return value


def normalized_document_path(value: object, label: str = "document path") -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty normalized relative path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or "." in path.parts
        or ".." in path.parts
        or any(part.startswith(".") for part in path.parts)
        or path.suffix != ".md"
    ):
        raise ValueError(f"{label} must be a visible normalized Markdown path: {value!r}")
    normalized = path.as_posix()
    if normalized != value:
        raise ValueError(f"{label} must use normalized POSIX separators: {value!r}")
    return normalized


def title_from_markdown(content: bytes, fallback_path: str) -> str:
    text = content.decode("utf-8")
    match = TITLE_RE.search(text)
    if match:
        return match.group(1).rstrip("#").strip()
    return PurePosixPath(fallback_path).stem.replace("-", " ")


@dataclass(frozen=True)
class CatalogEntry:
    """One canonical Markdown document, addressed by its source-relative path."""

    path: str
    title: str
    sha256: str

    @classmethod
    def from_mapping(cls, raw: object) -> "CatalogEntry":
        if not isinstance(raw, dict):
            raise ValueError("Every catalog entry must be an object")
        path = normalized_document_path(raw.get("path"))
        title = raw.get("title")
        digest = raw.get("sha256")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"Catalog entry {path} needs a title")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"Catalog entry {path} has an invalid sha256")
        if set(raw) != {"path", "title", "sha256"}:
            raise ValueError(f"Catalog entry {path} has unsupported fields")
        return cls(path=path, title=title, sha256=digest)

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "title": self.title, "sha256": self.sha256}


@dataclass(frozen=True)
class Catalog:
    """Release metadata sufficient to address and integrity-check the corpus."""

    schema_version: int
    svc_version: str
    entries: tuple[CatalogEntry, ...]

    @classmethod
    def from_mapping(cls, raw: object) -> "Catalog":
        if not isinstance(raw, dict):
            raise ValueError("Catalog must be a JSON object")
        if raw.get("schema_version") != CATALOG_SCHEMA_VERSION:
            raise ValueError(f"Unsupported catalog schema: {raw.get('schema_version')!r}")
        if set(raw) != {"schema_version", "svc_version", "entries"}:
            raise ValueError("Catalog has unsupported fields")
        version = require_semver(raw.get("svc_version"), "catalog svc_version")
        entries_raw = raw.get("entries")
        if not isinstance(entries_raw, list) or not entries_raw:
            raise ValueError("Catalog must contain at least one entry")
        entries = tuple(CatalogEntry.from_mapping(item) for item in entries_raw)
        paths = tuple(entry.path for entry in entries)
        if len(paths) != len(set(paths)):
            raise ValueError("Catalog document paths must be unique")
        if paths != tuple(sorted(paths)):
            raise ValueError("Catalog entries must be path-sorted")
        return cls(CATALOG_SCHEMA_VERSION, version, entries)

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "svc_version": self.svc_version,
            "entries": [entry.as_dict() for entry in self.entries],
        }


def catalog_bytes(svc_version: str, documents: Iterable[tuple[str, bytes]]) -> bytes:
    """Build canonical catalog bytes without copying Markdown bodies into the catalog."""

    require_semver(svc_version, "catalog svc_version")
    entries = []
    for path, content in documents:
        normalized = normalized_document_path(path)
        entries.append(
            CatalogEntry(
                path=normalized,
                title=title_from_markdown(content, normalized),
                sha256=sha256_bytes(content),
            )
        )
    paths = [entry.path for entry in entries]
    if len(paths) != len(set(paths)):
        raise ValueError("Catalog document paths must be unique")
    catalog = Catalog(CATALOG_SCHEMA_VERSION, svc_version, tuple(sorted(entries, key=lambda item: item.path)))
    return canonical_json(catalog.as_dict())


def parse_catalog(content: bytes) -> Catalog:
    return Catalog.from_mapping(json.loads(content))
