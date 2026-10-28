"""Adapters use live native managers; a PID is never a control handle."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from platformdirs import user_data_dir

from ...errors import SvcError
from .models import ExternalExecution
from .transport import (
    CodexClient,
    native_command,
    private_directory,
    private_file,
    unix_request,
)


def home() -> Path:
    override = os.environ.get("SVC_HARNESS_HOME")
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            raise SvcError(
                "harness-directory-invalid", "执行来源目录必须使用绝对路径。"
            )
        return path
    return Path(user_data_dir("SVC", appauthor=False)) / "harnesses"


def configuration() -> dict[str, str]:
    root = home()
    if root.exists() or root.is_symlink():
        private_directory(root)
    path = root / "config.json"
    if not path.exists():
        return {}
    private_file(path)
    if path.stat().st_size > 16384:
        raise SvcError("harness-config-invalid", "执行来源配置过大。")
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise SvcError("harness-config-invalid", "执行来源配置版本无效。")
    fields = value.get("settings", {})
    if not isinstance(fields, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) for k, v in fields.items()
    ):
        raise SvcError("harness-config-invalid", "执行来源配置必须是字符串映射。")
    return fields


def timestamp(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()
    return ""


def generation(path: Path) -> str:
    info = private_file(path, socket_file=True)
    return hashlib.sha256(
        f"{path}:{info.st_dev}:{info.st_ino}:{info.st_ctime_ns}".encode()
    ).hexdigest()[:32]


def rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise SvcError("harness-response-invalid", "原生执行清单不是对象数组。")
    return value


class Provider(Protocol):
    name: str
    instance: str

    def executions(self, *, timeout: float = 1.5) -> list[ExternalExecution]: ...
    def stop(self, native_id: str) -> str: ...
    def logs(self, native_id: str) -> tuple[str, bool]: ...


@dataclass
class PiProvider:
    descriptor: Path
    name: str = "pi"

    def __post_init__(self) -> None:
        private_file(self.descriptor)
        if self.descriptor.stat().st_size > 16384:
            raise SvcError("harness-endpoint-invalid", "Pi 接入描述过大。")
        data = json.loads(self.descriptor.read_text())
        if (
            not isinstance(data, dict)
            or data.get("schema_version") != 1
            or not all(
                isinstance(data.get(k), str) for k in ("instance", "socket", "token")
            )
        ):
            raise SvcError("harness-endpoint-invalid", "Pi 接入描述无效。")
        self.path = Path(data["socket"])
        if not self.path.is_absolute() or self.path.parent != home():
            raise SvcError("harness-endpoint-invalid", "Pi socket 不属于本机接入目录。")
        self.instance = str(data["instance"]) + ":" + generation(self.path)
        self.activation = str(data["instance"])
        self.token = str(data["token"])
        self.owner_pid = data.get("pid")
        if (
            not isinstance(self.owner_pid, int)
            or isinstance(self.owner_pid, bool)
            or self.owner_pid <= 1
        ):
            raise SvcError("harness-endpoint-invalid", "Pi 接入缺少本机宿主身份。")

    def request(
        self, operation: str, native_id: str = "", *, timeout: float | None = None
    ) -> dict[str, Any]:
        if self.instance != self.activation + ":" + generation(self.path):
            raise SvcError("harness-instance-changed", "Pi 实例已更换，请刷新后操作。")
        return unix_request(
            self.path,
            {
                "version": 1,
                "instance": self.activation,
                "token": self.token,
                "operation": operation,
                "task_id": native_id,
            },
            timeout=timeout
            if timeout is not None
            else (1.5 if operation == "list" else 32),
        )

    def executions(self, *, timeout: float = 1.5) -> list[ExternalExecution]:
        result = []
        for view in rows(self.request("list", timeout=timeout).get("tasks")):
            item = view.get("task")
            if not isinstance(item, dict) or not all(
                isinstance(item.get(k), str) for k in ("id", "command", "cwd", "status")
            ):
                raise SvcError("harness-response-invalid", "Pi 任务字段无效。")
            state = {
                "running": "running",
                "completed": "completed",
                "failed": "failed",
                "killed": "stopped",
            }.get(item["status"], "unknown")
            pid = item.get("pid")
            result.append(
                ExternalExecution(
                    "",
                    self.name,
                    item["id"],
                    self.instance,
                    str(item.get("name") or item["command"])[:512],
                    item["command"],
                    item["cwd"],
                    state,
                    "task",
                    timestamp(item.get("startTime")),
                    state == "running",
                    True,
                    "Pi 按其原生策略停止整个任务，必要时可能升级为强制终止。",
                    pid
                    if isinstance(pid, int) and not isinstance(pid, bool) and pid > 1
                    else None,
                    local_owner_pid=self.owner_pid,
                    issues=("Pi 清单中的长字段已由原管理器截断。",)
                    if view.get("truncatedFields")
                    else (),
                )
            )
        return result

    def stop(self, native_id: str) -> str:
        self.request("stop", native_id)
        return "Pi 已完成该任务的原生停止处理。"

    def logs(self, native_id: str) -> tuple[str, bool]:
        value = self.request("logs", native_id)
        if not isinstance(value.get("text"), str):
            raise SvcError("harness-response-invalid", "Pi 日志结果无效。")
        return value["text"], bool(value.get("truncated"))


@dataclass
class CodexProvider:
    path: Path
    name: str = "codex"

    def __post_init__(self) -> None:
        if not self.path.is_absolute():
            raise SvcError(
                "harness-endpoint-invalid", "Codex socket 必须使用绝对路径。"
            )
        # The official Unix transport can publish an owner-private socket through a symlink.
        self.path = self.path.resolve(strict=True)
        self.instance = generation(self.path)

    def client(self, timeout: float = 1.5) -> CodexClient:
        if generation(self.path) != self.instance:
            raise SvcError(
                "harness-instance-changed", "Codex 共享实例已更换，请刷新后操作。"
            )
        client = CodexClient(self.path, timeout=timeout)
        try:
            if generation(self.path) != self.instance:
                raise SvcError(
                    "harness-instance-changed", "Codex 在连接期间更换了实例，请刷新。"
                )
        except BaseException:
            client.close()
            raise
        return client

    def executions(self, *, timeout: float = 1.5) -> list[ExternalExecution]:
        result = []
        with self.client(timeout) as client:
            loaded = client.call("thread/loaded/list", {"limit": 16})
            if loaded.get("nextCursor"):
                raise SvcError(
                    "harness-list-incomplete",
                    "Codex 活跃会话超过本轮 16 项预算，请缩小共享服务器范围。",
                )
            threads = loaded.get("data")
            if not isinstance(threads, list) or any(
                not isinstance(item, str) for item in threads
            ):
                raise SvcError("harness-response-invalid", "Codex 会话清单无效。")
            for thread in threads:
                value = client.call(
                    "thread/backgroundTerminals/list", {"threadId": thread, "limit": 64}
                )
                if value.get("nextCursor"):
                    raise SvcError(
                        "harness-list-incomplete",
                        "Codex 后台终端超过本轮预算，清单未作为完整结果使用。",
                    )
                for item in rows(value.get("data")):
                    if not all(
                        isinstance(item.get(k), str)
                        for k in ("processId", "command", "cwd")
                    ):
                        raise SvcError(
                            "harness-response-invalid", "Codex 后台终端字段无效。"
                        )
                    pid = item.get("osPid")
                    native_id = json.dumps(
                        [thread, item["processId"]], separators=(",", ":")
                    )
                    result.append(
                        ExternalExecution(
                            "",
                            self.name,
                            native_id,
                            self.instance,
                            item["command"][:512],
                            item["command"][:4096],
                            item["cwd"],
                            "running",
                            "terminal",
                            "",
                            True,
                            False,
                            "Codex 将停止这个后台终端；不会中断整个 Agent 回合。",
                            pid
                            if isinstance(pid, int)
                            and not isinstance(pid, bool)
                            and pid > 1
                            else None,
                            issues=("Codex 长命令已截断。",)
                            if len(item["command"]) > 4096
                            else (),
                        )
                    )
        return result

    def stop(self, native_id: str) -> str:
        thread, process = json.loads(native_id)
        with self.client(3) as client:
            value = client.call(
                "thread/backgroundTerminals/terminate",
                {"threadId": thread, "processId": process},
            )
        if value.get("terminated") is not True:
            raise SvcError(
                "harness-stop-unconfirmed", "Codex 没有确认停止该后台终端，请刷新状态。"
            )
        return "Codex 已确认原生终止请求；这不代表 SVC 验证了进程组收敛。"

    def logs(self, native_id: str) -> tuple[str, bool]:
        raise SvcError(
            "harness-logs-unavailable",
            "当前 Codex 清单接口不提供日志读取，请在原会话查看。",
        )


@dataclass
class ClaudeProvider:
    executable: str
    name: str = "claude"
    instance: str = "claude-native-agents-v1"

    def executions(self, *, timeout: float = 1.5) -> list[ExternalExecution]:
        value = json.loads(
            native_command([self.executable, "agents", "--json"], timeout=timeout)
        )
        result = []
        for item in rows(value):
            if not isinstance(item.get("cwd"), str) or item.get("kind") not in (
                "background",
                "interactive",
            ):
                raise SvcError("harness-response-invalid", "Claude 原生会话字段无效。")
            raw_id = (
                item.get("id")
                if item["kind"] == "background"
                else item.get("sessionId")
            )
            if (
                not isinstance(raw_id, str)
                or not raw_id
                or raw_id.startswith("-")
                or len(raw_id) > 200
            ):
                continue
            pid = item.get("pid")
            pid = (
                pid
                if isinstance(pid, int) and not isinstance(pid, bool) and pid > 1
                else None
            )
            state = (
                "running"
                if item.get("status") in ("running", "working", "busy", "thinking")
                or item.get("state") in ("running", "starting")
                else "idle"
            )
            if item.get("state") == "done":
                state = "idle" if pid is not None else "completed"
            if item.get("state") in ("failed", "blocked"):
                state = "failed" if item["state"] == "failed" else "unknown"
            label = str(item.get("name") or "Claude Code 会话")[:512]
            # Instance identity fences an id reused by another native session/process.
            instance = hashlib.sha256(
                json.dumps(
                    [
                        str(Path(self.executable).resolve()),
                        raw_id,
                        item.get("sessionId"),
                        item.get("startedAt"),
                        pid,
                    ]
                ).encode()
            ).hexdigest()[:32]
            result.append(
                ExternalExecution(
                    "",
                    self.name,
                    raw_id,
                    instance,
                    label,
                    "",
                    item["cwd"],
                    state,
                    "session",
                    timestamp(item.get("startedAt")),
                    item["kind"] == "background" and pid is not None,
                    item["kind"] == "background",
                    "停止整个 Claude 后台会话及其原生管理的工作，保留会话记录。",
                    pid,
                    local_owner_pid=pid,
                )
            )
        return result

    def stop(self, native_id: str) -> str:
        native_command([self.executable, "stop", native_id], timeout=8)
        return "Claude Code 已处理整个后台会话的停止请求；记录仍保留。"

    def logs(self, native_id: str) -> tuple[str, bool]:
        text = native_command([self.executable, "logs", native_id], timeout=3)
        encoded = text.encode()
        return encoded[-65536:].decode("utf-8", errors="replace"), len(encoded) > 65536
