"""Resolve project entries without observing or inheriting their owner's actions."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from ..config import (
    ConfigError,
    ExecAction,
    ResourceConfig,
    declaration_digest_value,
    load_config,
)
from ..errors import Failure, SvcError
from ..workspace import WorkspaceIdentity, resolve_workspace_identity
from .identity import (
    interpolate_dev_argv,
    interpolate_dev_value,
    resolve_capability_identity,
)
from .readiness import resolve_dev_cwd
from .models import (
    ActionDescription,
    Coordination,
    ResourceView,
    ObservationDescription,
)


@dataclass(frozen=True)
class ResolvedAction:
    argv: tuple[str, ...]
    cwd: Path
    env: dict[str, str]
    digest: str


@dataclass(frozen=True)
class Resource:
    key: str
    workspace: WorkspaceIdentity
    config: ResourceConfig
    entry_id: str
    digest: str
    coordination: Coordination | None
    error: Failure | None
    actions: dict[str, ResolvedAction]

    def view(self) -> ResourceView:
        descriptions = []
        for key, action in self.config.actions.items():
            descriptions.append(
                ActionDescription(
                    key=key,
                    kind=action.kind,
                    intent=action.intent,
                    traits=tuple(action.traits),
                    effect_scope=action.effect_scope,
                    data_effect=action.data_effect,
                    completion=action.completion
                    if isinstance(action, ExecAction)
                    else None,
                    interruption=action.interruption
                    if isinstance(action, ExecAction)
                    else None,
                    convergent=action.convergent
                    if isinstance(action, ExecAction)
                    else False,
                    steps=() if isinstance(action, ExecAction) else tuple(action.steps),
                )
            )
        return ResourceView(
            resource=self.key,
            label=self.config.label or self.key,
            entry_id=self.entry_id,
            source=str(self.workspace.root),
            declaration_digest=self.digest,
            coordination=self.coordination,
            controller=self.config.controller,
            access=tuple(
                interpolate_dev_value(x, self.workspace, target=self.key)
                for x in self.config.access
            ),
            relations=tuple(self.config.relations),
            actions=tuple(descriptions),
            facets=tuple(
                ObservationDescription(
                    key=key,
                    label=facet.label or key,
                    automatic=facet.automatic,
                    purpose=facet.purpose,
                    provider=facet.probe.kind,
                )
                for key, facet in self.config.observations.items()
            ),
            error=self.error,
        )


def validate_access_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("operation URL must be an HTTP(S) address without credentials")


def declarations(repo: Path) -> tuple[WorkspaceIdentity, dict[str, ResourceConfig]]:
    workspace = resolve_workspace_identity(repo)
    try:
        dev = load_config(workspace.root).effective.dev
    except ConfigError as error:
        raise SvcError("invalid-dev-configuration", str(error)) from error
    return workspace, dev.resources if dev else {}


def resolve_resource(repo: Path, key: str) -> Resource:
    workspace, configs = declarations(repo)
    if key not in configs:
        raise SvcError("resource-not-declared", "资源未声明。", {"resource": key})
    return resolve_entry(workspace, key, configs[key])


def resolve_entry(
    workspace: WorkspaceIdentity, key: str, config: ResourceConfig
) -> Resource:
    entry_id = hashlib.sha256(
        f"{workspace.namespace_id}\0{workspace.instance}\0{key}".encode()
    ).hexdigest()
    coordination = None
    failure = None
    try:
        owner_workspace, owner_key, owner_config = workspace, key, config
        if config.owner:
            owner_path = (workspace.root / config.owner.repo).resolve()
            owner_workspace, owner_configs = declarations(owner_path)
            owner_key = config.owner.resource
            if owner_key not in owner_configs:
                raise SvcError("owner-not-declared", "共享 owner 的资源不存在。")
            owner_config = owner_configs[owner_key]
            if owner_config.owner:
                raise SvcError(
                    "owner-reference-chain",
                    "共享 owner 必须是直接资源，不能形成引用链或环。",
                )
        identity = resolve_capability_identity(
            owner_workspace,
            scope=owner_config.scope,
            target=owner_key,
            endpoint_identity="resource:" + owner_key,
            host_key=owner_config.host_key,
        )
        coordination = Coordination(
            coordination_id=identity.capability_id,
            scope=identity.scope,
            scope_id=identity.scope_id,
            workspace_instance=owner_workspace.instance,
            owner_repo=str(owner_workspace.root),
            owner_resource=owner_key,
        )
    except SvcError as error:
        failure = error.snapshot()
    actions = {}
    for name, action in config.actions.items():
        if not isinstance(action, ExecAction):
            continue
        env = dict(os.environ)
        env.update(
            {
                k: interpolate_dev_value(v, workspace, target=key)
                for k, v in action.env.items()
            }
        )
        env.update(
            SVC_DEV_TARGET=key,
            SVC_DEV_INSTANCE=workspace.instance,
            SVC_DEV_WORKTREE_ID=workspace.worktree_id,
        )
        env.pop("SVC_DEV_RESULT_FILE", None)
        argv = interpolate_dev_argv(action.argv, workspace, target=key)
        cwd = resolve_dev_cwd(workspace.root, action.cwd, workspace, key)
        for volatile in ("_", "SHLVL", "PWD", "OLDPWD"):
            env.pop(volatile, None)
        digest = declaration_digest_value(
            {"argv": argv, "cwd": str(cwd), "environment": env}
        )
        actions[name] = ResolvedAction(argv, cwd, env, digest)
    digest = declaration_digest_value(
        {
            "entry": entry_id,
            "declaration": config.model_dump(mode="json", exclude_none=True),
            "coordination": coordination.model_dump(mode="json")
            if coordination
            else None,
            "actions": {name: a.digest for name, a in actions.items()},
        }
    )
    return Resource(
        key, workspace, config, entry_id, digest, coordination, failure, actions
    )
