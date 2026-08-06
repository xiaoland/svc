"""Workspace-safe identities and constrained dev configuration interpolation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Mapping, Sequence

from ..errors import SvcError
from ..workspace import WorkspaceIdentity, resolve_workspace_identity


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
