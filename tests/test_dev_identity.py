from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest

from svc_cli.dev.identity import (
    interpolate_dev_argv,
    interpolate_dev_value,
    require_worktree_provenance,
    resolve_capability_identity,
    resolve_workspace_identity,
)
from svc_cli.errors import SvcError


def git(root: Path, *arguments: str) -> None:
    subprocess.run(("git", "-C", str(root), *arguments), check=True, capture_output=True, text=True)


def test_linked_worktrees_are_distinct_but_share_common_repository_identity() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "main"
        linked = Path(tmp) / "linked"
        root.mkdir()
        git(root, "init")
        git(root, "config", "user.email", "test@example.com")
        git(root, "config", "user.name", "Test")
        (root / "README.md").write_text("fixture\n", encoding="utf-8")
        git(root, "add", "README.md")
        git(root, "commit", "-m", "fixture")
        git(root, "worktree", "add", "-b", "linked", str(linked))

        main_identity = resolve_workspace_identity(root, namespace="fixture")
        linked_identity = resolve_workspace_identity(linked, namespace="fixture")
        assert main_identity.repository_kind == "git"
        assert main_identity.repo_common_id == linked_identity.repo_common_id
        assert main_identity.worktree_id != linked_identity.worktree_id
        assert main_identity.instance != linked_identity.instance

        moved = Path(tmp) / "linked-moved"
        git(root, "worktree", "move", str(linked), str(moved))
        moved_identity = resolve_workspace_identity(moved, namespace="fixture")
        assert linked_identity.worktree_id == moved_identity.worktree_id


def test_non_git_fallback_and_scope_specific_lock_identity() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace = resolve_workspace_identity(Path(tmp), namespace="fixture")
        assert workspace.repository_kind == "non-git"
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
        assert worktree.lock_key != repository.lock_key
        with pytest.raises(SvcError, match="host_key"):
            resolve_capability_identity(
                workspace,
                scope="host",
                profile="local",
                target="app",
                endpoint_identity="tcp://127.0.0.1:5432",
            )


def test_interpolation_is_constrained_and_provenance_requires_resolved_instance() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace = resolve_workspace_identity(Path(tmp), namespace="fixture")
        value = interpolate_dev_value(
            "http://${dev.target}-${dev.instance}.localhost/${dev.profile}",
            workspace,
            profile="worktree",
            target="frontend",
        )
        assert value == f"http://frontend-{workspace.instance}.localhost/worktree"
        assert interpolate_dev_argv(("tool", "--id=${dev.worktree.id}"), workspace, profile="worktree", target="frontend") == (
            "tool",
            f"--id={workspace.worktree_id}",
        )
        require_worktree_provenance("worktree", value, workspace)
        with pytest.raises(SvcError, match="provenance"):
            require_worktree_provenance("worktree", "http://static.localhost/health", workspace)
        with pytest.raises(SvcError, match="interpolation"):
            interpolate_dev_value("${HOME}", workspace, profile="worktree", target="frontend")
