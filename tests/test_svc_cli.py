from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from svc_cli.cli import EXIT_CONFLICT, EXIT_OK, main
from svc_cli.engine import ProtocolError, apply_plan, inspect_status, plan_init
from svc_cli.manifest import load_manifest


class SvcCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_manifest()

    def test_init_dry_run_is_deterministic_and_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = io.StringIO()
            second = io.StringIO()
            with redirect_stdout(first):
                first_code = main(["init", str(root), "--json"])
            with redirect_stdout(second):
                second_code = main(["init", str(root), "--json"])
            self.assertEqual(first_code, EXIT_OK)
            self.assertEqual(second_code, EXIT_OK)
            self.assertEqual(first.getvalue(), second.getvalue())
            self.assertEqual(json.loads(first.getvalue())["summary"]["create"], 4)
            self.assertEqual(list(root.iterdir()), [])

    def test_generated_state_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as first_tmp, tempfile.TemporaryDirectory() as second_tmp:
            roots = [Path(first_tmp), Path(second_tmp)]
            states: list[bytes] = []
            for root in roots:
                plan = plan_init(root, self.manifest)
                apply_plan(root, plan, plan.digest, self.manifest)
                states.append((root / ".svc/state.json").read_bytes())
            self.assertEqual(states[0], states[1])

    def test_init_apply_preserves_existing_consumer_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            consumer = b"# Consumer instructions\n"
            (root / "AGENTS.md").write_bytes(consumer)
            plan = plan_init(root, self.manifest)
            result = apply_plan(root, plan, plan.digest, self.manifest)
            self.assertEqual(result["status"], "applied")
            self.assertEqual((root / "AGENTS.md").read_bytes(), consumer)
            self.assertTrue(inspect_status(root, self.manifest)["healthy"])

    def test_apply_rejects_stale_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = plan_init(root, self.manifest)
            (root / "AGENTS.md").write_text("changed after dry-run\n", encoding="utf-8")
            with self.assertRaisesRegex(ProtocolError, "changed after planning"):
                apply_plan(root, plan, plan.digest, self.manifest)
            self.assertFalse((root / ".svc/state.json").exists())

    def test_apply_revalidates_snapshot_after_staging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = plan_init(root, self.manifest)
            import svc_cli.engine as engine

            original = engine._verify_tree
            calls = 0

            def mutate_after_shadow(tree: Path, current_plan: object, manifest: object) -> None:
                nonlocal calls
                original(tree, current_plan, manifest)
                calls += 1
                if calls == 1:
                    (root / "AGENTS.md").write_text("concurrent change\n", encoding="utf-8")

            with patch("svc_cli.engine._verify_tree", side_effect=mutate_after_shadow):
                with self.assertRaisesRegex(ProtocolError, "changed during staging"):
                    apply_plan(root, plan, plan.digest, self.manifest)
            self.assertFalse((root / ".svc/state.json").exists())

    def test_status_rejects_tampered_generated_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = plan_init(root, self.manifest)
            apply_plan(root, plan, plan.digest, self.manifest)
            state_path = root / ".svc/state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["release_manifest_sha256"] = "0" * 64
            state_path.write_text(json.dumps(state), encoding="utf-8")
            status = inspect_status(root, self.manifest)
            self.assertFalse(status["healthy"])
            generated = next(item for item in status["artifacts"] if item["class"] == "generated")
            self.assertEqual(generated["status"], "stale")

    def test_cli_apply_requires_exact_plan_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stderr = io.StringIO()
            from contextlib import redirect_stderr

            with redirect_stderr(stderr):
                code = main(["init", str(root), "--apply", "0" * 64, "--json"])
            self.assertEqual(code, EXIT_CONFLICT)
            error = json.loads(stderr.getvalue())
            self.assertEqual(error["error"]["code"], "plan-digest-mismatch")


if __name__ == "__main__":
    unittest.main()
