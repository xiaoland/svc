"""Discover existing managers and route exact native identities back to them."""

from __future__ import annotations

import base64
import json
import os
import shutil
import time
from dataclasses import replace
from pathlib import Path

from ...errors import SvcError
from ..models import TerminationResult
from ..provenance import project_for
from .models import ExecutionLogs, ExternalExecution, HarnessSnapshot, HarnessStatus
from .providers import (
    ClaudeProvider,
    CodexProvider,
    PiProvider,
    Provider,
    configuration,
    home,
)


def identity(item: ExternalExecution) -> str:
    value = json.dumps(
        [item.provider, item.instance_id, item.native_id], separators=(",", ":")
    ).encode()
    return "harness:" + base64.urlsafe_b64encode(value).decode().rstrip("=")


def decode_identity(value: str) -> tuple[str, str, str]:
    try:
        if not value.startswith("harness:") or len(value) > 8192:
            raise ValueError("invalid id")
        encoded = value.removeprefix("harness:")
        fields = json.loads(
            base64.b64decode(
                encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True
            )
        )
        if (
            not isinstance(fields, list)
            or len(fields) != 3
            or any(not isinstance(v, str) or not v for v in fields)
        ):
            raise ValueError("invalid fields")
        if fields[0] not in ("pi", "codex", "claude"):
            raise ValueError("invalid provider")
        return fields[0], fields[1], fields[2]
    except (ValueError, UnicodeError) as error:
        raise SvcError("harness-id-invalid", "外部执行标识无效。") from error


def discover(only: str | None = None) -> tuple[list[Provider], list[HarnessStatus]]:
    providers: list[Provider] = []
    states: list[HarnessStatus] = []
    config = configuration()
    if only in (None, "pi"):
        descriptors = (
            sorted(
                home().glob("pi-*.json"),
                key=lambda item: item.stat().st_mtime_ns,
                reverse=True,
            )
            if home().exists()
            else []
        )
        for path in descriptors[:8]:
            try:
                providers.append(PiProvider(path))
            except (SvcError, OSError, ValueError) as error:
                states.append(HarnessStatus("pi", "unavailable", str(error)[:2000]))
        if len(descriptors) > 8:
            states.append(HarnessStatus("pi", "partial", "Pi 实例超过本轮 8 项预算。"))
        if not descriptors:
            states.append(HarnessStatus("pi", "waiting", "等待 Pi 加载 SVC 接入扩展。"))
    if only in (None, "codex"):
        codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        path = Path(
            config.get(
                "codex_socket",
                str(codex_home / "app-server-control/app-server-control.sock"),
            )
        )
        if path.exists():
            try:
                providers.append(CodexProvider(path))
            except (SvcError, OSError) as error:
                states.append(HarnessStatus("codex", "unavailable", str(error)))
        else:
            states.append(
                HarnessStatus(
                    "codex",
                    "unavailable",
                    "未检测到 Codex 共享控制 socket；不会启动新服务器接管桌面任务。",
                )
            )
    if only in (None, "claude"):
        executable = config.get("claude_cli") or shutil.which("claude")
        if executable:
            providers.append(ClaudeProvider(executable))
        else:
            states.append(
                HarnessStatus(
                    "claude", "unavailable", "未找到支持 agents --json 的 Claude Code。"
                )
            )
    return providers, states


def collect(project_roots: tuple[Path, ...] = ()) -> HarnessSnapshot:
    try:
        providers, states = discover()
    except (OSError, ValueError, SvcError) as error:
        return HarnessSnapshot(
            (), (HarnessStatus("configuration", "unavailable", str(error)),)
        )
    executions: list[ExternalExecution] = []
    counts: dict[str, int] = {}
    deadline = time.monotonic() + 3
    for provider in providers:
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SvcError(
                    "harness-budget-exhausted", "本轮来源读取达到 3 秒预算，状态未知。"
                )
            items = provider.executions(timeout=min(1.5, remaining))
            if len(executions) + len(items) > 256:
                states.append(
                    HarnessStatus(
                        provider.name,
                        "partial",
                        "外部执行超过本轮 256 项预算，其余未读取。",
                    )
                )
            for item in items[: max(0, 256 - len(executions))]:
                path = Path(item.cwd)
                if not path.is_absolute() or not path.is_dir():
                    project = None
                else:
                    cwd = path.resolve()
                    project = next(
                        (
                            root
                            for root in sorted(
                                project_roots,
                                key=lambda value: len(value.parts),
                                reverse=True,
                            )
                            if cwd == root or root in cwd.parents
                        ),
                        None,
                    )
                    if project is None:
                        project, _ = project_for(cwd, None)
                executions.append(
                    replace(
                        item,
                        execution_id=identity(item),
                        project_path=str(project) if project else None,
                    )
                )
            counts[provider.name] = counts.get(provider.name, 0) + 1
        except (OSError, ValueError, TypeError, SvcError) as error:
            states.append(
                HarnessStatus(provider.name, "unavailable", str(error)[:2000])
            )
    normalized = []
    for name in ("pi", "codex", "claude"):
        notices = [item for item in states if item.provider == name]
        count = counts.get(name, 0)
        state = (
            "partial"
            if count and notices
            else ("connected" if count else notices[0].state)
        )
        message = (
            "；".join(dict.fromkeys(item.message for item in notices))
            if notices
            else "已连接原生执行管理器。"
        )
        normalized.append(HarnessStatus(name, state, message, count))
    return HarnessSnapshot(tuple(executions), tuple(normalized))


def resolve(value: str) -> tuple[Provider, ExternalExecution]:
    name, instance, native_id = decode_identity(value)
    providers, _ = discover(name)
    for provider in providers:
        if name != "claude" and provider.instance != instance:
            continue
        for item in provider.executions():
            if (
                item.instance_id == instance
                and item.native_id == native_id
                and identity(item) == value
            ):
                return provider, item
    raise SvcError(
        "harness-execution-stale",
        "该执行已结束、来源已重载或身份已变化，请刷新后操作。",
    )


def terminate(value: str, *, force: bool, by: str) -> TerminationResult:
    if force:
        raise SvcError(
            "harness-force-unsupported",
            "外部执行只能使用原管理器的停止策略，SVC 不提供额外强杀。",
        )
    if by == "agent":
        raise SvcError(
            "harness-human-stop-only",
            "原生管理器接入的人工停止入口不能伪装成 Agent 自动操作。",
        )
    provider, item = resolve(value)
    if not item.can_terminate:
        raise SvcError("harness-read-only", "当前原生执行未提供可用的停止通道。")
    return TerminationResult(
        value, "requested", "native", provider.stop(item.native_id)
    )


def logs(value: str) -> ExecutionLogs:
    provider, item = resolve(value)
    if not item.can_read_logs:
        raise SvcError(
            "harness-logs-unavailable", "此来源未提供日志读取，请在原会话查看。"
        )
    text, truncated = provider.logs(item.native_id)
    return ExecutionLogs(value, text, truncated)
