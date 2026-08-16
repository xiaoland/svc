from __future__ import annotations

import json
import os
import runpy
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from svc_cli import resources
from svc_cli.catalog import parse_catalog, parse_version_index, sha256_bytes
from tools.build_catalog import (
    build_catalog_bytes,
    build_projection,
    canonical_documents,
    read_version_index,
)


ROOT = Path(__file__).resolve().parents[1]
PDM_BUILD_UPDATE_FILES = runpy.run_path(str(ROOT / "svc_cli/pdm_build.py"))[
    "pdm_build_update_files"
]


def test_catalog_is_deterministic_and_covers_every_canonical_markdown_document() -> (
    None
):
    source = ROOT / "src"
    first = build_catalog_bytes(source)
    second = build_catalog_bytes(source)
    assert first == second

    catalog = parse_catalog(first)
    documents = canonical_documents(source)
    assert [entry.path for entry in catalog.entries] == [path for path, _ in documents]
    for entry, (_, source_path) in zip(catalog.entries, documents, strict=True):
        assert entry.sha256 == sha256_bytes(source_path.read_bytes())
        assert "content" not in entry.as_dict()

    index = read_version_index(source)
    assert catalog.corpus_version == index.corpus_version == "13.0.0"
    assert catalog.releases == index.releases
    assert index.supported_anchor == "10.0.1"


def test_wheel_projection_contains_catalog_and_one_copy_of_each_document() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        files = build_projection(ROOT / "src", Path(tmp))
        assert "svc_cli/data/catalog.json" in files
        catalog = parse_catalog(files["svc_cli/data/catalog.json"].read_bytes())
        assert catalog.corpus_version == "13.0.0"
        expected_corpus = {
            f"svc_cli/data/corpus/{entry.path}" for entry in catalog.entries
        }
        assert set(files) == {
            "svc_cli/data/catalog.json",
            *expected_corpus,
        }
        assert all(path.is_file() for path in files.values())


def test_catalog_and_wheel_exclude_only_root_agents_document(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src"
    (source / "nested").mkdir(parents=True)
    (source / "index.md").write_text("# Source corpus\n", encoding="utf-8")
    (source / "AGENTS.md").write_text("# Authoring instructions\n", encoding="utf-8")
    (source / "nested" / "AGENTS.md").write_text(
        "# Nested corpus document\n", encoding="utf-8"
    )
    (source / "nested" / "other.md").write_text(
        "# Other corpus document\n", encoding="utf-8"
    )
    (source / "version.json").write_text(
        '{"schema_version":1,"releases":[{"version":"7.1.0",'
        '"previous_version":"7.0.0","migration":{"status":"not-required"}}]}',
        encoding="utf-8",
    )

    documents = canonical_documents(source)
    assert [path for path, _ in documents] == [
        "index.md",
        "nested/AGENTS.md",
        "nested/other.md",
    ]

    with tempfile.TemporaryDirectory() as output:
        files = build_projection(source, Path(output))
        assert "svc_cli/data/corpus/AGENTS.md" not in files
        assert "svc_cli/data/corpus/nested/AGENTS.md" in files
        catalog = parse_catalog(files["svc_cli/data/catalog.json"].read_bytes())
        assert [entry.path for entry in catalog.entries] == [
            "index.md",
            "nested/AGENTS.md",
            "nested/other.md",
        ]


@pytest.mark.parametrize("kind", ("symlink", "directory"))
def test_catalog_rejects_non_regular_root_agents_document(
    tmp_path: Path,
    kind: str,
) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "index.md").write_text("# Source corpus\n", encoding="utf-8")
    agents = source / "AGENTS.md"
    if kind == "symlink":
        target = tmp_path / "authoring.md"
        target.write_text("# Authoring instructions\n", encoding="utf-8")
        try:
            os.symlink(target, agents)
        except OSError as error:
            pytest.skip(f"symlinks unavailable: {error}")
    else:
        agents.mkdir()

    with pytest.raises(ValueError, match="authoring instructions"):
        canonical_documents(source)


def test_wheel_projection_reads_corpus_version_from_source_index(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    source = root / "src"
    source.mkdir(parents=True)
    document = source / "index.md"
    document.write_text("# Source corpus\n", encoding="utf-8")
    (source / "version.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "releases": [
                    {
                        "version": "7.1.0",
                        "previous_version": "7.0.0",
                        "migration": {"status": "not-required"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    files = build_projection(source, tmp_path / "build")

    catalog = parse_catalog(files["svc_cli/data/catalog.json"].read_bytes())
    assert catalog.corpus_version == "7.1.0"
    assert [entry.path for entry in catalog.entries] == ["index.md"]
    assert files["svc_cli/data/corpus/index.md"] == document


def test_pdm_hook_ignores_distribution_version_for_corpus_projection() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        build_dir = Path(tmp)
        for package_version in ("12.3.4", "99.0.0"):
            context = SimpleNamespace(
                target="wheel",
                root=ROOT / "svc_cli",
                build_dir=build_dir / package_version,
                config=SimpleNamespace(metadata={"version": package_version}),
            )
            files: dict[str, Path] = {}
            PDM_BUILD_UPDATE_FILES(context, files)
            catalog_path = files["svc_cli/data/catalog.json"]
            assert catalog_path == context.build_dir / "svc_cli/data/catalog.json"
            assert parse_catalog(catalog_path.read_bytes()).corpus_version == "13.0.0"
            assert all(name.startswith("svc_cli/data/") for name in files)

        sdist_files: dict[str, Path] = {}
        context.target = "sdist"
        PDM_BUILD_UPDATE_FILES(context, sdist_files)
        assert sdist_files["_build_inputs/corpus/version.json"] == (
            ROOT / "src/version.json"
        )
        expected_paths = {
            entry.path
            for entry in parse_catalog(build_catalog_bytes(ROOT / "src")).entries
        }
        assert {
            name.removeprefix("_build_inputs/corpus/")
            for name in sdist_files
            if name.endswith(".md")
        } == expected_paths


def test_source_catalog_uses_the_same_source_owned_corpus_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "index.md").write_text("# Source corpus\n", encoding="utf-8")
    (source / "version.json").write_text(
        '{"schema_version":1,"releases":[{"version":"3.0.0",'
        '"previous_version":"2.0.0","migration":{"status":"not-required"}}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(resources, "_packaged_data_root", lambda: None)
    monkeypatch.setattr(resources, "source_root", lambda: source)

    assert parse_catalog(resources.read_catalog_bytes()).corpus_version == "3.0.0"


@pytest.mark.parametrize(
    ("raw", "message"),
    (
        (
            {
                "schema_version": 1,
                "releases": [
                    {
                        "version": "2.0.0",
                        "previous_version": "1.0.0",
                        "migration": {"status": "not-required"},
                    },
                    {
                        "version": "2.1.0",
                        "previous_version": "1.9.0",
                        "migration": {"status": "not-required"},
                    },
                ],
            },
            "not contiguous",
        ),
        (
            {
                "schema_version": 1,
                "releases": [
                    {
                        "version": "2.0.0",
                        "previous_version": "1.0.0",
                        "migration": {},
                    }
                ],
            },
            "status",
        ),
    ),
)
def test_version_index_rejects_incomplete_release_authority(
    raw: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        parse_version_index(json.dumps(raw).encode())


def test_catalog_builder_rejects_a_missing_guide(tmp_path: Path) -> None:
    (tmp_path / "index.md").write_text("# Corpus\n", encoding="utf-8")
    (tmp_path / "version.json").write_text(
        '{"schema_version":1,"releases":[{"version":"2.0.0",'
        '"previous_version":"1.0.0","migration":{"status":"guide",'
        '"paths":["migrations/missing.md"]}}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="references missing guide"):
        build_catalog_bytes(tmp_path)
