from __future__ import annotations

import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

import svc_cli.plans as plans
from svc_cli.errors import SvcError
from svc_cli.project import (
    AGENTS_FILE,
    CODEX_SKILL_FILE,
    DOCS_INDEX_FILE,
    PROJECT_FILE,
    inspect_status,
    parse_project_state,
    plan_adopt,
    plan_init,
    render_project_state,
)
from svc_cli.integration import local_config_ignore_body
from svc_cli.plans import apply_local_plan


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class ProjectIntegrationTests(unittest.TestCase):
    def test_init_is_deterministic_plan_first_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = tree_bytes(root)
            first = plan_init(root)
            second = plan_init(root)
            self.assertEqual(first.as_dict(), second.as_dict())
            self.assertEqual(tree_bytes(root), before)
            self.assertEqual(
                {write.path for write in first.writes},
                {PROJECT_FILE, CODEX_SKILL_FILE, AGENTS_FILE, DOCS_INDEX_FILE, ".gitignore"},
            )

            result = apply_local_plan(first, first.digest)
            self.assertEqual(result["status"], "applied")
            self.assertEqual(parse_project_state((root / PROJECT_FILE).read_bytes()).svc_version, "10.0.0")
            self.assertTrue((root / CODEX_SKILL_FILE).is_file())
            self.assertTrue((root / DOCS_INDEX_FILE).is_file())
            self.assertIn(b"svc:begin local-config", (root / ".gitignore").read_bytes())
            self.assertFalse((root / "svc.local.json").exists())
            self.assertTrue(inspect_status(root)["healthy"])

            repeat = plan_init(root)
            self.assertEqual(repeat.status, "noop")
            snapshot = tree_bytes(root)
            self.assertEqual(apply_local_plan(repeat, repeat.digest)["status"], "noop")
            self.assertEqual(tree_bytes(root), snapshot)

    def test_init_preserves_unmarked_consumer_content_and_creates_docs_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents = b"# Consumer rules\n\nKeep this verbatim.\n"
            docs = b"# Existing docs\n\nKeep this too.\n"
            (root / AGENTS_FILE).write_bytes(agents)
            (root / "docs").mkdir()
            (root / DOCS_INDEX_FILE).write_bytes(docs)

            plan = plan_init(root)
            apply_local_plan(plan, plan.digest)
            self.assertTrue((root / AGENTS_FILE).read_bytes().startswith(agents))
            self.assertTrue((root / DOCS_INDEX_FILE).read_bytes().startswith(docs))
            self.assertIn(b"svc:begin navigation", (root / AGENTS_FILE).read_bytes())
            self.assertIn(b"svc:begin navigation", (root / DOCS_INDEX_FILE).read_bytes())

    def test_modified_skill_or_navigation_blocks_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initial = plan_init(root)
            apply_local_plan(initial, initial.digest)
            agents = root / AGENTS_FILE
            agents.write_text(agents.read_text(encoding="utf-8").replace("This project uses", "This project secretly uses"), encoding="utf-8")
            before = tree_bytes(root)

            plan = plan_init(root)
            self.assertIn("generated-guidance-drift", {blocker.code for blocker in plan.blockers})
            with self.assertRaisesRegex(SvcError, "unresolved blockers"):
                apply_local_plan(plan, plan.digest)
            self.assertEqual(tree_bytes(root), before)

    def test_unowned_existing_skill_is_never_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = root / CODEX_SKILL_FILE
            skill.parent.mkdir(parents=True)
            skill.write_text("# My own skill\n", encoding="utf-8")
            before = tree_bytes(root)
            plan = plan_init(root)
            self.assertIn("generated-skill-drift", {blocker.code for blocker in plan.blockers})
            with self.assertRaises(SvcError):
                apply_local_plan(plan, plan.digest)
            self.assertEqual(tree_bytes(root), before)

    def test_stale_plan_and_commit_or_postcondition_failure_leave_no_partial_project_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stale = plan_init(root)
            (root / AGENTS_FILE).write_text("concurrent consumer change\n", encoding="utf-8")
            with self.assertRaisesRegex(SvcError, "changed after planning"):
                apply_local_plan(stale, stale.digest)
            self.assertFalse((root / PROJECT_FILE).exists())

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = plan_init(root)
            before = tree_bytes(root)
            original = plans._commit_write
            calls = 0

            def fail_second(path: Path, content: bytes) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected write failure")
                original(path, content)

            with patch("svc_cli.plans._commit_write", side_effect=fail_second):
                with self.assertRaises(SvcError) as raised:
                    apply_local_plan(plan, plan.digest)
            self.assertEqual(raised.exception.code, "apply-failed")
            self.assertEqual(raised.exception.details["rollback"], "succeeded")
            self.assertEqual(tree_bytes(root), before)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = plan_init(root)
            before = tree_bytes(root)
            with patch(
                "svc_cli.plans._verify_postconditions",
                side_effect=SvcError("postcondition-failed", "injected postcondition failure"),
            ):
                with self.assertRaises(SvcError) as raised:
                    apply_local_plan(plan, plan.digest)
            self.assertEqual(raised.exception.code, "postcondition-failed")
            self.assertEqual(raised.exception.details["rollback"], "succeeded")
            self.assertEqual(tree_bytes(root), before)

    def test_rollback_does_not_overwrite_an_intervening_consumer_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = plan_init(root)
            original = plans._commit_write
            calls = 0

            def fail_after_consumer_change(path: Path, content: bytes) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    (root / PROJECT_FILE).write_text("consumer change\n", encoding="utf-8")
                    raise OSError("injected write failure")
                original(path, content)

            with patch("svc_cli.plans._commit_write", side_effect=fail_after_consumer_change):
                with self.assertRaises(SvcError) as raised:
                    apply_local_plan(plan, plan.digest)
            self.assertEqual(raised.exception.code, "apply-failed")
            self.assertEqual(raised.exception.details["rollback"], "conflicted")
            self.assertEqual((root / PROJECT_FILE).read_text(encoding="utf-8"), "consumer change\n")

    def test_status_distinguishes_adoption_and_adopt_updates_only_project_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initial = plan_init(root)
            apply_local_plan(initial, initial.digest)
            (root / PROJECT_FILE).write_bytes(render_project_state("9.9.9"))
            status = inspect_status(root)
            self.assertEqual(status["project"]["status"], "adoption-pending")
            self.assertFalse(status["healthy"])

            adopt = plan_adopt(root, "10.0.0")
            self.assertEqual([write.path for write in adopt.writes], [PROJECT_FILE])
            apply_local_plan(adopt, adopt.digest)
            self.assertTrue(inspect_status(root)["healthy"])

            with patch("svc_cli.project.installed_distribution_version", return_value="10.0.1"):
                mismatch = inspect_status(root)
            self.assertEqual(mismatch["runtime"]["status"], "mismatch")
            self.assertFalse(mismatch["healthy"])

    def test_init_manages_only_a_clean_local_config_ignore_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = b"node_modules\r\nsvc.local.json\r\n"
            (root / ".gitignore").write_bytes(original)
            plan = plan_init(root)
            apply_local_plan(plan, plan.digest)
            ignored = (root / ".gitignore").read_bytes()
            self.assertTrue(ignored.startswith(original))
            self.assertIn(local_config_ignore_body().encode(), ignored.replace(b"\r\n", b"\n"))
            self.assertIn(b"\r\n", ignored)

            drifted = ignored.replace(
                b"svc.local.json\r\n# svc:end local-config",
                b"private-svc.local.json\r\n# svc:end local-config",
            )
            (root / ".gitignore").write_bytes(drifted)
            blocked = plan_init(root)
            self.assertIn("managed-ignore-drift", {item.code for item in blocked.blockers})

    def test_schema_v1_blocks_writes_and_v2_adopt_preserves_consumer_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = b'{\n  "schema_version": 1,\n  "svc_version": "10.0.0"\n}\n'
            (root / PROJECT_FILE).write_bytes(legacy)
            blocked = plan_init(root)
            self.assertIn("schema-v1-write-blocked", {item.code for item in blocked.blockers})
            self.assertEqual((root / PROJECT_FILE).read_bytes(), legacy)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current = (
                b'{\n'
                b'  "schema_version": 2,\n'
                b'  "svc_version" : "9.9.9",\n'
                b'  "dev": {"profile":"local","profiles":{"local":{"targets":{"app":{'
                b'"probe":{"kind":"exec","argv":["check"]},"provision":{"kind":"manual"}}}}}}\n'
                b'}\n'
            )
            (root / PROJECT_FILE).write_bytes(current)
            adopt = plan_adopt(root, "10.0.0")
            self.assertEqual([write.path for write in adopt.writes], [PROJECT_FILE])
            updated = adopt.writes[0].content
            self.assertEqual(updated.replace(b'"10.0.0"', b'"9.9.9"'), current)
            apply_local_plan(adopt, adopt.digest)
            self.assertEqual((root / PROJECT_FILE).read_bytes(), updated)

    def test_invalid_local_overlay_blocks_init_without_rewriting_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initial = plan_init(root)
            apply_local_plan(initial, initial.digest)
            local = root / "svc.local.json"
            local.write_text('{"schema_version": 2}\n', encoding="utf-8")
            before = local.read_bytes()
            blocked = plan_init(root)
            self.assertIn("invalid-project-configuration", {item.code for item in blocked.blockers})
            with self.assertRaises(SvcError):
                apply_local_plan(blocked, blocked.digest)
            self.assertEqual(local.read_bytes(), before)

    def test_apply_preserves_existing_consumer_file_mode_and_rejects_mode_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents = root / AGENTS_FILE
            agents.write_text("# Consumer\n", encoding="utf-8")
            os.chmod(agents, 0o640)
            plan = plan_init(root)
            os.chmod(agents, 0o600)
            with self.assertRaisesRegex(SvcError, "mode changed"):
                apply_local_plan(plan, plan.digest)
            os.chmod(agents, 0o640)
            apply_local_plan(plan, plan.digest)
            self.assertEqual(agents.stat().st_mode & 0o777, 0o640)


if __name__ == "__main__":
    unittest.main()
