from __future__ import annotations

import tempfile
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace

import pdm_build
from svc_cli.catalog import parse_catalog, sha256_bytes
from tools.build_catalog import build_catalog_bytes, build_projection, canonical_documents


ROOT = Path(__file__).resolve().parents[1]


class CatalogTests(unittest.TestCase):
    def test_catalog_is_deterministic_and_covers_every_canonical_markdown_document(self) -> None:
        source = ROOT / "src"
        first = build_catalog_bytes(source, source / "manifest.json")
        second = build_catalog_bytes(source, source / "manifest.json")
        self.assertEqual(first, second)

        catalog = parse_catalog(first)
        documents = canonical_documents(source)
        self.assertEqual([entry.path for entry in catalog.entries], [path for path, _ in documents])
        for entry, (_, source_path) in zip(catalog.entries, documents, strict=True):
            self.assertEqual(entry.sha256, sha256_bytes(source_path.read_bytes()))
            self.assertNotIn("content", entry.as_dict())

        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(catalog.svc_version, pyproject["project"]["version"])

    def test_wheel_projection_contains_catalog_and_one_copy_of_each_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            files = build_projection(ROOT, Path(tmp))
            self.assertIn("svc_cli/data/catalog.json", files)
            catalog = parse_catalog(files["svc_cli/data/catalog.json"].read_bytes())
            expected_corpus = {f"svc_cli/data/corpus/{entry.path}" for entry in catalog.entries}
            self.assertEqual(set(files) - {"svc_cli/data/catalog.json"}, expected_corpus)
            self.assertTrue(all(path.is_file() for path in files.values()))

    def test_pdm_hook_projects_only_runtime_catalog_resources_for_a_wheel(self) -> None:
        files: dict[str, Path] = {}
        pdm_build.pdm_build_update_files(SimpleNamespace(target="wheel", root=ROOT), files)
        self.assertIn("svc_cli/data/catalog.json", files)
        self.assertTrue(all(name.startswith("svc_cli/data/") for name in files))
        untouched: dict[str, Path] = {}
        pdm_build.pdm_build_update_files(SimpleNamespace(target="sdist", root=ROOT), untouched)
        self.assertEqual(untouched, {})

    def test_src_is_canonical_content_and_metadata_only(self) -> None:
        source = ROOT / "src"
        self.assertEqual(list((source / "svc_cli").rglob("*.py")) if (source / "svc_cli").exists() else [], [])
        self.assertEqual(list((source / "tools").rglob("*.py")) if (source / "tools").exists() else [], [])
        self.assertEqual(list(source.rglob("*.py")), [])
        self.assertTrue((ROOT / "svc_cli" / "cli.py").is_file())
        self.assertTrue((ROOT / "tools" / "build_catalog.py").is_file())


if __name__ == "__main__":
    unittest.main()
