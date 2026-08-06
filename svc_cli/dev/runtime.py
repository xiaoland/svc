"""Dev capability coordination over neutral private process attempts."""

from __future__ import annotations

import os
import signal
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from filelock import BaseFileLock, Timeout

from .._execution import (
    ACTIVE_STATES,
    ExecutionRecord,
    ExecutionStore,
    LaunchSpec,
    OwnedExecution,
    mark_owner_lost,
    reconcile_owner_loss,
    release_owned,
    start_isolated,
    terminate_owned,
    wait_owned,
)
from ..config import ConfigError, ExecProvision, ManualProvision, TargetConfig, load_config
from ..errors import SvcError
from ..workspace import WorkspaceIdentity, resolve_workspace_identity
from .identity import (
    CapabilityIdentity,
    interpolate_dev_argv,
    interpolate_dev_value,
    resolve_capability_identity,
)
from .readiness import (
    ProbeObservation,
    probe_exec,
    probe_http,
    probe_target,
    probe_tcp,
    resolve_dev_cwd,
)


def ensure_target(
    repo: Path,
    target_name: str,
    *,
    namespace: str | None = None,
    store: ExecutionStore | None = None,
) -> dict[str, object]:
    """Ensure one capability without taking over an unowned process."""

    try:
        resolved = load_config(repo)
    except ConfigError as error:
        raise SvcError(
            "invalid-project-configuration",
            "Cannot load declared dev configuration.",
            {"reason": str(error)},
        ) from error
    if resolved.effective.dev is None:
        raise SvcError("dev-not-configured", "This project has no declared dev configuration.")
    profile = resolved.effective.dev.profile
    profile_config = resolved.effective.dev.profiles[profile]
    if target_name not in profile_config.targets:
        raise SvcError(
            "unknown-dev-target",
            "The selected dev profile has no such target.",
            {"target": target_name, "profile": profile},
        )
    target = profile_config.targets[target_name]
    workspace = resolve_workspace_identity(repo, namespace=namespace)
    initial = probe_target(target, workspace, profile=profile, target_name=target_name)
    identity = resolve_capability_identity(
        workspace,
        scope=target.scope,
        profile=profile,
        target=target_name,
        endpoint_identity=initial.endpoint_identity,
        host_key=target.host_key,
    )
    base = _result_base(resolved.effective_digest, workspace, identity, initial)
    if initial.healthy:
        return {**base, "status": "reused"}
    if initial.responded:
        raise _occupied_error(base)
    if isinstance(target.provision, ManualProvision):
        raise SvcError(
            "manual-action-required",
            "This target requires the consumer-declared manual provisioning action.",
            {**base, "status": "manual-action-required", "access": target.access},
        )

    deadline = time.monotonic() + target.readiness_timeout
    authority = store or ExecutionStore()
    lock = authority.slot_lock("dev", identity.lock_key)
    pointer_before = authority.read_slot("dev", identity.lock_key)
    pointer_before_active = (
        pointer_before is not None and authority.read(pointer_before).state in ACTIVE_STATES
    )
    try:
        lock.acquire(timeout=0)
    except Timeout:
        return _join_dev_attempt(
            authority,
            lock,
            pointer_before,
            pointer_before_active,
            target,
            workspace,
            profile,
            target_name,
            identity,
            resolved.effective_digest,
            deadline,
        )
    try:
        return _ensure_under_lock(
            authority,
            target,
            workspace,
            profile,
            target_name,
            identity,
            resolved.effective_digest,
            deadline,
        )
    finally:
        lock.release()


def inspect_dev_identity(repo: Path, *, namespace: str | None = None) -> dict[str, object]:
    workspace = resolve_workspace_identity(repo, namespace=namespace)
    return {"schema_version": 1, "command": "dev identity", "workspace": workspace.as_dict()}


def inspect_dev_status(
    repo: Path,
    target_name: str | None = None,
    *,
    namespace: str | None = None,
) -> dict[str, object]:
    try:
        resolved = load_config(repo)
    except ConfigError as error:
        return {
            "schema_version": 1,
            "command": "dev status",
            "healthy": False,
            "status": "invalid-configuration",
            "reason": str(error),
        }
    if resolved.effective.dev is None:
        return {"schema_version": 1, "command": "dev status", "healthy": False, "status": "not-configured"}
    profile = resolved.effective.dev.profile
    workspace = resolve_workspace_identity(repo, namespace=namespace)
    targets = resolved.effective.dev.profiles[profile].targets
    names = (target_name,) if target_name is not None else tuple(sorted(targets))
    entries: list[dict[str, object]] = []
    for name in names:
        target = targets.get(name)
        if target is None:
            raise SvcError(
                "unknown-dev-target",
                "The selected dev profile has no such target.",
                {"target": name, "profile": profile},
            )
        try:
            observed = probe_target(target, workspace, profile=profile, target_name=name)
            identity = resolve_capability_identity(
                workspace,
                scope=target.scope,
                profile=profile,
                target=name,
                endpoint_identity=observed.endpoint_identity,
                host_key=target.host_key,
            )
            entries.append({"target": name, "capability": identity.as_dict(), "probe": observed.as_dict()})
        except SvcError as error:
            entries.append({"target": name, "error": error.as_dict()["error"]})
    healthy = bool(entries) and all(_entry_is_healthy(entry) for entry in entries)
    return {
        "schema_version": 1,
        "command": "dev status",
        "status": "healthy" if healthy else "action-required",
        "healthy": healthy,
        "effective_declaration_digest": resolved.effective_digest,
        "profile": profile,
        "workspace": workspace.as_dict(),
        "targets": entries,
    }


def _ensure_under_lock(
    store: ExecutionStore,
    target: TargetConfig,
    workspace: WorkspaceIdentity,
    profile: str,
    target_name: str,
    identity: CapabilityIdentity,
    effective_digest: str,
    deadline: float,
) -> dict[str, object]:
    current_id = store.read_slot("dev", identity.lock_key)
    if current_id is not None:
        current = store.read(current_id)
        if current.state in ACTIVE_STATES:
            lost = mark_owner_lost(store, current)
            return _await_capability_after_attempt(
                target,
                workspace,
                profile,
                target_name,
                identity,
                effective_digest,
                deadline,
                lost,
            )

    observed = probe_target(
        target,
        workspace,
        profile=profile,
        target_name=target_name,
        timeout=_remaining(deadline),
    )
    base = _result_base(effective_digest, workspace, identity, observed)
    if observed.healthy:
        return {**base, "status": "reused"}
    if observed.responded:
        raise _occupied_error(base)

    provision = target.provision
    if isinstance(provision, ManualProvision):
        raise AssertionError("manual provisioning is handled before coordination")
    launched = _provision(
        store,
        provision,
        workspace,
        profile,
        target_name,
        identity,
        effective_digest,
        timeout=_remaining(deadline),
    )
    if launched is None:
        return _wait_for_external_readiness(target, workspace, profile, target_name, deadline, base)
    with _cleanup_on_interrupt(store, launched, base):
        return _wait_for_owned_readiness(
            store,
            target,
            workspace,
            profile,
            target_name,
            deadline,
            base,
            launched,
        )


def _join_dev_attempt(
    store: ExecutionStore,
    lock: BaseFileLock,
    pointer_before: str | None,
    pointer_before_active: bool,
    target: TargetConfig,
    workspace: WorkspaceIdentity,
    profile: str,
    target_name: str,
    identity: CapabilityIdentity,
    effective_digest: str,
    deadline: float,
) -> dict[str, object]:
    while _remaining(deadline) > 0:
        current_id = store.read_slot("dev", identity.lock_key)
        if current_id is not None:
            current = store.read(current_id)
            if current.state in ACTIVE_STATES or current_id != pointer_before or pointer_before_active:
                return _await_capability_after_attempt(
                    target,
                    workspace,
                    profile,
                    target_name,
                    identity,
                    effective_digest,
                    deadline,
                    current,
                    store=store,
                )
        try:
            lock.acquire(timeout=0)
        except Timeout:
            time.sleep(min(0.02, _remaining(deadline)))
            continue
        try:
            after = store.read_slot("dev", identity.lock_key)
            if after is not None and after != pointer_before:
                record = store.read(after)
                if record.state in ACTIVE_STATES:
                    record = mark_owner_lost(store, record)
                return _await_capability_after_attempt(
                    target,
                    workspace,
                    profile,
                    target_name,
                    identity,
                    effective_digest,
                    deadline,
                    record,
                )
            if pointer_before is not None and pointer_before_active:
                previous = store.read(pointer_before)
                if previous.state in ACTIVE_STATES:
                    previous = mark_owner_lost(store, previous)
                return _await_capability_after_attempt(
                    target,
                    workspace,
                    profile,
                    target_name,
                    identity,
                    effective_digest,
                    deadline,
                    previous,
                )
            return _ensure_under_lock(
                store,
                target,
                workspace,
                profile,
                target_name,
                identity,
                effective_digest,
                deadline,
            )
        finally:
            lock.release()
    base = _result_base(effective_digest, workspace, identity, probe_target(target, workspace, profile=profile, target_name=target_name, timeout=0))
    raise SvcError("dev-lock-timeout", "Timed out waiting for another ensure operation.", {**base, "status": "lock-timeout"})


def _provision(
    store: ExecutionStore,
    provision: ExecProvision,
    workspace: WorkspaceIdentity,
    profile: str,
    target_name: str,
    identity: CapabilityIdentity,
    effective_digest: str,
    *,
    timeout: float,
) -> OwnedExecution | None:
    argv = interpolate_dev_argv(provision.argv, workspace, profile=profile, target=target_name)
    cwd = resolve_dev_cwd(workspace.root, provision.cwd, workspace, profile, target_name)
    environment = os.environ.copy()
    environment.update(
        {
            "SVC_DEV_INSTANCE": workspace.instance,
            "SVC_DEV_WORKTREE_ID": workspace.worktree_id,
            "SVC_DEV_PROFILE": profile,
            "SVC_DEV_TARGET": target_name,
        }
    )
    environment.update(
        {
            key: interpolate_dev_value(value, workspace, profile=profile, target=target_name)
            for key, value in provision.env.items()
        }
    )
    published = store.publish(
        domain="dev",
        entry=target_name,
        workspace_id=workspace.instance,
        effective_entry_digest=effective_digest,
        slot_key=identity.lock_key,
        argv=argv,
        cwd=cwd,
        capture="merged",
    )
    store.write_slot("dev", identity.lock_key, published.record.execution_id)
    started = start_isolated(store, published, LaunchSpec(argv, cwd, environment))
    log_path = str(store.log_path(started if isinstance(started, ExecutionRecord) else started.record, "merged"))
    if isinstance(started, ExecutionRecord):
        raise SvcError(
            "provision-start-failed",
            "The declared run command could not start.",
            {"log_path": log_path, "reason": started.failure_reason or "unknown"},
        )
    if provision.mode == "run":
        return started
    settled = wait_owned(store, started, timeout=max(0.01, timeout))
    if settled is None:
        terminated = terminate_owned(store, started)
        raise SvcError(
            "activation-timeout",
            "The declared activation command did not finish before the readiness deadline.",
            {"log_path": log_path, "cleanup": "completed" if terminated.state == "interrupted" else "unknown"},
        )
    if settled.state != "exited" or settled.exit_code != 0:
        raise SvcError(
            "activation-failed",
            "The declared activation command failed.",
            {"log_path": log_path, "returncode": settled.exit_code},
        )
    return None


def _wait_for_external_readiness(
    target: TargetConfig,
    workspace: WorkspaceIdentity,
    profile: str,
    target_name: str,
    deadline: float,
    base: dict[str, object],
) -> dict[str, object]:
    while _remaining(deadline) > 0:
        observed = probe_target(
            target,
            workspace,
            profile=profile,
            target_name=target_name,
            timeout=_remaining(deadline),
        )
        if observed.healthy:
            return {**base, "probe": observed.as_dict(), "status": "started"}
        time.sleep(min(target.poll_interval, _remaining(deadline)))
    raise SvcError(
        "readiness-timeout",
        "Activated target did not become ready before its deadline.",
        {**base, "status": "readiness-timeout"},
    )


def _wait_for_owned_readiness(
    store: ExecutionStore,
    target: TargetConfig,
    workspace: WorkspaceIdentity,
    profile: str,
    target_name: str,
    deadline: float,
    base: dict[str, object],
    owned: OwnedExecution,
) -> dict[str, object]:
    log_path = str(store.log_path(owned.record, "merged"))
    while _remaining(deadline) > 0:
        if owned.process.poll() is not None:
            settled = wait_owned(store, owned)
            raise SvcError(
                "provision-exited",
                "The SVC-started provisioner exited before readiness.",
                {
                    **base,
                    "status": "child-exit",
                    "log_path": log_path,
                    "returncode": settled.exit_code if settled is not None else owned.process.returncode,
                    "cleanup": "completed",
                },
            )
        observed = probe_target(
            target,
            workspace,
            profile=profile,
            target_name=target_name,
            timeout=_remaining(deadline),
        )
        if observed.healthy:
            try:
                release_owned(store, owned)
            except SvcError:
                try:
                    terminate_owned(store, owned)
                except SvcError:
                    pass
                raise
            return {
                **base,
                "probe": observed.as_dict(),
                "status": "started",
                "log_path": log_path,
                "process_id": owned.process.pid,
            }
        time.sleep(min(target.poll_interval, _remaining(deadline)))
    terminated = terminate_owned(store, owned)
    raise SvcError(
        "readiness-timeout",
        "SVC-started provisioner did not become ready before its deadline.",
        {
            **base,
            "status": "readiness-timeout",
            "log_path": log_path,
            "cleanup": "completed" if terminated.state == "interrupted" else "unknown",
        },
    )


def _await_capability_after_attempt(
    target: TargetConfig,
    workspace: WorkspaceIdentity,
    profile: str,
    target_name: str,
    identity: CapabilityIdentity,
    effective_digest: str,
    deadline: float,
    record: ExecutionRecord,
    *,
    store: ExecutionStore | None = None,
) -> dict[str, object]:
    authority = store
    while record.state in ACTIVE_STATES and _remaining(deadline) > 0:
        time.sleep(min(0.02, _remaining(deadline)))
        if authority is None:
            break
        record = reconcile_owner_loss(authority, authority.read(record.execution_id))
    while _remaining(deadline) > 0:
        observed = probe_target(
            target,
            workspace,
            profile=profile,
            target_name=target_name,
            timeout=_remaining(deadline),
        )
        base = _result_base(effective_digest, workspace, identity, observed)
        if observed.healthy:
            return {**base, "status": "reused"}
        if observed.responded:
            raise _occupied_error(base)
        if record.state not in {"released", "owner-lost", "exited"}:
            raise _attempt_error(record, base, authority)
        time.sleep(min(target.poll_interval, _remaining(deadline)))
    observed = probe_target(target, workspace, profile=profile, target_name=target_name, timeout=0)
    base = _result_base(effective_digest, workspace, identity, observed)
    if record.state == "owner-lost":
        raise SvcError(
            "dev-owner-lost",
            "The provisioning owner was lost before the capability became ready.",
            {**base, "status": "owner-lost", "execution_id": record.execution_id},
        )
    raise SvcError(
        "readiness-timeout",
        "Observed provisioning attempt did not produce readiness before its deadline.",
        {**base, "status": "readiness-timeout", "execution_id": record.execution_id},
    )


def _attempt_error(
    record: ExecutionRecord,
    base: dict[str, object],
    store: ExecutionStore | None,
) -> SvcError:
    details = {**base, "status": record.state, "execution_id": record.execution_id}
    if store is not None:
        details["log_path"] = str(store.log_path(record, "merged"))
    if record.exit_code is not None:
        details["returncode"] = record.exit_code
    return SvcError("provision-exited", "The shared provisioning attempt did not become ready.", details)


@contextmanager
def _cleanup_on_interrupt(
    store: ExecutionStore,
    owned: OwnedExecution,
    base: dict[str, object],
) -> Iterator[None]:
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)}

    def interrupt(_number: int, _frame: object) -> None:
        raise KeyboardInterrupt

    try:
        for number in previous:
            signal.signal(number, interrupt)
        try:
            yield
        except KeyboardInterrupt as error:
            terminated = terminate_owned(store, owned)
            raise SvcError(
                "ensure-interrupted",
                "Ensure was interrupted; SVC cleaned up only the launch it started in this attempt.",
                {
                    **base,
                    "status": "interrupted",
                    "log_path": str(store.log_path(owned.record, "merged")),
                    "cleanup": "completed" if terminated.state == "interrupted" else "unknown",
                },
            ) from error
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def _occupied_error(base: dict[str, object]) -> SvcError:
    return SvcError(
        "occupied-unhealthy",
        "A declared endpoint responded but did not satisfy readiness; SVC will not take it over.",
        {**base, "status": "conflict"},
    )


def _entry_is_healthy(entry: dict[str, object]) -> bool:
    probe = entry.get("probe")
    return isinstance(probe, dict) and bool(probe.get("healthy"))


def _result_base(
    effective_digest: str,
    workspace: WorkspaceIdentity,
    identity: CapabilityIdentity,
    observed: ProbeObservation,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "command": "dev ensure",
        "effective_declaration_digest": effective_digest,
        "workspace": workspace.as_dict(),
        "capability": identity.as_dict(),
        "probe": observed.as_dict(),
    }


def _remaining(deadline: float) -> float:
    return max(0.0, deadline - time.monotonic())
