from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import svc_cli.engine as engine
from svc_cli.engine import ProtocolError, apply_plan, plan_migrate
from svc_cli.manifest import load_manifest
from svc_cli.migrations import resolve_migrations


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests/fixtures/migrations/9.8.0_to_10.0.0"


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_manifest()

    def fixture(self, name: str, destination: Path) -> None:
        shutil.copytree(FIXTURES / name, destination, dirs_exist_ok=True)

    def test_migration_is_sequential_idempotent_and_preserves_consumer_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture("prepared", root)
            consumer_before = (root / "AGENTS.md").read_bytes()
            product_before = (root / "docs/10-prd/README.md").read_bytes()
            before = tree_bytes(root)

            plan = plan_migrate(root, self.manifest, "10.0.0", "9.8.0")
            self.assertFalse(plan.blockers)
            self.assertEqual(plan.migrations, ("9.8.0-to-10.0.0",))
            self.assertEqual(tree_bytes(root), before)
            result = apply_plan(root, plan, plan.digest, self.manifest)
            self.assertEqual(result["verification"], "passed")
            self.assertEqual((root / "AGENTS.md").read_bytes(), consumer_before)
            self.assertEqual((root / "docs/10-prd/README.md").read_bytes(), product_before)

            repeated = plan_migrate(root, self.manifest, "10.0.0")
            self.assertFalse(repeated.blockers)
            after = tree_bytes(root)
            self.assertEqual(apply_plan(root, repeated, repeated.digest, self.manifest)["status"], "noop")
            self.assertEqual(tree_bytes(root), after)

    def test_unprepared_v98_is_a_non_mutating_blocked_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture("blocked", root)
            before = tree_bytes(root)
            plan = plan_migrate(root, self.manifest, "10.0.0", "9.8.0")
            codes = {item["code"] for item in plan.blockers}
            self.assertIn("consumer-action-required", codes)
            self.assertIn("manual-cleanup-required", codes)
            with self.assertRaisesRegex(ProtocolError, "unresolved blockers"):
                apply_plan(root, plan, plan.digest, self.manifest)
            self.assertEqual(tree_bytes(root), before)

    def test_managed_drift_blocks_with_zero_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture("prepared", root)
            target = root / "docs/00-meta/implementation-taste.md"
            target.write_text("local managed fork\n", encoding="utf-8")
            before = tree_bytes(root)
            plan = plan_migrate(root, self.manifest, "10.0.0", "9.8.0")
            self.assertIn("managed-drift", {item["code"] for item in plan.blockers})
            self.assertEqual(tree_bytes(root), before)

    def test_staged_postcondition_failure_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture("prepared", root)
            before = tree_bytes(root)
            plan = plan_migrate(root, self.manifest, "10.0.0", "9.8.0")
            with patch("svc_cli.engine._verify_tree", side_effect=ProtocolError("postcondition-failed", "injected")):
                with self.assertRaisesRegex(ProtocolError, "injected"):
                    apply_plan(root, plan, plan.digest, self.manifest)
            self.assertEqual(tree_bytes(root), before)

    def test_commit_failure_rolls_back_complete_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture("prepared", root)
            before = tree_bytes(root)
            plan = plan_migrate(root, self.manifest, "10.0.0", "9.8.0")
            original = engine._commit_write
            calls = 0

            def fail_second(path: Path, content: bytes) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected commit failure")
                original(path, content)

            with patch("svc_cli.engine._commit_write", side_effect=fail_second):
                with self.assertRaises(ProtocolError) as raised:
                    apply_plan(root, plan, plan.digest, self.manifest)
            self.assertEqual(raised.exception.code, "apply-failed")
            self.assertEqual(raised.exception.details["rollback"], "succeeded")
            self.assertEqual(tree_bytes(root), before)

    def test_persistent_journal_recovers_after_interrupted_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture("prepared", root)
            before = tree_bytes(root)
            plan = plan_migrate(root, self.manifest, "10.0.0", "9.8.0")
            original = engine._commit_write
            calls = 0

            def fail_second(path: Path, content: bytes) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated process interruption")
                original(path, content)

            with (
                patch("svc_cli.engine._commit_write", side_effect=fail_second),
                patch("svc_cli.engine._rollback", return_value=False),
            ):
                with self.assertRaises(ProtocolError) as raised:
                    apply_plan(root, plan, plan.digest, self.manifest)
            self.assertEqual(raised.exception.details["rollback"], "recovery-required")
            self.assertTrue((root / ".svc/transactions" / plan.digest / "journal.json").is_file())

            recovery = engine.recover_pending_transaction(root)
            self.assertEqual(recovery["status"], "rolled-back")
            self.assertEqual(tree_bytes(root), before)
            self.assertTrue((root / "docs/00-meta").is_dir())
            self.assertFalse((root / ".svc").exists())

    def test_migration_registry_requires_adjacent_unique_steps(self) -> None:
        migrations = resolve_migrations("9.8.0", "10.0.0")
        self.assertEqual([item.migration_id for item in migrations], ["9.8.0-to-10.0.0"])
        with self.assertRaises(ValueError):
            resolve_migrations("9.7.0", "10.0.0")


if __name__ == "__main__":
    unittest.main()
