from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.tools.release import (
    ReleaseError,
    bump,
    bump_impact,
    check,
    check_pr,
    fragments,
    pypi_plan,
    verify_migration,
    verify_prepared,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class ReleasePlannerTests(unittest.TestCase):
    def test_behavioral_bumps_are_exact(self) -> None:
        self.assertEqual(bump("10.2.3", "major"), "11.0.0")
        self.assertEqual(bump("10.2.3", "minor"), "10.3.0")
        self.assertEqual(bump("10.2.3", "patch"), "10.2.4")
        self.assertEqual(bump_impact("9.8.0", "10.0.0"), "major")
        with self.assertRaisesRegex(ReleaseError, "single Behavioral SemVer bump"):
            bump_impact("10.2.3", "10.3.1")

    def test_fragments_reject_unknown_names_and_empty_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            changes = root / "changes"
            changes.mkdir()
            (changes / "42.feature.md").write_text("Visible change\n", encoding="utf-8")
            with self.assertRaisesRegex(ReleaseError, "Invalid change fragment"):
                fragments(root)
            (changes / "42.feature.md").unlink()
            (changes / "42.patch.md").touch()
            with self.assertRaisesRegex(ReleaseError, "Empty change fragment"):
                fragments(root)

    def test_repository_release_contract_is_consistent(self) -> None:
        plan = check(REPO_ROOT)
        self.assertEqual(plan["base_version"], "9.8.0")
        self.assertEqual(plan["target_version"], "10.0.0")
        self.assertEqual(plan["impact"], "major")

    def test_feature_pr_does_not_prebump_released_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "changes").mkdir()
            (root / "src").mkdir()
            (root / "changes/42.minor.md").write_text(
                "Add an optional capability.\n", encoding="utf-8"
            )
            (root / "pyproject.toml").write_text(
                '[project]\nname = "fixture"\nversion = "10.0.0"\n\n[build-system]\n',
                encoding="utf-8",
            )
            (root / "src/manifest.json").write_text(
                json.dumps(
                    {
                        "previous_version": "9.8.0",
                        "svc_version": "10.0.0",
                        "behavioral_impact": {"level": "major", "reasons": ["released"]},
                    }
                ),
                encoding="utf-8",
            )
            with patch("src.tools.release.git_tags", return_value=["10.0.0"]):
                plan = check(root)
            self.assertEqual(plan["target_version"], "10.1.0")
            self.assertEqual(plan["impact"], "minor")

    def test_pypi_retry_accepts_only_identical_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp)
            wheel = dist / "example.whl"
            wheel.write_bytes(b"stable bytes")
            digest = __import__("hashlib").sha256(wheel.read_bytes()).hexdigest()
            response = unittest.mock.MagicMock()
            response.__enter__.return_value = response
            response.__exit__.return_value = False
            response.read.return_value = json.dumps(
                {"urls": [{"filename": wheel.name, "digests": {"sha256": digest}}]}
            ).encode()
            with patch("urllib.request.urlopen", return_value=response):
                result = pypi_plan(dist, REPO_ROOT)
            self.assertFalse(result["needed"])

    def test_prepared_release_has_no_fragments_and_has_release_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "changes").mkdir()
            (root / "src").mkdir()
            (root / "pyproject.toml").write_text(
                '[project]\nname = "fixture"\nversion = "10.0.0"\n\n[build-system]\n',
                encoding="utf-8",
            )
            (root / "src/manifest.json").write_text(
                json.dumps(
                    {
                        "previous_version": "9.8.0",
                        "svc_version": "10.0.0",
                        "behavioral_impact": {
                            "level": "major",
                            "reasons": ["contract change"],
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "CHANGELOG.md").write_text(
                "## [10.0.0] - 2026-07-13\n\n"
                "[10.0.0]: https://github.com/xiaoland/svc/releases/tag/v10.0.0\n",
                encoding="utf-8",
            )
            self.assertEqual(verify_prepared(root)["impact"], "major")

    def test_major_migration_non_applicability_must_be_explicit(self) -> None:
        with self.assertRaisesRegex(ReleaseError, "requires a sequential migration"):
            verify_migration("10.0.0", "11.0.0", "major")
        verify_migration(
            "10.0.0",
            "11.0.0",
            "major",
            {"status": "not-applicable", "reason": "No persisted consumer state."},
        )

    def test_pull_request_requires_fragment_or_release_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "changes").mkdir()
            diff = unittest.mock.MagicMock(stdout="README.md\n")
            with patch("subprocess.run", return_value=diff):
                with self.assertRaisesRegex(ReleaseError, "requires a change fragment"):
                    check_pr("origin/main", False, root)
                result = check_pr("origin/main", True, root)
            self.assertEqual(result["release"], "none")


if __name__ == "__main__":
    unittest.main()
