from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"


class WorkflowContractTests(unittest.TestCase):
    def workflow(self, name: str) -> str:
        return (WORKFLOWS / name).read_text(encoding="utf-8")

    def test_every_action_is_pinned_to_a_commit(self) -> None:
        for path in sorted(WORKFLOWS.glob("*.yml")):
            uses = re.findall(r"uses:\s*([^\s#]+)", path.read_text(encoding="utf-8"))
            for action in uses:
                with self.subTest(workflow=path.name, action=action):
                    self.assertRegex(action, r"^[^@]+@[0-9a-f]{40}$")

    def test_ci_is_read_only_and_smokes_the_embedded_runtime_wheel(self) -> None:
        text = self.workflow("ci.yml")
        self.assertIn("contents: read", text)
        self.assertIn('python-version: ["3.11", "3.14"]', text)
        self.assertIn("pdm run release check-pr", text)
        self.assertIn("release:none", text)
        self.assertIn("pdm build", text)
        self.assertIn("svc lookup --name", text)
        self.assertIn("svc init", text)
        self.assertNotIn("svc migrate", text)
        self.assertNotIn("contents: write", text)

    def test_release_pr_uses_app_token_and_does_not_publish(self) -> None:
        text = self.workflow("release-pr.yml")
        self.assertIn("actions/create-github-app-token@", text)
        self.assertIn("pdm run release prepare", text)
        self.assertIn("migration guidance", text)
        self.assertIn("gh pr create", text)
        self.assertNotIn("gh release create", text)
        self.assertNotIn("gh-action-pypi-publish", text)

    def test_publish_is_protected_oidc_attested_and_exports_release_metadata(self) -> None:
        text = self.workflow("publish.yml")
        self.assertIn("environment: release", text)
        self.assertIn("id-token: write", text)
        self.assertIn("attestations: write", text)
        self.assertIn("actions/attest-build-provenance@", text)
        self.assertIn("pypa/gh-action-pypi-publish@", text)
        self.assertIn("pdm run release pypi-plan", text)
        self.assertIn("svc-release-metadata.json", text)
        self.assertIn('git config user.name "github-actions[bot]"', text)
        self.assertIn('git config user.email "41898282+github-actions[bot]@users.noreply.github.com"', text)
        self.assertNotIn("ghcr.io", text)


if __name__ == "__main__":
    unittest.main()
