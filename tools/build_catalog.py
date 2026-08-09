"""Project canonical SVC Markdown into a deterministic wheel corpus/catalog payload."""

from __future__ import annotations

from pathlib import Path

from svc_cli.catalog import (
    CorpusVersionIndex,
    catalog_bytes,
    normalized_document_path,
    parse_version_index,
)


def canonical_documents(source_root: Path) -> list[tuple[str, Path]]:
    root = source_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Canonical SVC source does not exist: {source_root}")
    documents: list[tuple[str, Path]] = []
    for path in sorted(root.rglob("*.md")):
        if path.is_symlink():
            raise ValueError(
                f"Canonical source may not contain a symlinked Markdown document: {path}"
            )
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


def read_version_index(source_root: Path) -> CorpusVersionIndex:
    version_path = source_root / "version.json"
    if not version_path.is_file():
        raise FileNotFoundError(f"Corpus version index does not exist: {version_path}")
    return parse_version_index(version_path.read_bytes())


def build_catalog_bytes(source_root: Path) -> bytes:
    documents = canonical_documents(source_root)
    return catalog_bytes(
        read_version_index(source_root),
        ((relative, path.read_bytes()) for relative, path in documents),
    )


def build_projection(root: Path, output_dir: Path) -> dict[str, Path]:
    """Write the derived catalog once and return the exact wheel payload mapping."""

    source_root = root / "src"
    documents = canonical_documents(source_root)
    catalog = catalog_bytes(
        read_version_index(source_root),
        ((relative, path.read_bytes()) for relative, path in documents),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = output_dir / "catalog.json"
    catalog_path.write_bytes(catalog)

    files: dict[str, Path] = {"svc_cli/data/catalog.json": catalog_path}
    for relative, source in documents:
        files[f"svc_cli/data/corpus/{relative}"] = source
    for descriptor in sorted((root / "svc_cli/data/migrations").glob("config-*.json")):
        files[f"svc_cli/data/migrations/{descriptor.name}"] = descriptor
    return files
