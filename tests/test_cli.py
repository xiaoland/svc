from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from svc_cli.cli import EXIT_CONFLICT, EXIT_OK, main


class CliContractTests(unittest.TestCase):
    def invoke(self, arguments: list[str]) -> tuple[int, dict[str, object], str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(arguments)
        payload = json.loads(stdout.getvalue()) if stdout.getvalue() else json.loads(stderr.getvalue())
        return code, payload, stderr.getvalue()

    def test_lookup_machine_output_uses_source_relative_path_identity(self) -> None:
        code, payload, _ = self.invoke(["lookup", "--name", r"assets/templates/AGENTS\.local\.template\.md", "--json"])
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(payload["results"][0]["path"], "assets/templates/AGENTS.local.template.md")
        self.assertIn("content", payload["results"][0])

    def test_init_cli_is_plan_first_and_requires_its_exact_digest_to_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, plan, _ = self.invoke(["init", str(root), "--json"])
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(list(root.iterdir()), [])
            digest = str(plan["plan_digest"])

            wrong_code, wrong, _ = self.invoke(["init", str(root), "--apply", "0" * 64, "--json"])
            self.assertEqual(wrong_code, EXIT_CONFLICT)
            self.assertEqual(wrong["error"]["code"], "plan-digest-mismatch")

            applied_code, applied, _ = self.invoke(["init", str(root), "--apply", digest, "--json"])
            self.assertEqual(applied_code, EXIT_OK)
            self.assertEqual(applied["status"], "applied")

            status_code, status, _ = self.invoke(["status", str(root), "--json"])
            self.assertEqual(status_code, EXIT_OK)
            self.assertTrue(status["healthy"])

    def test_dev_identity_and_missing_configuration_status_are_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, identity, _ = self.invoke(["dev", "identity", "--repo", str(root), "--json"])
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(identity["command"], "dev identity")
            self.assertEqual(identity["workspace"]["repository_kind"], "non-git")

            code, status, _ = self.invoke(["dev", "status", "--repo", str(root), "--json"])
            self.assertEqual(code, EXIT_CONFLICT)
            self.assertEqual(status["status"], "invalid-configuration")

    def test_dev_setup_cli_is_plan_then_exact_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "svc.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "svc_version": "10.0.1",
                        "dev": {
                            "profile": "local",
                            "profiles": {
                                "local": {
                                    "targets": {
                                        "app": {
                                            "scope": "repository",
                                            "probe": {"kind": "exec", "argv": ["check"]},
                                            "provision": {"kind": "manual"},
                                        }
                                    }
                                }
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "package.json").write_text('{"name":"fixture"}\n', encoding="utf-8")
            code, plan, _ = self.invoke(["dev", "setup", "npm", "app", "--repo", str(root), "--plan", "--json"])
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(plan["status"], "ready")
            self.assertNotIn("svc:dev:app", (root / "package.json").read_text(encoding="utf-8"))
            digest = str(plan["plan_digest"])

            code, applied, _ = self.invoke(["dev", "setup", "npm", "app", "--repo", str(root), "--apply", digest, "--json"])
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(applied["status"], "applied")
            self.assertIn('"svc:dev:app": "svc dev ensure app"', (root / "package.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
