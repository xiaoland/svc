from __future__ import annotations

import tempfile
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

import pdm_build
from svc_cli.catalog import parse_catalog, sha256_bytes
from svc_cli import resources
from tools.build_catalog import (
    build_catalog_bytes,
    build_projection,
    canonical_documents,
)


ROOT = Path(__file__).resolve().parents[1]
PROJECTED_VERSION = "12.3.4"


def test_catalog_is_deterministic_and_covers_every_canonical_markdown_document() -> (
    None
):
    source = ROOT / "src"
    first = build_catalog_bytes(source, PROJECTED_VERSION)
    second = build_catalog_bytes(source, PROJECTED_VERSION)
    assert first == second

    catalog = parse_catalog(first)
    documents = canonical_documents(source)
    assert [entry.path for entry in catalog.entries] == [path for path, _ in documents]
    for entry, (_, source_path) in zip(catalog.entries, documents, strict=True):
        assert entry.sha256 == sha256_bytes(source_path.read_bytes())
        assert "content" not in entry.as_dict()

    assert catalog.svc_version == PROJECTED_VERSION


def test_wheel_projection_contains_catalog_and_one_copy_of_each_document() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        files = build_projection(ROOT, Path(tmp), PROJECTED_VERSION)
        assert "svc_cli/data/catalog.json" in files
        catalog = parse_catalog(files["svc_cli/data/catalog.json"].read_bytes())
        assert catalog.svc_version == PROJECTED_VERSION
        expected_corpus = {
            f"svc_cli/data/corpus/{entry.path}" for entry in catalog.entries
        }
        assert set(files) - {"svc_cli/data/catalog.json"} == expected_corpus
        assert all(path.is_file() for path in files.values())


def test_wheel_projection_has_no_legacy_source_manifest_dependency(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    source = root / "src"
    source.mkdir(parents=True)
    document = source / "index.md"
    document.write_text("# Source corpus\n", encoding="utf-8")

    files = build_projection(root, tmp_path / "build", PROJECTED_VERSION)

    catalog = parse_catalog(files["svc_cli/data/catalog.json"].read_bytes())
    assert catalog.svc_version == PROJECTED_VERSION
    assert [entry.path for entry in catalog.entries] == ["index.md"]
    assert files["svc_cli/data/corpus/index.md"] == document


def test_pdm_hook_projects_resolved_version_only_under_backend_build_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        build_dir = Path(tmp)
        context = SimpleNamespace(
            target="wheel",
            root=ROOT,
            build_dir=build_dir,
            config=SimpleNamespace(metadata={"version": PROJECTED_VERSION}),
        )
        files: dict[str, Path] = {}
        pdm_build.pdm_build_update_files(context, files)
        catalog_path = files["svc_cli/data/catalog.json"]
        assert catalog_path == build_dir / "svc_cli/data/catalog.json"
        assert parse_catalog(catalog_path.read_bytes()).svc_version == PROJECTED_VERSION
        assert all(name.startswith("svc_cli/data/") for name in files)

        untouched: dict[str, Path] = {}
        context.target = "sdist"
        pdm_build.pdm_build_update_files(context, untouched)
        assert untouched == {}


def test_pdm_hook_requires_backend_resolved_version() -> None:
    context = SimpleNamespace(
        target="wheel",
        root=ROOT,
        build_dir=ROOT / "unused",
        config=SimpleNamespace(metadata={}),
    )
    with pytest.raises(ValueError, match="resolve project.version"):
        pdm_build.pdm_build_update_files(context, {})


def test_scm_source_formatter_retains_latest_stable_tag_version() -> None:
    version = SimpleNamespace(version="11.2.3", distance=7, dirty=True)
    assert pdm_build.format_scm_version(version) == "11.2.3"


def test_pyproject_declares_strict_dynamic_scm_projection() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["dynamic"] == ["version"]
    assert "version" not in pyproject["project"]
    assert pyproject["build-system"]["requires"] == ["pdm-backend==2.4.9"]
    assert pyproject["tool"]["pdm"]["version"] == {
        "source": "scm",
        "tag_filter": "v[0-9]*.[0-9]*.[0-9]*",
        "tag_regex": r"^v(?P<version>(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*))$",
        "version_format": "pdm_build:format_scm_version",
        "fallback_version": "0.0.0",
    }


def test_source_catalog_uses_distribution_projection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "index.md").write_text("# Source corpus\n", encoding="utf-8")
    monkeypatch.setattr(resources, "_packaged_data_root", lambda: None)
    monkeypatch.setattr(resources, "source_root", lambda: source)
    monkeypatch.setattr(
        resources, "distribution_version", lambda name: PROJECTED_VERSION
    )
    assert (
        parse_catalog(resources.read_catalog_bytes()).svc_version == PROJECTED_VERSION
    )


def test_source_catalog_has_explicit_non_release_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "index.md").write_text("# Source corpus\n", encoding="utf-8")
    monkeypatch.setattr(resources, "_packaged_data_root", lambda: None)
    monkeypatch.setattr(resources, "source_root", lambda: source)

    def missing_distribution(name: str) -> str:
        raise resources.PackageNotFoundError(name)

    monkeypatch.setattr(resources, "distribution_version", missing_distribution)
    assert parse_catalog(resources.read_catalog_bytes()).svc_version == "0.0.0"
