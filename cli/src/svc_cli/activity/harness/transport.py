"""Bounded native clients; closing a client never stops its owner's tasks."""

from __future__ import annotations

import json
import os
import selectors
import socket
import stat
import subprocess
import time
from pathlib import Path
from typing import Any

from websockets.exceptions import WebSocketException
from websockets.sync.client import unix_connect

from ...errors import SvcError

MAX_FRAME = 1024 * 1024


def private_directory(path: Path) -> None:
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
    ):
        raise SvcError(
            "harness-directory-invalid", "SVC 执行来源目录必须仅当前用户可访问。"
        )


def private_file(path: Path, *, socket_file: bool = False) -> os.stat_result:
    info = path.lstat()
    expected = stat.S_ISSOCK if socket_file else stat.S_ISREG
    if not expected(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise SvcError(
            "harness-endpoint-invalid",
            "执行来源必须使用当前用户私有的普通文件或 socket。",
        )
    return info


def native_command(argv: list[str], *, timeout: float = 1.5) -> str:
    selector = selectors.DefaultSelector()
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        selector.close()
        raise SvcError(
            "harness-command-unavailable", f"无法启动原生管理器：{error}"
        ) from error
    captured: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = time.monotonic() + timeout
    assert process.stdout is not None and process.stderr is not None
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SvcError(
                    "harness-timeout", "原生管理器响应超时；控制结果未知，请刷新。"
                )
            events = selector.select(min(0.1, remaining))
            if not events and process.poll() is not None:
                break
            for key, _ in events:
                data = os.read(key.fd, 65536)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                captured[key.data].extend(data)
                bound = MAX_FRAME if key.data == "stdout" else 16384
                if len(captured[key.data]) > bound:
                    raise SvcError(
                        "harness-response-too-large", "原生管理器输出超过本轮读取预算。"
                    )
        try:
            code = process.wait(timeout=max(0.01, deadline - time.monotonic()))
        except subprocess.TimeoutExpired as error:
            raise SvcError(
                "harness-timeout", "原生管理器响应超时；控制结果未知。"
            ) from error
        if code:
            message = (
                captured["stderr"].decode("utf-8", errors="replace")[:2000].strip()
            )
            raise SvcError(
                "harness-command-failed", message or f"原生管理器退出 {code}。"
            )
        return captured["stdout"].decode("utf-8", errors="replace")
    finally:
        selector.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        process.stdout.close()
        process.stderr.close()


def unix_request(
    path: Path, payload: dict[str, object], *, timeout: float = 0.7
) -> dict[str, Any]:
    private_file(path, socket_file=True)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        deadline = time.monotonic() + timeout
        client.settimeout(timeout)
        try:
            client.connect(str(path))
            client.sendall(json.dumps(payload).encode() + b"\n")
            data = bytearray()
            while b"\n" not in data:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise SvcError(
                        "harness-timeout", "执行来源读取已超过本轮截止时间。"
                    )
                client.settimeout(remaining)
                chunk = client.recv(min(65536, MAX_FRAME + 1 - len(data)))
                if not chunk:
                    raise SvcError("harness-disconnected", "执行来源在返回结果前断开。")
                data.extend(chunk)
                if len(data) > MAX_FRAME:
                    raise SvcError(
                        "harness-response-too-large", "执行来源结果超过 1 MiB。"
                    )
            value = json.loads(bytes(data).split(b"\n", 1)[0])
        except (OSError, ValueError) as error:
            raise SvcError(
                "harness-unavailable", f"无法连接执行来源：{error}"
            ) from error
    if not isinstance(value, dict):
        raise SvcError("harness-response-invalid", "执行来源没有返回对象。")
    if value.get("ok") is not True:
        raise SvcError(
            "harness-request-failed", str(value.get("error", "原生请求失败。"))[:2000]
        )
    result = value.get("result")
    if not isinstance(result, dict):
        raise SvcError("harness-response-invalid", "执行来源结果不完整。")
    return result


class CodexClient:
    """Attach through the public Unix WebSocket endpoint, without starting a server."""

    def __init__(self, path: Path, *, timeout: float = 1.5):
        private_file(path, socket_file=True)
        self.deadline = time.monotonic() + timeout
        self.counter = 0
        try:
            self.connection = unix_connect(
                str(path),
                open_timeout=timeout,
                close_timeout=0.1,
                max_size=MAX_FRAME,
                max_queue=2,
                compression=None,
                ping_interval=None,
            )
        except (OSError, TimeoutError, WebSocketException) as error:
            raise SvcError(
                "harness-unavailable", f"Codex 共享连接失败：{error}"
            ) from error
        try:
            self.call(
                "initialize",
                {
                    "clientInfo": {"name": "svc-dev", "version": "0.2.0"},
                    "capabilities": {"experimentalApi": True},
                },
            )
            self.send({"method": "initialized", "params": {}})
        except BaseException:
            self.close()
            raise

    def send(self, value: dict[str, object]) -> None:
        try:
            self.connection.send(json.dumps(value))
        except (OSError, WebSocketException) as error:
            raise SvcError(
                "harness-disconnected", f"Codex 共享连接已断开：{error}"
            ) from error

    def call(self, method: str, params: dict[str, object]) -> dict[str, Any]:
        self.counter += 1
        request_id = self.counter
        self.send({"id": request_id, "method": method, "params": params})
        while True:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise SvcError("harness-timeout", "Codex 共享服务器响应超时。")
            try:
                value = json.loads(self.connection.recv(timeout=remaining))
            except TimeoutError as error:
                raise SvcError(
                    "harness-timeout", "Codex 共享服务器响应超时。"
                ) from error
            except (OSError, WebSocketException, ValueError) as error:
                raise SvcError(
                    "harness-response-invalid", f"Codex 共享响应无效：{error}"
                ) from error
            if not isinstance(value, dict):
                raise SvcError("harness-response-invalid", "Codex 响应不是对象。")
            if value.get("id") != request_id or not (
                "result" in value or "error" in value
            ):
                continue
            if "error" in value:
                raise SvcError("harness-request-failed", str(value["error"])[:2000])
            result = value.get("result")
            if not isinstance(result, dict):
                raise SvcError("harness-response-invalid", "Codex 返回了不完整的结果。")
            return result

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> CodexClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
