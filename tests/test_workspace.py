from __future__ import annotations

import subprocess
from pathlib import Path

from svc_cli.dev.identity import resolve_workspace_identity as resolve_dev_workspace_identity
from svc_cli.workspace import resolve_workspace_identity


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(("git", "-C", str(root), *arguments), check=True, capture_output=True, text=True)


def test_workspace_owner_preserves_non_git_identity_and_dev_projection(tmp_path: Path) -> None:
    identity = resolve_workspace_identity(tmp_path, namespace="fixture")
    assert identity.repository_kind == "non-git"
    assert identity == resolve_dev_workspace_identity(tmp_path, namespace="fixture")


def test_workspace_owner_distinguishes_linked_worktrees(tmp_path: Path) -> None:
    root = tmp_path / "main"
    linked = tmp_path / "linked"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "fixture")
    _git(root, "worktree", "add", "-b", "linked", str(linked))

    main = resolve_workspace_identity(root, namespace="fixture")
    other = resolve_workspace_identity(linked, namespace="fixture")
    assert main.repo_common_id == other.repo_common_id
    assert main.worktree_id != other.worktree_id
