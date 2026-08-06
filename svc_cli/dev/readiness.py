"""Dev-owned HTTP, TCP, and exec readiness evaluation."""

from __future__ import annotations

import ipaddress
import socket
import ssl
import subprocess
import threading
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Protocol

import urllib3

from ..config import ExecProbe, HttpProbe, TargetConfig, TcpProbe
from ..errors import SvcError
from ..workspace import WorkspaceIdentity
from .identity import interpolate_dev_argv, interpolate_dev_value, require_worktree_provenance


class _HTTPResponse(Protocol):
    status: int

    def close(self) -> None: ...


@dataclass(frozen=True)
class ProbeObservation:
    kind: str
    healthy: bool
    reason: str
    endpoint_identity: str
    responded: bool = False
    status_code: int | None = None
    output_bytes: int | None = None
    output_truncated: bool = False

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "kind": self.kind,
            "healthy": self.healthy,
            "reason": self.reason,
            "endpoint_identity": self.endpoint_identity,
            "responded": self.responded,
        }
        if self.status_code is not None:
            result["status_code"] = self.status_code
        if self.output_bytes is not None:
            result["output_bytes"] = self.output_bytes
            result["output_truncated"] = self.output_truncated
        return result


def probe_target(
    target: TargetConfig,
    workspace: WorkspaceIdentity,
    *,
    profile: str,
    target_name: str,
    timeout: float | None = None,
) -> ProbeObservation:
    probe = target.probe
    effective_timeout = min(probe.timeout, timeout) if timeout is not None else probe.timeout
    if effective_timeout <= 0:
        return ProbeObservation(probe.kind, False, "deadline-exhausted", "deadline")
    if isinstance(probe, HttpProbe):
        url = interpolate_dev_value(probe.url, workspace, profile=profile, target=target_name)
        require_worktree_provenance(target.scope, url, workspace)
        return probe_http(probe, url, timeout=effective_timeout)
    if isinstance(probe, TcpProbe):
        host = interpolate_dev_value(probe.host, workspace, profile=profile, target=target_name)
        endpoint = f"tcp://{host}:{probe.port}"
        require_worktree_provenance(target.scope, endpoint, workspace)
        return probe_tcp(probe, host, timeout=effective_timeout)
    argv = interpolate_dev_argv(probe.argv, workspace, profile=profile, target=target_name)
    endpoint = "exec:" + "\0".join(argv)
    require_worktree_provenance(target.scope, endpoint, workspace)
    cwd = resolve_dev_cwd(workspace.root, probe.cwd, workspace, profile, target_name)
    return probe_exec(probe, argv, cwd, timeout=effective_timeout)


def probe_http(
    probe: HttpProbe,
    url: str,
    *,
    timeout: float,
    opener: Callable[[str, str, dict[str, str], float], _HTTPResponse] | None = None,
    resolver: Callable[[str, int], Iterable[str]] | None = None,
) -> ProbeObservation:
    parsed = _validate_http_url(url)
    port = parsed.port or _default_port(parsed.scheme)
    addresses = _resolve_addresses(parsed.hostname or "", port, resolver)
    _enforce_address_scope(addresses, probe.network_scope)
    deadline = time.monotonic() + timeout
    path = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    headers = {"Host": parsed.netloc}
    try:
        if opener is not None:
            response = opener(probe.method, path, headers, timeout)
            try:
                status = int(getattr(response, "status"))
            finally:
                response.close()
        else:
            status = _pinned_http_status(probe, parsed, addresses, path, headers, deadline)
    except (urllib3.exceptions.HTTPError, OSError, ssl.SSLError, TimeoutError) as error:
        return ProbeObservation("http", False, _network_error_reason(error), url)
    lower, upper = probe.success_status
    healthy = lower <= status <= upper
    return ProbeObservation(
        "http",
        healthy,
        "accepted-status" if healthy else "unexpected-status",
        url,
        True,
        status,
    )


def probe_tcp(
    probe: TcpProbe,
    host: str,
    *,
    timeout: float,
    resolver: Callable[[str, int], Iterable[str]] | None = None,
) -> ProbeObservation:
    addresses = _resolve_addresses(host, probe.port, resolver)
    _enforce_address_scope(addresses, probe.network_scope)
    endpoint = f"tcp://{host}:{probe.port}"
    deadline = time.monotonic() + timeout
    last_error: OSError | None = None
    for address in addresses:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return ProbeObservation("tcp", False, "timeout", endpoint)
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        try:
            with socket.socket(family, socket.SOCK_STREAM) as connection:
                connection.settimeout(remaining)
                connection.connect((address, probe.port))
            return ProbeObservation("tcp", True, "connected", endpoint, True)
        except OSError as error:
            last_error = error
    return ProbeObservation("tcp", False, _network_error_reason(last_error), endpoint)


def probe_exec(probe: ExecProbe, argv: tuple[str, ...], cwd: Path, *, timeout: float) -> ProbeObservation:
    captured = bytearray()
    overflow = False
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=False,
            close_fds=True,
        )
    except OSError:
        return ProbeObservation("exec", False, "exec-start-failed", "exec:" + "\0".join(argv))
    assert process.stdout is not None
    output = process.stdout

    def drain() -> None:
        nonlocal overflow
        while chunk := output.read(8_192):
            remaining = probe.output_limit - len(captured)
            if remaining > 0:
                captured.extend(chunk[:remaining])
            if len(chunk) > remaining:
                overflow = True

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        reader.join(timeout=1)
        process.stdout.close()
        return ProbeObservation(
            "exec",
            False,
            "timeout",
            "exec:" + "\0".join(argv),
            output_bytes=len(captured),
            output_truncated=overflow,
        )
    reader.join(timeout=1)
    process.stdout.close()
    return ProbeObservation(
        "exec",
        code == 0 and not overflow,
        "zero-exit" if code == 0 and not overflow else "nonzero-exit" if code else "output-limit",
        "exec:" + "\0".join(argv),
        output_bytes=len(captured),
        output_truncated=overflow,
    )


def resolve_dev_cwd(
    root: Path,
    configured: str | None,
    workspace: WorkspaceIdentity,
    profile: str,
    target: str,
) -> Path:
    value = interpolate_dev_value(configured or ".", workspace, profile=profile, target=target)
    candidate = (root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise SvcError("dev-cwd-escapes-workspace", "Dev command working directory escapes the workspace.") from error
    if not candidate.is_dir():
        raise SvcError("dev-cwd-not-directory", "Dev command working directory does not exist.", {"cwd": value})
    return candidate


def _pinned_http_status(
    probe: HttpProbe,
    parsed: urllib.parse.SplitResult,
    addresses: Iterable[str],
    path: str,
    headers: dict[str, str],
    deadline: float,
) -> int:
    port = parsed.port or _default_port(parsed.scheme)
    last_error: BaseException | None = None
    for address in addresses:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("HTTP readiness deadline exhausted")
        if parsed.scheme == "https":
            pool: urllib3.HTTPConnectionPool = urllib3.HTTPSConnectionPool(
                address,
                port,
                assert_hostname=False if probe.insecure_tls else parsed.hostname,
                server_hostname=parsed.hostname,
                cert_reqs=ssl.CERT_NONE if probe.insecure_tls else ssl.CERT_REQUIRED,
                retries=False,
            )
        else:
            pool = urllib3.HTTPConnectionPool(address, port, retries=False)
        try:
            response = pool.urlopen(
                probe.method,
                path,
                headers=headers,
                retries=False,
                redirect=False,
                assert_same_host=False,
                timeout=urllib3.Timeout(total=remaining, connect=remaining, read=remaining),
                preload_content=False,
            )
            try:
                return int(response.status)
            finally:
                response.close()
        except (urllib3.exceptions.HTTPError, OSError, ssl.SSLError, TimeoutError) as error:
            last_error = error
        finally:
            pool.close()
    if last_error is not None:
        raise last_error
    raise OSError("no probe address was attempted")


def _validate_http_url(value: str) -> urllib.parse.SplitResult:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise SvcError("invalid-http-probe-url", "HTTP probe URL must be an absolute HTTP(S) URL without credentials or fragments.")
    try:
        _ = parsed.port
    except ValueError as error:
        raise SvcError("invalid-http-probe-url", "HTTP probe URL has an invalid port.") from error
    return parsed


def _default_port(scheme: str) -> int:
    return 443 if scheme == "https" else 80


def _resolve_addresses(
    host: str,
    port: int,
    resolver: Callable[[str, int], Iterable[str]] | None = None,
) -> tuple[str, ...]:
    if resolver is not None:
        addresses = tuple(resolver(host, port))
    else:
        try:
            addresses = tuple(
                sorted({str(entry[4][0]) for entry in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
            )
        except socket.gaierror as error:
            raise SvcError("probe-address-unresolved", "Dev probe hostname could not be resolved.", {"host": host}) from error
    if not addresses:
        raise SvcError("probe-address-unresolved", "Dev probe hostname resolved to no addresses.", {"host": host})
    return addresses


def _enforce_address_scope(addresses: Iterable[str], network_scope: str) -> None:
    if network_scope == "remote":
        return
    non_loopback = [address for address in addresses if not ipaddress.ip_address(address).is_loopback]
    if non_loopback:
        raise SvcError(
            "remote-probe-not-allowed",
            "Dev probe resolves outside loopback without explicit remote scope.",
            {"addresses": non_loopback},
        )


def _network_error_reason(error: BaseException | None) -> str:
    if isinstance(error, (socket.timeout, TimeoutError, urllib3.exceptions.TimeoutError)):
        return "timeout"
    return "unreachable"
