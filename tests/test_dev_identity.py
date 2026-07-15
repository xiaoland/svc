from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from svc_cli.dev.identity import (
    interpolate_dev_argv,
    interpolate_dev_value,
    require_worktree_provenance,
    resolve_capability_identity,
    resolve_workspace_identity,
)
from svc_cli.errors import SvcError


class DevIdentityTests(unittest.TestCase):
    def git(self, root: Path, *arguments: str) -> None:
        subprocess.run(("git", "-C", str(root), *arguments), check=True, capture_output=True, text=True)

    def test_linked_worktrees_are_distinct_but_share_common_repository_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "main"
            linked = Path(tmp) / "linked"
            root.mkdir()
            self.git(root, "init")
            self.git(root, "config", "user.email", "test@example.com")
            self.git(root, "config", "user.name", "Test")
            (root / "README.md").write_text("fixture\n", encoding="utf-8")
            self.git(root, "add", "README.md")
            self.git(root, "commit", "-m", "fixture")
            self.git(root, "worktree", "add", "-b", "linked", str(linked))

            main_identity = resolve_workspace_identity(root, namespace="fixture")
            linked_identity = resolve_workspace_identity(linked, namespace="fixture")
            self.assertEqual(main_identity.repository_kind, "git")
            self.assertEqual(main_identity.repo_common_id, linked_identity.repo_common_id)
            self.assertNotEqual(main_identity.worktree_id, linked_identity.worktree_id)
            self.assertNotEqual(main_identity.instance, linked_identity.instance)

            moved = Path(tmp) / "linked-moved"
            self.git(root, "worktree", "move", str(linked), str(moved))
            moved_identity = resolve_workspace_identity(moved, namespace="fixture")
            self.assertEqual(linked_identity.worktree_id, moved_identity.worktree_id)

    def test_non_git_fallback_and_scope_specific_lock_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = resolve_workspace_identity(Path(tmp), namespace="fixture")
            self.assertEqual(workspace.repository_kind, "non-git")
            worktree = resolve_capability_identity(
                workspace,
                scope="worktree",
                profile="local",
                target="app",
                endpoint_identity=f"http://app-{workspace.instance}.localhost/health",
            )
            repository = resolve_capability_identity(
                workspace,
                scope="repository",
                profile="local",
                target="app",
                endpoint_identity="tcp://127.0.0.1:5432",
            )
            self.assertNotEqual(worktree.lock_key, repository.lock_key)
            with self.assertRaisesRegex(SvcError, "host_key"):
                resolve_capability_identity(
                    workspace,
                    scope="host",
                    profile="local",
                    target="app",
                    endpoint_identity="tcp://127.0.0.1:5432",
                )

    def test_interpolation_is_constrained_and_provenance_requires_resolved_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = resolve_workspace_identity(Path(tmp), namespace="fixture")
            value = interpolate_dev_value(
                "http://${dev.target}-${dev.instance}.localhost/${dev.profile}",
                workspace,
                profile="worktree",
                target="frontend",
            )
            self.assertEqual(value, f"http://frontend-{workspace.instance}.localhost/worktree")
            self.assertEqual(
                interpolate_dev_argv(("tool", "--id=${dev.worktree.id}"), workspace, profile="worktree", target="frontend"),
                ("tool", f"--id={workspace.worktree_id}"),
            )
            require_worktree_provenance("worktree", value, workspace)
            with self.assertRaisesRegex(SvcError, "provenance"):
                require_worktree_provenance("worktree", "http://static.localhost/health", workspace)
            with self.assertRaisesRegex(SvcError, "interpolation"):
                interpolate_dev_value("${HOME}", workspace, profile="worktree", target="frontend")


if __name__ == "__main__":
    unittest.main()
