from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace

import pdm_build
from svc_cli.manifest import load_manifest, validate_behavioral_bump


REPO_ROOT = Path(__file__).resolve().parents[1]


class ManifestTests(unittest.TestCase):
    def test_manifest_is_complete_and_matches_package_version(self) -> None:
        manifest = load_manifest()
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(manifest.svc_version, pyproject["project"]["version"])
        self.assertEqual(manifest.previous_version, "9.8.0")
        self.assertEqual(
            {artifact.file_class for artifact in manifest.artifacts},
            {"svc-managed", "consumer-owned", "generated"},
        )
        self.assertEqual(len(manifest.artifacts), 5)
        self.assertEqual(manifest.state_artifact.target, ".svc/state.json")

    def test_manifest_is_canonical_json_with_valid_payload_digests(self) -> None:
        raw = json.loads((REPO_ROOT / "src/manifest.json").read_text(encoding="utf-8"))
        manifest = load_manifest()
        self.assertEqual(raw["svc_version"], manifest.svc_version)
        for artifact in manifest.artifacts:
            if artifact.source:
                self.assertEqual(artifact.digest, __import__("hashlib").sha256(artifact.content()).hexdigest())

    def test_behavioral_semver_requires_matching_bump(self) -> None:
        validate_behavioral_bump("9.8.0", "10.0.0", "major")
        validate_behavioral_bump("10.0.0", "10.1.0", "minor")
        validate_behavioral_bump("10.1.0", "10.1.1", "patch")
        with self.assertRaises(ValueError):
            validate_behavioral_bump("10.0.0", "10.0.1", "minor")

    def test_wheel_projection_contains_only_declared_release_resources(self) -> None:
        files: dict[str, Path] = {}
        pdm_build.pdm_build_update_files(
            SimpleNamespace(target="wheel", root=REPO_ROOT),
            files,
        )
        manifest = load_manifest()
        expected = {"svc_cli/data/manifest.json"}
        expected.update(
            f"svc_cli/data/{artifact.source}"
            for artifact in manifest.artifacts
            if artifact.source
        )
        self.assertEqual(set(files), expected)
        self.assertTrue(all(path.is_file() for path in files.values()))


if __name__ == "__main__":
    unittest.main()
