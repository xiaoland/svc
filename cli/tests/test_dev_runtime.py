from __future__ import annotations
import sys
import tempfile
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import pytest
from svc_cli.config import ExecProbe, HttpProbe
from svc_cli.dev.readiness import probe_exec, probe_http
from svc_cli.dev.runtime import catalog
from svc_cli.errors import SvcError
from svc_cli_test_support.project_contract import write_project_config


class _Response:
    def __init__(self, status: int) -> None:
        self.status = status

    def close(self) -> None:
        pass


@pytest.mark.parametrize("kind", ["absent", "manual", "exec"])
def test_status_reports_stop_capability_without_executing_cleanup(
    tmp_path: Path, kind: str
) -> None:
    marker = tmp_path / "stopped"
    resource = {"scope": "repository", "access": ["http://localhost"]}
    if kind != "absent":
        action = {"kind": kind, "intent": "停止", "effect_scope": "当前实例"}
        if kind == "manual":
            action["steps"] = ["停止外部控制者"]
        else:
            action["argv"] = [
                sys.executable,
                "-c",
                f"from pathlib import Path; Path({str(marker)!r}).touch()",
            ]
        resource["actions"] = {"stop": action}
    write_project_config(tmp_path, dev_resources={"app": resource})
    actions = catalog(tmp_path, observe=True).resources[0].actions
    assert [action.kind for action in actions] == ([] if kind == "absent" else [kind])
    assert not marker.exists()


def test_http_probe_enforces_loopback_and_treats_redirect_as_an_observation() -> None:
    probe = HttpProbe(
        kind="http", url="http://app.localhost/health", success_status=[200, 299]
    )
    observed = probe_http(
        probe,
        probe.url,
        timeout=1,
        resolver=lambda host, port: ("127.0.0.1",),
        opener=lambda method, path, headers, timeout: _Response(302),
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
            opener=lambda method, path, headers, timeout: _Response(200),
        )


def test_http_probe_pins_the_validated_address_instead_of_resolving_again() -> None:
    requests: list[tuple[str, str]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
            requests.append((self.path, self.headers["Host"]))
            self.send_response(302)
            self.send_header("Location", "/followed")
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        probe = HttpProbe(
            kind="http",
            url=f"http://unresolvable.example:{server.server_port}/",
            success_status=[200, 299],
        )
        observed = probe_http(
            probe, probe.url, timeout=1, resolver=lambda host, port: ("127.0.0.1",)
        )
        assert not observed.healthy
        assert observed.status_code == 302
        assert requests == [("/", f"unresolvable.example:{server.server_port}")]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_exec_probe_enforces_its_declared_output_limit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        probe = ExecProbe(
            kind="exec",
            argv=[sys.executable, "-c", "print('x' * 100)"],
            output_limit=10,
        )
        result = probe_exec(probe, tuple(probe.argv), Path(tmp), timeout=1)
        assert not result.healthy
        assert result.reason == "output-limit"
        assert result.output_truncated
        assert result.output_bytes == 10
