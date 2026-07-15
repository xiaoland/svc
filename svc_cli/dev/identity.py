"""Workspace-safe identities and constrained dev configuration interpolation."""

from __future__ import annotations

import hashlib
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from ..errors import SvcError


_TOKEN = re.compile(r"\$\{([^}]+)\}")
_TOKEN_NAMES = frozenset(
    {
        "dev.instance",
        "dev.worktree.id",
        "dev.profile",
        "dev.target",
    }
)
_SCOPES = frozenset({"worktree", "repository", "host"})


def _digest(*parts: str, length: int = 20) -> str:
    payload = "\0".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:length]


@dataclass(frozen=True)
class WorkspaceIdentity:
    """Stable identity facts for one executable workspace.

    Git paths are inputs to hashing only.  No caller should treat a display path,
    branch name, or HEAD as process provenance.
    """

    root: Path
    namespace_id: str
    repository_kind: str
    repo_common_id: str
    worktree_id: str
    instance: str

    def as_dict(self) -> dict[str, str]:
        return {
            "root": str(self.root),
            "namespace_id": self.namespace_id,
            "repository_kind": self.repository_kind,
            "repo_common_id": self.repo_common_id,
            "worktree_id": self.worktree_id,
            "instance": self.instance,
        }


@dataclass(frozen=True)
class CapabilityIdentity:
    scope: str
    profile: str
    target: str
    endpoint_id: str
    coordination_subject: str
    lock_key: str
    runtime_key: str

    def as_dict(self) -> dict[str, str]:
        return {
            "scope": self.scope,
            "profile": self.profile,
            "target": self.target,
            "endpoint_id": self.endpoint_id,
            "coordination_subject": self.coordination_subject,
            "lock_key": self.lock_key,
            "runtime_key": self.runtime_key,
        }


def resolve_workspace_identity(root: Path, *, namespace: str | None = None) -> WorkspaceIdentity:
    """Resolve Git's common/private worktree facts, with a deterministic fallback."""

    workspace = _workspace_root(root)
    namespace_id = _namespace_id(namespace)
    git = _git_paths(workspace)
    if git is None:
        workspace_id = _digest("non-git-workspace", str(workspace))
        return WorkspaceIdentity(
            root=workspace,
            namespace_id=namespace_id,
            repository_kind="non-git",
            repo_common_id=workspace_id,
            worktree_id=workspace_id,
            instance=_digest("instance", namespace_id, workspace_id, length=16),
        )

    common_dir, git_dir = git
    common_id = _digest("git-common", str(common_dir))
    private_marker = "main" if git_dir == common_dir else _relative_private_marker(common_dir, git_dir)
    worktree_id = _digest("git-worktree", common_id, private_marker)
    return WorkspaceIdentity(
        root=workspace,
        namespace_id=namespace_id,
        repository_kind="git",
        repo_common_id=common_id,
        worktree_id=worktree_id,
        instance=_digest("instance", namespace_id, worktree_id, length=16),
    )


def resolve_capability_identity(
    workspace: WorkspaceIdentity,
    *,
    scope: str,
    profile: str,
    target: str,
    endpoint_identity: str,
    host_key: str | None = None,
) -> CapabilityIdentity:
    """Derive the only lock key an ensure operation is allowed to share."""

    if scope not in _SCOPES:
        raise SvcError("invalid-dev-scope", "Dev target scope is invalid.", {"scope": scope})
    if not profile or not target or not endpoint_identity:
        raise SvcError("invalid-dev-identity", "Dev identity fields must be non-empty.")
    if scope == "worktree":
        subject = workspace.worktree_id
    elif scope == "repository":
        subject = workspace.repo_common_id
    else:
        if not host_key:
            raise SvcError("missing-host-key", "Host-scoped targets require an explicit host_key.")
        subject = _digest("host-capability", workspace.namespace_id, host_key)

    endpoint_id = _digest("endpoint", endpoint_identity)
    material = (workspace.namespace_id, scope, subject, profile, target, endpoint_id)
    return CapabilityIdentity(
        scope=scope,
        profile=profile,
        target=target,
        endpoint_id=endpoint_id,
        coordination_subject=subject,
        lock_key=_digest("lock", *material, length=48),
        runtime_key=_digest("runtime", *material, length=48),
    )


def interpolate_dev_value(value: str, workspace: WorkspaceIdentity, *, profile: str, target: str) -> str:
    """Substitute the four non-secret tokens without invoking a shell."""

    values = {
        "dev.instance": workspace.instance,
        "dev.worktree.id": workspace.worktree_id,
        "dev.profile": profile,
        "dev.target": target,
    }

    def replace(match: re.Match[str]) -> str:
        token = match.group(1)
        if token not in _TOKEN_NAMES:
            raise SvcError(
                "unknown-dev-interpolation",
                "Only documented ${dev.*} interpolation tokens are allowed.",
                {"token": token},
            )
        return values[token]

    return _TOKEN.sub(replace, value)


def interpolate_dev_argv(
    argv: Sequence[str], workspace: WorkspaceIdentity, *, profile: str, target: str
) -> tuple[str, ...]:
    if not argv or any(not isinstance(item, str) or not item for item in argv):
        raise SvcError("invalid-dev-argv", "Dev command argv must be a non-empty string array.")
    return tuple(interpolate_dev_value(item, workspace, profile=profile, target=target) for item in argv)


def require_worktree_provenance(scope: str, endpoint_identity: str, workspace: WorkspaceIdentity) -> None:
    """Reject static healthy endpoints for application targets in linked worktrees."""

    if scope == "worktree" and workspace.instance not in endpoint_identity:
        raise SvcError(
            "worktree-provenance-unverified",
            "A worktree-scoped target probe must expose this worktree's resolved instance.",
            {"instance": workspace.instance},
        )


def _workspace_root(root: Path) -> Path:
    try:
        resolved = root.resolve(strict=True)
    except OSError as error:
        raise SvcError("workspace-not-directory", "Dev workspace does not exist.", {"root": str(root)}) from error
    if not resolved.is_dir():
        raise SvcError("workspace-not-directory", "Dev workspace is not a directory.", {"root": str(root)})
    return resolved


def _namespace_id(namespace: str | None) -> str:
    if namespace is not None:
        if not namespace or "\x00" in namespace:
            raise SvcError("invalid-dev-namespace", "Dev execution namespace must be a non-empty string.")
        material = namespace
    else:
        uid = str(os.getuid()) if hasattr(os, "getuid") else "unknown-user"
        material = "|".join((sys.platform, platform.node(), uid))
    return _digest("namespace", material)


def _git_paths(workspace: Path) -> tuple[Path, Path] | None:
    invocation = [
        "git",
        "-C",
        str(workspace),
        "rev-parse",
        "--is-bare-repository",
        "--path-format=absolute",
        "--git-common-dir",
        "--git-dir",
    ]
    completed = subprocess.run(invocation, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return None
    lines = completed.stdout.splitlines()
    if len(lines) != 3 or lines[0] != "false":
        if lines and lines[0] == "true":
            raise SvcError("bare-repository", "A bare Git repository is not a runnable dev workspace.")
        return None
    common_dir = Path(lines[1]).resolve()
    git_dir = Path(lines[2]).resolve()
    if not common_dir.is_dir() or not git_dir.is_dir():
        raise SvcError("invalid-git-worktree", "Git did not report usable worktree administration directories.")
    return common_dir, git_dir


def _relative_private_marker(common_dir: Path, git_dir: Path) -> str:
    try:
        return git_dir.relative_to(common_dir).as_posix()
    except ValueError:
        # Git normally places linked-worktree administration beneath common-dir.
        # Preserve isolation if an implementation uses another location.
        return f"external:{git_dir}"
