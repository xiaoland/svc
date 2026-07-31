from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from svc_cli.config import ExecProbe, ExecProvision, HttpProbe, TcpProbe, TargetConfig
from svc_cli.dev.identity import resolve_workspace_identity
from svc_cli.dev.runtime import Launch, _cleanup_on_interrupt, _provision, ensure_target, probe_exec, probe_http, probe_target, probe_tcp
from svc_cli.errors import SvcError


class _Response:
    def __init__(self, status: int) -> None:
        self.status = status

    def close(self) -> None:
        pass


def test_http_probe_enforces_loopback_and_treats_redirect_as_an_observation() -> None:
    probe = HttpProbe(kind="http", url="http://app.localhost/health", success_status=[200, 299])
    observed = probe_http(
        probe,
        probe.url,
        timeout=1,
        resolver=lambda host, port: ("127.0.0.1",),
        opener=lambda request, timeout, context: _Response(302),
    )
    assert not observed.healthy
    assert observed.responded
    assert observed.status_code == 302
    with pytest.raises(SvcError, match="outside loopback"):
        probe_http(
            probe,
            probe.url,
            timeout=1,
            resolver=lambda host, port: ("198.51.100.10",),
            opener=lambda request, timeout, context: _Response(200),
        )


def test_http_probe_pins_the_validated_address_instead_of_resolving_again() -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
            self.send_response(204)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        probe = HttpProbe(kind="http", url=f"http://unresolvable.example:{server.server_port}/", success_status=[200, 299])
        observed = probe_http(probe, probe.url, timeout=1, resolver=lambda host, port: ("127.0.0.1",))
        assert observed.healthy
        assert observed.status_code == 204
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_tcp_probe_failure_is_a_bounded_observation() -> None:
    tcp = TcpProbe(kind="tcp", host="127.0.0.1", port=9, timeout=1)
    observation = probe_tcp(tcp, tcp.host, timeout=0.1, resolver=lambda host, port: ("127.0.0.1",))
    assert not observation.healthy


def test_exec_probe_enforces_its_declared_output_limit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        probe = ExecProbe(kind="exec", argv=[sys.executable, "-c", "print('x' * 100)"], output_limit=10)
        result = probe_exec(probe, tuple(probe.argv), Path(tmp), timeout=1)
        assert not result.healthy
        assert result.reason == "output-limit"
        assert result.output_truncated
        assert result.output_bytes == 10


def test_worktree_scope_refuses_static_probe_and_manual_never_provisions() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        workspace = resolve_workspace_identity(root, namespace="fixture")
        static = TargetConfig(
            probe={"kind": "http", "url": "http://127.0.0.1:1/health"},
            provision={"kind": "manual"},
        )
        with pytest.raises(SvcError, match="provenance"):
            probe_target(static, workspace, profile="local", target_name="app")

        write_config(
            root,
            {
                "schema_version": 2,
                "svc_version": "10.0.1",
                "dev": {
                    "profile": "local",
                    "profiles": {
                        "local": {
                            "targets": {
                                "manual": {
                                    "scope": "repository",
                                    "probe": {"kind": "tcp", "host": "127.0.0.1", "port": 1},
                                    "provision": {"kind": "manual"},
                                }
                            }
                        }
                    },
                },
            },
        )
        with pytest.raises(SvcError, match="manual"):
            ensure_target(root, "manual", namespace="fixture")


def test_owned_early_exit_reports_only_attempt_cleanup() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_config(
            root,
            {
                "schema_version": 2,
                "svc_version": "10.0.1",
                "dev": {
                    "profile": "local",
                    "profiles": {
                        "local": {
                            "targets": {
                                "fails": {
                                    "scope": "repository",
                                    "readiness_timeout": 1,
                                    "poll_interval": 0.01,
                                    "probe": {"kind": "exec", "argv": [sys.executable, "-c", "import sys; sys.exit(1)"]},
                                    "provision": {"kind": "exec", "mode": "run", "argv": [sys.executable, "-c", "import sys; sys.exit(0)"]},
                                }
                            }
                        }
                    },
                },
            },
        )
        with pytest.raises(SvcError) as raised:
            ensure_target(root, "fails", namespace="fixture")
        assert raised.value.code == "provision-exited"
        assert raised.value.details["cleanup"] == "completed"
        assert "log_path" in raised.value.details


def test_concurrent_ensure_starts_once_then_reuses_the_declared_server() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        port = free_port()
        counter = root / "starts.txt"
        server = (
            "from pathlib import Path; import http.server; "
            f"Path({str(counter)!r}).open('a').write('1\\n'); "
            f"http.server.HTTPServer(('127.0.0.1', {port}), http.server.SimpleHTTPRequestHandler).serve_forever()"
        )
        write_config(
            root,
            {
                "schema_version": 2,
                "svc_version": "10.0.1",
                "dev": {
                    "profile": "local",
                    "profiles": {
                        "local": {
                            "targets": {
                                "server": {
                                    "scope": "repository",
                                    "readiness_timeout": 5,
                                    "poll_interval": 0.02,
                                    "probe": {"kind": "http", "url": f"http://127.0.0.1:{port}/", "success_status": [200, 299]},
                                    "provision": {"kind": "exec", "mode": "run", "argv": [sys.executable, "-c", server]},
                                }
                            }
                        }
                    },
                },
            },
        )
        results: list[dict[str, object]] = []
        failures: list[BaseException] = []

        def ensure() -> None:
            try:
                results.append(ensure_target(root, "server", namespace="fixture"))
            except BaseException as error:  # test records concurrent failures
                failures.append(error)

        first = threading.Thread(target=ensure)
        second = threading.Thread(target=ensure)
        first.start()
        second.start()
        first.join()
        second.join()
        try:
            assert failures == []
            assert sorted(str(result["status"]) for result in results) == ["reused", "started"]
            assert counter.read_text(encoding="utf-8") == "1\n"
        finally:
            started = next((result for result in results if result.get("status") == "started"), None)
            if started is not None:
                stop_owned_process(int(started["process_id"]))


def test_keyboard_interrupt_cleans_up_only_the_current_launch() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "launch.log"
        stream = log.open("wb")
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=stream,
            stderr=stream,
            start_new_session=os.name != "nt",
        )
        stream.close()
        with pytest.raises(SvcError) as raised:
            with _cleanup_on_interrupt(Launch(process, log), {"command": "dev ensure"}):
                raise KeyboardInterrupt
        assert raised.value.code == "ensure-interrupted"
        assert raised.value.details["cleanup"] == "completed"
        assert process.poll() is not None


def test_activation_timeout_is_structured_and_cleans_its_owned_group() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace = resolve_workspace_identity(Path(tmp), namespace="fixture")
        provision = ExecProvision(kind="exec", mode="activate", argv=[sys.executable, "-c", "import time; time.sleep(30)"])
        with pytest.raises(SvcError) as raised:
            _provision(
                provision,
                workspace,
                "local",
                "activation",
                SimpleNamespace(runtime_key="fixture"),
                timeout=0.01,
            )
        assert raised.value.code == "activation-timeout"
        assert raised.value.details["cleanup"] == "completed"


def write_config(root: Path, value: object) -> None:
    (root / "svc.json").write_text(json.dumps(value), encoding="utf-8")


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def stop_owned_process(pid: int) -> None:
    if os.name == "nt":
        os.kill(pid, signal.SIGTERM)
    else:
        os.killpg(pid, signal.SIGTERM)
