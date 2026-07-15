"""Project canonical SVC Markdown into a deterministic wheel corpus/catalog payload."""

from __future__ import annotations

import json
from pathlib import Path

from svc_cli.catalog import catalog_bytes, normalized_document_path, require_semver


ROOT = Path(__file__).resolve().parents[1]


def load_release_metadata(path: Path) -> dict[str, object]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 2:
        raise ValueError("SVC release metadata must use schema_version 2")
    require_semver(raw.get("svc_version"), "release svc_version")
    return raw


def canonical_documents(source_root: Path) -> list[tuple[str, Path]]:
    root = source_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Canonical SVC source does not exist: {source_root}")
    documents: list[tuple[str, Path]] = []
    for path in sorted(root.rglob("*.md")):
        if path.is_symlink():
            raise ValueError(f"Canonical source may not contain a symlinked Markdown document: {path}")
        if not path.is_file():
            continue
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError as error:
            raise ValueError(f"Canonical source escapes src/: {path}") from error
        documents.append((normalized_document_path(relative), resolved))
    if not documents:
        raise ValueError("Canonical SVC source contains no Markdown documents")
    return documents


def build_catalog_bytes(source_root: Path, release_metadata_path: Path) -> bytes:
    metadata = load_release_metadata(release_metadata_path)
    documents = canonical_documents(source_root)
    return catalog_bytes(
        str(metadata["svc_version"]),
        ((relative, path.read_bytes()) for relative, path in documents),
    )


def build_projection(root: Path = ROOT, output_dir: Path | None = None) -> dict[str, Path]:
    """Write the derived catalog once and return the exact wheel payload mapping."""

    source_root = root / "src"
    metadata_path = source_root / "manifest.json"
    documents = canonical_documents(source_root)
    catalog = build_catalog_bytes(source_root, metadata_path)
    destination = output_dir or root / "build" / "catalog"
    destination.mkdir(parents=True, exist_ok=True)
    catalog_path = destination / "catalog.json"
    catalog_path.write_bytes(catalog)

    files: dict[str, Path] = {"svc_cli/data/catalog.json": catalog_path}
    for relative, source in documents:
        files[f"svc_cli/data/corpus/{relative}"] = source
    return files
