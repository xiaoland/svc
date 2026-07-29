from __future__ import annotations

import tempfile
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pdm_build
from svc_cli.catalog import parse_catalog, sha256_bytes
from tools.build_catalog import build_catalog_bytes, build_projection, canonical_documents


ROOT = Path(__file__).resolve().parents[1]


def test_catalog_is_deterministic_and_covers_every_canonical_markdown_document() -> None:
    source = ROOT / "src"
    first = build_catalog_bytes(source, source / "manifest.json")
    second = build_catalog_bytes(source, source / "manifest.json")
    assert first == second

    catalog = parse_catalog(first)
    documents = canonical_documents(source)
    assert [entry.path for entry in catalog.entries] == [path for path, _ in documents]
    for entry, (_, source_path) in zip(catalog.entries, documents, strict=True):
        assert entry.sha256 == sha256_bytes(source_path.read_bytes())
        assert "content" not in entry.as_dict()

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert catalog.svc_version == pyproject["project"]["version"]


def test_wheel_projection_contains_catalog_and_one_copy_of_each_document() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        files = build_projection(ROOT, Path(tmp))
        assert "svc_cli/data/catalog.json" in files
        catalog = parse_catalog(files["svc_cli/data/catalog.json"].read_bytes())
        expected_corpus = {f"svc_cli/data/corpus/{entry.path}" for entry in catalog.entries}
        assert set(files) - {"svc_cli/data/catalog.json"} == expected_corpus
        assert all(path.is_file() for path in files.values())


def test_pdm_hook_projects_only_runtime_catalog_resources_for_a_wheel() -> None:
    files: dict[str, Path] = {}
    pdm_build.pdm_build_update_files(SimpleNamespace(target="wheel", root=ROOT), files)
    assert "svc_cli/data/catalog.json" in files
    assert all(name.startswith("svc_cli/data/") for name in files)
    untouched: dict[str, Path] = {}
    pdm_build.pdm_build_update_files(SimpleNamespace(target="sdist", root=ROOT), untouched)
    assert untouched == {}
