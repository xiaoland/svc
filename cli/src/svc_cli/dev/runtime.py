"""Resource observations and explicit actions over local execution ownership."""

from __future__ import annotations

import signal
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from filelock import Timeout
from .._execution import (
    ExecutionStore,
    LaunchSpec,
    OwnedExecution,
    ExecutionRecord,
    start_isolated,
    wait_owned,
    terminate_owned,
    release_owned,
    settle_unstarted_interruption,
)
from ..config import ExecAction, ManualAction, declaration_digest_value
from ..errors import SvcError
from ..activity.provenance import register as register_observation
from . import records
from .models import ActionReceipt, CatalogResult, ResourceView, Submission, Observation
from .resources import (
    Resource,
    declarations,
    resolve_entry,
    resolve_resource,
    validate_access_url,
)
from .observations import observe_resource, satisfied, utc_now


@dataclass
class InterruptRequest:
    number: int | None = None


@contextmanager
def interruptions() -> Iterator[InterruptRequest]:
    request = InterruptRequest()
    previous = {}

    def receive(number: int, _frame: object) -> None:
        request.number = number

    if threading.current_thread() is threading.main_thread():
        for number in (signal.SIGINT, signal.SIGTERM):
            previous[number] = signal.signal(number, receive)
    try:
        yield request
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def catalog(
    repo: Path,
    key: str | None = None,
    *,
    observe: bool = False,
    observation: str | None = None,
    store: ExecutionStore | None = None,
) -> CatalogResult:
    workspace, configs = declarations(repo)
    if key is not None and key not in configs:
        raise SvcError("resource-not-declared", "资源未声明。", {"resource": key})
    if observation and not key:
        raise SvcError("observation-resource-required", "按需观察必须选择一个资源。")
    store = store or ExecutionStore()
    views: list[ResourceView] = []
    for name, config in configs.items():
        if key is not None and name != key:
            continue
        resource = resolve_entry(workspace, name, config)
        view = resource.view()
        if observation and observation not in config.observations:
            raise SvcError("observation-not-declared", "观察项未声明。")
        facets = (
            observe_resource(resource, [observation] if observation else None)
            if observe
            else ()
        )
        execution = None
        failure = resource.error
        if resource.coordination:
            try:
                execution = records.inspect(
                    store, resource.coordination.coordination_id
                )
            except SvcError as error:
                failure = error.snapshot()
        views.append(
            view.model_copy(
                update={
                    "observations": facets,
                    "execution": execution,
                    "error": failure,
                }
            )
        )
    partial = any(
        x.error
        or (
            x.execution is not None
            and x.execution.phase == "owner-lost"
            and not x.execution.acknowledged
        )
        or any(o.state == "unknown" or o.stale for o in x.observations)
        for x in views
    )
    return CatalogResult(
        workspace=workspace,
        resources=tuple(views),
        status="not-configured" if not views else "partial" if partial else "ok",
    )


def receipt(
    resource: Resource, action: str, status: str, message: str, **fields: object
) -> ActionReceipt:
    return ActionReceipt.model_validate(
        {
            "resource": resource.key,
            "entry_id": resource.entry_id,
            "action": action,
            "declaration_digest": resource.digest,
            "coordination": resource.coordination,
            "status": status,
            "message": message,
            **fields,
        }
    )


def intent(resource: Resource, action: str) -> str:
    return declaration_digest_value(
        {
            "entry": resource.entry_id,
            "action": action,
            "declaration": resource.digest,
            "execution": resource.actions[action].digest,
        }
    )


def unchanged(resource: Resource) -> bool:
    current = resolve_resource(resource.workspace.root, resource.key)
    return (
        current.digest == resource.digest
        and current.coordination == resource.coordination
    )


def act(
    repo: Path,
    key: str,
    action_key: str,
    *,
    expected_digest: str | None = None,
    store: ExecutionStore | None = None,
) -> ActionReceipt:
    store = store or ExecutionStore()
    selected = resolve_resource(repo, key)
    if expected_digest is not None and selected.digest != expected_digest:
        return receipt(
            selected, action_key, "stale", "声明已变化，请刷新后重新选择动作。"
        )
    if selected.coordination is None:
        return receipt(
            selected,
            action_key,
            "failed",
            "无法解析共享控制边界。",
            error=selected.error,
        )
    action = selected.config.actions.get(action_key)
    if action is None:
        return receipt(selected, action_key, "absent", "资源未声明该动作。")
    if isinstance(action, ManualAction):
        return receipt(
            selected, action_key, "manual", "需要人工操作。", steps=tuple(action.steps)
        )
    lock = store.coordination_lock("dev", selected.coordination.coordination_id)
    with interruptions() as interrupted:
        try:
            lock.acquire(timeout=0)
        except Timeout:
            return join_or_busy(store, selected, action_key, action, interrupted)
        try:
            current = resolve_resource(repo, key)
            if current.coordination != selected.coordination or (
                expected_digest is not None and current.digest != expected_digest
            ):
                return receipt(
                    current, action_key, "stale", "声明或控制边界已变化，请刷新。"
                )
            selected = current
            assert selected.coordination is not None
            action = selected.config.actions.get(action_key)
            if not isinstance(action, ExecAction):
                return receipt(
                    selected, action_key, "stale", "动作声明已变化，请刷新。"
                )
            pair = records.current(
                store, selected.coordination.coordination_id, abandoned=True
            )
            if pair and pair[1].phase == "owner-lost" and not pair[1].acknowledged:
                return receipt(
                    selected,
                    action_key,
                    "owner-lost",
                    "前次执行结果未知；核对控制者后确认恢复。",
                    execution=records.view(store, *pair),
                )
            if interrupted.number is not None:
                return receipt(
                    selected, action_key, "interrupted", "动作启动前已取消。"
                )
            if (
                action.completion == "ready"
                and selected.coordination.scope == "worktree"
                and not any(
                    selected.config.observations[name].purpose == "runtime-readiness"
                    for name in action.conditions
                )
            ):
                return receipt(
                    selected,
                    action_key,
                    "failed",
                    "工作树服务启动必须声明 runtime-readiness 实例观察。",
                )
            if action.convergent:
                observations = observe_resource(selected, action.conditions)
                if satisfied(observations):
                    return receipt(
                        selected,
                        action_key,
                        "reused",
                        "声明的正向条件已满足。",
                        observations=observations,
                    )
            return execute(store, selected, action_key, action, interrupted)
        finally:
            lock.release()


def join_or_busy(
    store: ExecutionStore,
    selected: Resource,
    key: str,
    action: ExecAction,
    interrupted: InterruptRequest,
) -> ActionReceipt:
    assert selected.coordination is not None
    pair = records.current(store, selected.coordination.coordination_id)
    if not pair or not action.convergent:
        return receipt(
            selected,
            key,
            "busy",
            "同一资源已有控制操作；本次没有排队。",
            execution=records.view(store, *pair) if pair else None,
        )
    execution, record = pair
    if (
        record.phase != "pending"
        or record.entry_id != selected.entry_id
        or record.action != key
        or record.intent_digest != intent(selected, key)
        or record.declaration_digest != selected.digest
    ):
        return receipt(
            selected,
            key,
            "busy",
            "在途操作不属于同一入口、动作和声明。",
            execution=records.view(store, *pair),
        )
    while True:
        if interrupted.number is not None:
            return receipt(
                selected,
                key,
                "interrupted",
                "已停止等待；未终止原动作。",
                execution=records.view(store, execution, record),
            )
        if not unchanged(selected):
            return receipt(selected, key, "stale", "等待期间声明已变化，请刷新。")
        execution = store.read(execution.execution_id)
        record = records.read(store, execution)
        if record.phase == "settled":
            assert record.receipt is not None
            return record.receipt.model_copy(update={"joined": True})
        if record.phase == "owner-lost":
            return receipt(
                selected,
                key,
                "owner-lost",
                "原动作失去执行者，结果未知。",
                execution=records.view(store, execution, record),
            )
        lock = store.coordination_lock("dev", execution.coordination_key)
        try:
            lock.acquire(timeout=0)
        except Timeout:
            time.sleep(0.05)
        else:
            try:
                records.current(store, execution.coordination_key, abandoned=True)
            finally:
                lock.release()


def execute(
    store: ExecutionStore,
    resource: Resource,
    key: str,
    action: ExecAction,
    interrupted: InterruptRequest,
) -> ActionReceipt:
    assert resource.coordination is not None
    resolved = resource.actions[key]
    published = store.publish(
        domain="dev",
        operation="act",
        subject=resource.key,
        workspace_instance=resource.workspace.instance,
        intent_digest=intent(resource, key),
        coordination_key=resource.coordination.coordination_id,
        argv=resolved.argv,
        cwd=resolved.cwd,
        capture="merged",
    )
    meta = records.DevRecord(
        execution_id=published.record.execution_id,
        coordination_id=resource.coordination.coordination_id,
        entry_id=resource.entry_id,
        action=key,
        declaration_digest=resource.digest,
        intent_digest=published.record.intent_digest,
    )
    owned: OwnedExecution | None = None
    final: ExecutionRecord | None
    try:
        records.write(store, meta)
        store.write_coordination("dev", meta.coordination_id, meta.execution_id)
        if interrupted.number is not None:
            final = settle_unstarted_interruption(
                store, published.record, interrupted.number
            )
            result = receipt(resource, key, "interrupted", "动作启动前已取消。")
            return settle(store, meta, final, result, interrupted)
        environment = dict(resolved.env)
        result_path = store.execution_dir(meta.execution_id) / "dev-result.json"
        if action.result == "operation-json":
            environment["SVC_DEV_RESULT_FILE"] = str(result_path)
        launched = start_isolated(
            store,
            published,
            LaunchSpec(resolved.argv, resolved.cwd, environment),
            wait_on_record_failure=action.interruption == "wait",
        )
        if isinstance(launched, ExecutionRecord):
            return settle(
                store,
                meta,
                launched,
                receipt(resource, key, "failed", "无法启动动作。"),
                interrupted,
            )
        owned = launched
        register_observation(
            store,
            owned.record,
            resource.workspace.root,
            "declared",
            resource_entry_id=resource.entry_id,
            resource_key=resource.key,
        )
        started = time.monotonic()
        ready_deadline = started + action.completion_timeout
        observations: tuple[Observation, ...] = ()
        while True:
            if interrupted.number is not None and action.interruption == "terminate":
                final = terminate_owned(
                    store, owned, requested_signal=interrupted.number
                )
                return settle(
                    store,
                    meta,
                    final,
                    receipt(resource, key, "interrupted", "本次拥有的动作已终止。"),
                    interrupted,
                )
            if (
                action.timeout is not None
                and time.monotonic() - started >= action.timeout
            ):
                final = terminate_owned(store, owned)
                return settle(
                    store,
                    meta,
                    final,
                    receipt(resource, key, "interrupted", "动作达到声明的终止期限。"),
                    interrupted,
                )
            requested = (
                signal.Signals(interrupted.number).name if interrupted.number else None
            )
            if meta.requested_signal != requested:
                meta = meta.model_copy(update={"requested_signal": requested})
                records.write(store, meta)
            final = wait_owned(store, owned, timeout=0.05)
            if action.completion == "ready":
                if final is not None:
                    return settle(
                        store,
                        meta,
                        final,
                        receipt(resource, key, "failed", "进程在取得就绪证明前退出。"),
                        interrupted,
                    )
                observations = observe_resource(resource, action.conditions)
                runtime_facets = [
                    resource.config.observations[name] for name in action.conditions
                ]
                provenance = resource.coordination.scope != "worktree" or any(
                    x.purpose == "runtime-readiness" for x in runtime_facets
                )
                if satisfied(observations) and provenance:
                    final = release_owned(store, owned)
                    if final.state == "released":
                        owned = (
                            None  # Receipt storage cannot revoke released ownership.
                        )
                    if final.state != "released":
                        return settle(
                            store,
                            meta,
                            final,
                            receipt(resource, key, "failed", "进程在释放前退出。"),
                            interrupted,
                        )
                    return settle(
                        store,
                        meta,
                        final,
                        receipt(
                            resource,
                            key,
                            "ready",
                            "就绪条件已证实；进程已释放。",
                            observations=observations,
                        ),
                        interrupted,
                    )
                if time.monotonic() >= ready_deadline:
                    final = terminate_owned(store, owned)
                    return settle(
                        store,
                        meta,
                        final,
                        receipt(
                            resource,
                            key,
                            "condition-unmet",
                            "未取得就绪与实例证明，本次启动已终止。",
                            observations=observations,
                        ),
                        interrupted,
                    )
                time.sleep(action.poll_interval)
                continue
            if final is not None:
                break
        if final.state == "interrupted":
            return settle(
                store,
                meta,
                final,
                receipt(resource, key, "interrupted", "控制者因信号退出。"),
                interrupted,
            )
        if final.exit_code != 0:
            return settle(
                store,
                meta,
                final,
                receipt(
                    resource,
                    key,
                    "failed",
                    f"控制者拒绝或执行失败（退出 {final.exit_code}）。",
                ),
                interrupted,
            )
        if action.completion == "submitted":
            operation = None
            if action.result == "operation-json":
                try:
                    submission = Submission.model_validate_json(
                        records.read_regular(result_path, 65536)
                    )
                    if submission.operation.url:
                        validate_access_url(submission.operation.url)
                    operation = submission.operation
                except (OSError, ValueError) as error:
                    return settle(
                        store,
                        meta,
                        final,
                        receipt(
                            resource,
                            key,
                            "failed",
                            f"提交命令退出 0，但结果无效；请求可能已发生：{error}",
                        ),
                        interrupted,
                    )
            return settle(
                store,
                meta,
                final,
                receipt(
                    resource,
                    key,
                    "accepted",
                    "控制者已接受请求；资源操作尚未证实完成。",
                    operation=operation,
                ),
                interrupted,
            )
        if action.conditions:
            deadline = time.monotonic() + action.completion_timeout
            while True:
                observations = observe_resource(resource, action.conditions)
                if satisfied(observations) or time.monotonic() >= deadline:
                    break
                time.sleep(action.poll_interval)
            if not satisfied(observations):
                return settle(
                    store,
                    meta,
                    final,
                    receipt(
                        resource,
                        key,
                        "condition-unmet",
                        "命令结束，但完成条件尚未证实。",
                        observations=observations,
                    ),
                    interrupted,
                )
        return settle(
            store,
            meta,
            final,
            receipt(
                resource,
                key,
                "completed",
                "声明动作已完成。",
                observations=observations,
            ),
            interrupted,
        )
    except BaseException:
        # Keep wait ownership even if evidence storage fails after process creation.
        if owned is not None and owned.process.poll() is None:
            if action.interruption == "wait":
                owned.process.wait()
            else:
                terminate_owned(store, owned)
        raise
    finally:
        if published.merged_stream is not None:
            published.merged_stream.close()


def settle(
    store: ExecutionStore,
    meta: records.DevRecord,
    final: ExecutionRecord,
    result: ActionReceipt,
    interrupted: InterruptRequest,
) -> ActionReceipt:
    settled = meta.model_copy(update={"phase": "settled"})
    result = result.model_copy(
        update={
            "execution": records.view(store, final, settled),
            "requested_signal": signal.Signals(interrupted.number).name
            if interrupted.number
            else None,
        }
    )
    records.write(
        store,
        settled.model_copy(
            update={"receipt": result, "requested_signal": result.requested_signal}
        ),
    )
    return result


def reconcile(
    repo: Path,
    key: str,
    execution_id: str,
    *,
    acknowledge: bool = False,
    store: ExecutionStore | None = None,
) -> ActionReceipt:
    store = store or ExecutionStore()
    resource = resolve_resource(repo, key)
    if resource.coordination is None:
        return receipt(
            resource, "reconcile", "failed", "无法解析控制边界。", error=resource.error
        )
    lock = store.coordination_lock("dev", resource.coordination.coordination_id)
    try:
        lock.acquire(timeout=0)
    except Timeout:
        return receipt(resource, "reconcile", "busy", "执行者仍持有资源控制锁。")
    try:
        current = resolve_resource(repo, key)
        if (
            current.digest != resource.digest
            or current.coordination != resource.coordination
        ):
            return receipt(current, "reconcile", "stale", "声明已变化，请刷新。")
        pair = records.current(
            store, resource.coordination.coordination_id, abandoned=True
        )
        if not pair:
            return receipt(
                resource, "reconcile", "nothing-to-reconcile", "没有未决执行。"
            )
        execution, meta = pair
        if execution.execution_id != execution_id:
            return receipt(
                resource,
                "reconcile",
                "stale",
                "execution ID 不是当前边界的执行。",
                execution=records.view(store, *pair),
            )
        if meta.phase != "owner-lost":
            return receipt(
                resource,
                "reconcile",
                "nothing-to-reconcile",
                "当前执行无需恢复。",
                execution=records.view(store, *pair),
            )
        if acknowledge and not meta.acknowledged:
            meta = meta.model_copy(
                update={"acknowledged": True, "acknowledged_at": utc_now()}
            )
            records.write(store, meta)
        return receipt(
            resource,
            "reconcile",
            "acknowledged" if meta.acknowledged else "owner-lost",
            "已确认原结果未知；没有重试或终止旧进程。"
            if meta.acknowledged
            else "原结果未知，重新操作可能重复；需要明确确认。",
            execution=records.view(store, execution, meta),
        )
    finally:
        lock.release()
