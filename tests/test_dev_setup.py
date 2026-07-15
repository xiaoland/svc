from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from svc_cli.dev.setup import plan_setup
from svc_cli.errors import SvcError
from svc_cli.plans import apply_local_plan


class DevSetupTests(unittest.TestCase):
    def write_config(self, root: Path, targets: tuple[str, ...] = ("frontend",)) -> None:
        target = {
            "probe": {"kind": "exec", "argv": ["true"]},
            "provision": {"kind": "manual"},
        }
        value = {
            "schema_version": 2,
            "svc_version": "10.0.1",
            "dev": {"profile": "local", "profiles": {"local": {"targets": {name: target for name in targets}}}},
        }
        (root / "svc.json").write_text(json.dumps(value), encoding="utf-8")

    def test_vscode_jsonc_insert_is_surgical_idempotent_and_leaves_launch_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_config(root, ("frontend", "backend"))
            vscode = root / ".vscode"
            vscode.mkdir()
            tasks = vscode / "tasks.json"
            original = (
                b"{\r\n"
                b"  // Consumer comment\r\n"
                b"  \"version\": \"2.0.0\",\r\n"
                b"  \"tasks\": [\r\n"
                b"    {\"label\":\"consumer\",\"command\":\"keep\"},\r\n"
                b"  ],\r\n"
                b"}\r\n"
            )
            tasks.write_bytes(original)
            launch = vscode / "launch.json"
            launch.write_bytes(b'{"consumer":true}\r\n')
            before_launch = launch.read_bytes()

            plan = plan_setup(root, "vscode")
            self.assertEqual(plan.status, "ready")
            self.assertEqual(tasks.read_bytes(), original)
            apply_local_plan(plan, plan.digest)
            updated = tasks.read_bytes()
            self.assertIn(b"// Consumer comment\r\n", updated)
            self.assertIn(b'{"label":"consumer","command":"keep"}', updated)
            self.assertIn(b"svc:dev:begin target=frontend", updated)
            self.assertIn(b"svc:dev:begin target=backend", updated)
            self.assertNotIn(b"\n", updated.replace(b"\r\n", b""))
            self.assertEqual(launch.read_bytes(), before_launch)
            self.assertEqual(plan_setup(root, "vscode").status, "noop")

    def test_vscode_edited_marker_or_reserved_label_blocks_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_config(root)
            initial = plan_setup(root, "vscode")
            apply_local_plan(initial, initial.digest)
            tasks = root / ".vscode" / "tasks.json"
            edited = tasks.read_bytes().replace(b'"command": "svc"', b'"command": "consumer"')
            tasks.write_bytes(edited)
            blocked = plan_setup(root, "vscode")
            self.assertIn("invalid-vscode-tasks", {item.code for item in blocked.blockers})
            self.assertEqual(tasks.read_bytes(), edited)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_config(root)
            (root / ".vscode").mkdir()
            tasks = root / ".vscode" / "tasks.json"
            original = b'{"version":"2.0.0","tasks":[{"label":"svc:dev:frontend"}]}'
            tasks.write_bytes(original)
            blocked = plan_setup(root, "vscode")
            self.assertIn("invalid-vscode-tasks", {item.code for item in blocked.blockers})
            self.assertEqual(tasks.read_bytes(), original)

    def test_npm_is_root_only_surgical_conflict_safe_and_preserves_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_config(root)
            package = root / "package.json"
            original = b'{\n  "name": "consumer",\n  "scripts": {\n    "test": "pytest"\n  }\n}\n'
            package.write_bytes(original)
            package.chmod(0o640)
            plan = plan_setup(root, "npm")
            self.assertEqual(plan.status, "ready")
            apply_local_plan(plan, plan.digest)
            updated = package.read_bytes()
            self.assertIn(b'"test": "pytest",', updated)
            self.assertIn(b'"svc:dev:frontend": "svc dev ensure frontend"', updated)
            self.assertEqual(stat.S_IMODE(package.stat().st_mode), 0o640)
            self.assertEqual(plan_setup(root, "npm").status, "noop")

            package.write_bytes(updated.replace(b"svc dev ensure frontend", b"consumer command"))
            conflict = plan_setup(root, "npm")
            self.assertIn("invalid-package-json", {item.code for item in conflict.blockers})

            package.write_bytes(b'{"scripts":{"test":"ok",}}')
            malformed = plan_setup(root, "npm")
            self.assertIn("invalid-package-json", {item.code for item in malformed.blockers})

    def test_plan_digest_binds_config_and_destination_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_config(root)
            (root / "package.json").write_text('{"name":"consumer"}', encoding="utf-8")
            plan = plan_setup(root, "npm")
            (root / "package.json").write_text('{"name":"changed"}', encoding="utf-8")
            with self.assertRaises(SvcError) as raised:
                apply_local_plan(plan, plan.digest)
            self.assertEqual(raised.exception.code, "stale-plan")

            first = plan_setup(root, "npm")
            self.write_config(root, ("frontend", "backend"))
            second = plan_setup(root, "npm")
            self.assertNotEqual(first.digest, second.digest)

    def test_vscode_parent_symlink_swap_after_planning_is_stale_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_config(root)
            plan = plan_setup(root, "vscode")
            redirected = root / "redirected"
            redirected.mkdir()
            try:
                os.symlink(redirected, root / ".vscode")
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")
            with self.assertRaises(SvcError) as raised:
                apply_local_plan(plan, plan.digest)
            self.assertEqual(raised.exception.code, "stale-plan")
            self.assertFalse((redirected / "tasks.json").exists())


if __name__ == "__main__":
    unittest.main()
