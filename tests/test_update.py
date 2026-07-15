from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import svc_cli.update as update
from svc_cli.errors import SvcError
from svc_cli.update import SelfUpdatePlan, apply_self_update, plan_self_update


class FakeDistribution:
    def __init__(self, version: str = "10.0.0", installer: str | None = "pip", direct_url: str | None = None) -> None:
        self.version = version
        self.installer = installer
        self.direct_url = direct_url

    def read_text(self, name: str) -> str | None:
        if name == "INSTALLER":
            return self.installer
        if name == "direct_url.json":
            return self.direct_url
        return None


class SelfUpdateTests(unittest.TestCase):
    def test_pip_plan_is_explicit_and_editable_or_unknown_installers_block(self) -> None:
        with patch("svc_cli.update.distribution", return_value=FakeDistribution()):
            plan = plan_self_update()
        self.assertEqual(plan.status, "ready")
        self.assertEqual(plan.installer, "pip")
        self.assertEqual(plan.command[-3:], ("install", "--upgrade", "sustainable-vibe-coding"))

        editable = '{"dir_info": {"editable": true}}'
        with patch("svc_cli.update.distribution", return_value=FakeDistribution(direct_url=editable)):
            blocked = plan_self_update()
        self.assertIn("editable-install", {item.code for item in blocked.blockers})

        with patch("svc_cli.update.distribution", return_value=FakeDistribution(installer="uv")):
            unsupported = plan_self_update()
        self.assertIn("unsupported-installer", {item.code for item in unsupported.blockers})

    def test_apply_requires_exact_unchanged_plan_and_verifies_in_a_fresh_interpreter(self) -> None:
        plan = SelfUpdatePlan(
            "10.0.0",
            ("python", "-m", "pip", "install", "--upgrade", "sustainable-vibe-coding"),
            "pip",
            (),
        )
        with self.assertRaisesRegex(SvcError, "does not match"):
            apply_self_update(plan, "0" * 64)

        with (
            patch("svc_cli.update._installed_version", return_value="10.0.0"),
            patch("svc_cli.update._run_update", return_value=SimpleNamespace(returncode=0, stderr="")),
            patch("svc_cli.update._fresh_installed_version", return_value="10.1.0"),
        ):
            result = apply_self_update(plan, plan.digest)
        self.assertEqual(result["status"], "updated")
        self.assertEqual(result["previous_version"], "10.0.0")
        self.assertEqual(result["installed_cli_version"], "10.1.0")

        with patch("svc_cli.update._installed_version", return_value="10.0.1"):
            with self.assertRaisesRegex(SvcError, "changed after planning"):
                apply_self_update(plan, plan.digest)


if __name__ == "__main__":
    unittest.main()
