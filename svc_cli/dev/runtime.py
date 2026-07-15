"""Bounded probes, provisioning, and per-capability dev-server coordination."""

from __future__ import annotations

import ipaddress
import http.client
import os
import signal
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from filelock import FileLock, Timeout
from platformdirs import user_runtime_dir

from ..config import ExecProbe, ExecProvision, HttpProbe, ManualProvision, TargetConfig, TcpProbe
from ..errors import SvcError
from .identity import (
    WorkspaceIdentity,
    interpolate_dev_argv,
    interpolate_dev_value,
    require_worktree_provenance,
    resolve_capability_identity,
    resolve_workspace_identity,
)


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


@dataclass
class Launch:
    process: subprocess.Popen[bytes]
    log_path: Path


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, connect_host: str, port: int, timeout: float) -> None:
        super().__init__(connect_host, port=port, timeout=timeout)
        self._connect_host = connect_host

    def connect(self) -> None:
        self.sock = socket.create_connection((self._connect_host, self.port), self.timeout, self.source_address)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, connect_host: str, port: int, server_hostname: str, context: ssl.SSLContext, timeout: float) -> None:
        super().__init__(server_hostname, port=port, context=context, timeout=timeout)
        self._connect_host = connect_host
        self._server_hostname = server_hostname

    def connect(self) -> None:
        self.sock = socket.create_connection((self._connect_host, self.port), self.timeout, self.source_address)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self._server_hostname)


def probe_target(
    target: TargetConfig,
    workspace: WorkspaceIdentity,
    *,
    profile: str,
    target_name: str,
    timeout: float | None = None,
) -> ProbeObservation:
    """Run exactly one configured readiness check without a shell or ambient proxy."""

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
    cwd = _resolve_cwd(workspace.root, probe.cwd, workspace, profile, target_name)
    return probe_exec(probe, argv, cwd, timeout=effective_timeout)


def probe_http(
    probe: HttpProbe,
    url: str,
    *,
    timeout: float,
    opener: Callable[[urllib.request.Request, float, ssl.SSLContext], object] | None = None,
    resolver: Callable[[str, int], Iterable[str]] | None = None,
) -> ProbeObservation:
    parsed = _validate_http_url(url)
    port = parsed.port or _default_port(parsed.scheme)
    addresses = _resolve_addresses(parsed.hostname or "", port, resolver)
    _enforce_address_scope(addresses, probe.network_scope)
    request = urllib.request.Request(url, method=probe.method)
    context = ssl._create_unverified_context() if probe.insecure_tls else ssl.create_default_context()
    try:
        if opener is not None:
            response = opener(request, timeout, context)
            try:
                raw_status = getattr(response, "status", None)
                status = int(raw_status if raw_status is not None else response.getcode())
            finally:
                response.close()
        else:
            status = _pinned_http_status(parsed, addresses, probe.method, timeout, context)
    except (urllib.error.URLError, OSError, ssl.SSLError, TimeoutError, http.client.HTTPException) as error:
        return ProbeObservation("http", False, _network_error_reason(error), url)
    lower, upper = probe.success_status
    return ProbeObservation("http", lower <= status <= upper, "accepted-status" if lower <= status <= upper else "unexpected-status", url, True, status)


def probe_tcp(
    probe: TcpProbe,
    host: str,
    *,
    timeout: float,
    resolver: Callable[[str, int], Iterable[str]] | None = None,
) -> ProbeObservation:
    addresses = tuple(_resolve_addresses(host, probe.port, resolver))
    _enforce_address_scope(addresses, probe.network_scope)
    endpoint = f"tcp://{host}:{probe.port}"
    last_error: OSError | None = None
    for address in addresses:
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        try:
            with socket.socket(family, socket.SOCK_STREAM) as connection:
                connection.settimeout(timeout)
                connection.connect((address, probe.port))
            return ProbeObservation("tcp", True, "connected", endpoint, True)
        except OSError as error:
            last_error = error
    return ProbeObservation("tcp", False, _network_error_reason(last_error), endpoint)


def probe_exec(probe: ExecProbe, argv: tuple[str, ...], cwd: Path, *, timeout: float) -> ProbeObservation:
    captured = bytearray()
    overflow = False
    try:
        process = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
    except OSError as error:
        return ProbeObservation("exec", False, "exec-start-failed", "exec:" + "\0".join(argv))

    assert process.stdout is not None

    def drain() -> None:
        nonlocal overflow
        while chunk := process.stdout.read(8_192):
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


def ensure_target(repo: Path, target_name: str, *, namespace: str | None = None) -> dict[str, object]:
    """Ensure a declared target once, without ever taking over an external process."""

    from ..config import ConfigError, load_config

    try:
        resolved = load_config(repo)
    except ConfigError as error:
        raise SvcError("invalid-project-configuration", "Cannot load declared dev configuration.", {"reason": str(error)}) from error
    if resolved.effective.dev is None:
        raise SvcError("dev-not-configured", "This project has no declared dev configuration.")
    profile = resolved.effective.dev.profile
    profile_config = resolved.effective.dev.profiles[profile]
    if target_name not in profile_config.targets:
        raise SvcError("unknown-dev-target", "The selected dev profile has no such target.", {"target": target_name, "profile": profile})
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
        raise SvcError(
            "occupied-unhealthy",
            "A declared endpoint responded but did not satisfy readiness; SVC will not take it over.",
            {**base, "status": "conflict"},
        )
    if isinstance(target.provision, ManualProvision):
        raise SvcError(
            "manual-action-required",
            "This target requires the consumer-declared manual provisioning action.",
            {**base, "status": "manual-action-required", "access": target.access},
        )

    deadline = time.monotonic() + target.readiness_timeout
    lock = FileLock(str(_runtime_root() / "locks" / f"{identity.lock_key}.lock"))
    lock_path = Path(lock.lock_file)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with lock.acquire(timeout=max(0.1, target.readiness_timeout)):
            remaining = _remaining(deadline)
            observed = probe_target(target, workspace, profile=profile, target_name=target_name, timeout=remaining)
            base = _result_base(resolved.effective_digest, workspace, identity, observed)
            if observed.healthy:
                return {**base, "status": "reused"}
            if observed.responded:
                raise SvcError(
                    "occupied-unhealthy",
                    "A declared endpoint responded but did not satisfy readiness; SVC will not take it over.",
                    {**base, "status": "conflict"},
                )
            launch = _provision(
                target.provision,
                workspace,
                profile,
                target_name,
                identity,
                timeout=_remaining(deadline),
            )
            if launch is None:
                return _wait_for_external_readiness(target, workspace, profile, target_name, deadline, base)
            with _cleanup_on_interrupt(launch, base):
                return _wait_for_owned_readiness(target, workspace, profile, target_name, deadline, base, launch)
    except Timeout as error:
        raise SvcError("dev-lock-timeout", "Timed out waiting for another ensure operation.", {**base, "status": "lock-timeout"}) from error


def inspect_dev_identity(repo: Path, *, namespace: str | None = None) -> dict[str, object]:
    workspace = resolve_workspace_identity(repo, namespace=namespace)
    return {"schema_version": 1, "command": "dev identity", "workspace": workspace.as_dict()}


def inspect_dev_status(repo: Path, target_name: str | None = None, *, namespace: str | None = None) -> dict[str, object]:
    """Observe declared targets only; status never starts or takes over a process."""

    from ..config import ConfigError, load_config

    try:
        resolved = load_config(repo)
    except ConfigError as error:
        return {"schema_version": 1, "command": "dev status", "healthy": False, "status": "invalid-configuration", "reason": str(error)}
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
            raise SvcError("unknown-dev-target", "The selected dev profile has no such target.", {"target": name, "profile": profile})
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
    healthy = bool(entries) and all(bool(entry.get("probe", {}).get("healthy")) for entry in entries)
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


def _provision(
    provision: ExecProvision,
    workspace: WorkspaceIdentity,
    profile: str,
    target_name: str,
    identity: object,
    *,
    timeout: float,
) -> Launch | None:
    argv = interpolate_dev_argv(provision.argv, workspace, profile=profile, target=target_name)
    cwd = _resolve_cwd(workspace.root, provision.cwd, workspace, profile, target_name)
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
    runtime = _runtime_root() / "logs"
    runtime.mkdir(parents=True, exist_ok=True)
    runtime_key = getattr(identity, "runtime_key")
    log_path = runtime / f"{runtime_key}-{int(time.time() * 1000)}.log"
    stream = log_path.open("ab")
    kwargs: dict[str, object] = {
        "cwd": cwd,
        "env": environment,
        "stdin": subprocess.DEVNULL,
        "stdout": stream,
        "stderr": subprocess.STDOUT,
        "shell": False,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(argv, **kwargs)
    except OSError as error:
        stream.close()
        raise SvcError("provision-start-failed", "The declared run command could not start.", {"log_path": str(log_path), "reason": str(error)}) from error
    stream.close()
    launch = Launch(process, log_path)
    if provision.mode == "run":
        return launch
    try:
        process.wait(timeout=max(0.01, timeout))
    except subprocess.TimeoutExpired as error:
        cleanup = _cleanup_launch(launch)
        raise SvcError(
            "activation-timeout",
            "The declared activation command did not finish before the readiness deadline.",
            {"log_path": str(log_path), "cleanup": cleanup},
        ) from error
    if process.returncode != 0:
        raise SvcError(
            "activation-failed",
            "The declared activation command failed.",
            {"log_path": str(log_path), "returncode": process.returncode},
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
        observed = probe_target(target, workspace, profile=profile, target_name=target_name, timeout=_remaining(deadline))
        if observed.healthy:
            return {**base, "probe": observed.as_dict(), "status": "started"}
        time.sleep(min(target.poll_interval, _remaining(deadline)))
    raise SvcError("readiness-timeout", "Activated target did not become ready before its deadline.", {**base, "status": "readiness-timeout"})


def _wait_for_owned_readiness(
    target: TargetConfig,
    workspace: WorkspaceIdentity,
    profile: str,
    target_name: str,
    deadline: float,
    base: dict[str, object],
    launch: Launch,
) -> dict[str, object]:
    while _remaining(deadline) > 0:
        if launch.process.poll() is not None:
            cleanup = _cleanup_launch(launch)
            raise SvcError(
                "provision-exited",
                "The SVC-started provisioner exited before readiness.",
                {**base, "status": "child-exit", "log_path": str(launch.log_path), "returncode": launch.process.returncode, "cleanup": cleanup},
            )
        observed = probe_target(target, workspace, profile=profile, target_name=target_name, timeout=_remaining(deadline))
        if observed.healthy:
            result = {
                **base,
                "probe": observed.as_dict(),
                "status": "started",
                "log_path": str(launch.log_path),
                "process_id": launch.process.pid,
            }
            _disown_launch(launch)
            return result
        time.sleep(min(target.poll_interval, _remaining(deadline)))
    cleanup = _cleanup_launch(launch)
    raise SvcError(
        "readiness-timeout",
        "SVC-started provisioner did not become ready before its deadline.",
        {**base, "status": "readiness-timeout", "log_path": str(launch.log_path), "cleanup": cleanup},
    )


def _cleanup_launch(launch: Launch) -> str:
    if launch.process.poll() is not None:
        return "completed"
    try:
        if os.name == "nt":
            completed = subprocess.run(
                ("taskkill", "/PID", str(launch.process.pid), "/T", "/F"),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                check=False,
            )
            if completed.returncode != 0:
                raise OSError("taskkill did not terminate the SVC-owned process tree")
        else:
            os.killpg(launch.process.pid, signal.SIGTERM)
        launch.process.wait(timeout=3)
        return "completed"
    except (OSError, subprocess.TimeoutExpired):
        try:
            if os.name == "nt":
                launch.process.kill()
            else:
                os.killpg(launch.process.pid, signal.SIGKILL)
            launch.process.wait(timeout=3)
            return "completed"
        except (OSError, subprocess.TimeoutExpired):
            return "unknown"


@contextmanager
def _cleanup_on_interrupt(launch: Launch, base: dict[str, object]):
    """Turn terminal interrupts into attempt-owned cleanup when this is the main thread."""

    if threading.current_thread() is not threading.main_thread():
        yield
        return
    signals = (signal.SIGINT, signal.SIGTERM)
    previous = {number: signal.getsignal(number) for number in signals}

    def interrupt(_number: int, _frame: object) -> None:
        raise KeyboardInterrupt

    try:
        for number in signals:
            signal.signal(number, interrupt)
        try:
            yield
        except KeyboardInterrupt as error:
            cleanup = _cleanup_launch(launch)
            raise SvcError(
                "ensure-interrupted",
                "Ensure was interrupted; SVC cleaned up only the launch it started in this attempt.",
                {**base, "status": "interrupted", "log_path": str(launch.log_path), "cleanup": cleanup},
            ) from error
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def _disown_launch(launch: Launch) -> None:
    """Release Python's child handle after readiness without retaining PID authority.

    A successful target is consumer infrastructure from this point on.  SVC keeps
    neither a process object nor a record that could authorize a later kill.
    CPython otherwise emits a resource warning while reaping this intentionally
    independent child during garbage collection.
    """

    if hasattr(launch.process, "_child_created"):
        launch.process._child_created = False  # type: ignore[attr-defined]


def _runtime_root() -> Path:
    return Path(user_runtime_dir("svc", ensure_exists=True))


def _result_base(effective_digest: str, workspace: WorkspaceIdentity, identity: object, observed: ProbeObservation) -> dict[str, object]:
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


def _pinned_http_status(
    parsed: urllib.parse.SplitResult,
    addresses: Iterable[str],
    method: str,
    timeout: float,
    context: ssl.SSLContext,
) -> int:
    port = parsed.port or _default_port(parsed.scheme)
    host_header = parsed.netloc
    path = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    last_error: BaseException | None = None
    for address in addresses:
        connection: http.client.HTTPConnection
        if parsed.scheme == "https":
            connection = _PinnedHTTPSConnection(address, port, parsed.hostname or "", context, timeout)
        else:
            connection = _PinnedHTTPConnection(address, port, timeout)
        try:
            connection.request(method, path, headers={"Host": host_header})
            response = connection.getresponse()
            try:
                return response.status
            finally:
                response.close()
        except (OSError, ssl.SSLError, TimeoutError, http.client.HTTPException) as error:
            last_error = error
        finally:
            connection.close()
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


def _resolve_addresses(host: str, port: int, resolver: Callable[[str, int], Iterable[str]] | None = None) -> tuple[str, ...]:
    if resolver is not None:
        addresses = tuple(resolver(host, port))
    else:
        try:
            addresses = tuple(sorted({entry[4][0] for entry in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}))
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
        raise SvcError("remote-probe-not-allowed", "Dev probe resolves outside loopback without explicit remote scope.", {"addresses": non_loopback})


def _resolve_cwd(root: Path, configured: str | None, workspace: WorkspaceIdentity, profile: str, target: str) -> Path:
    value = interpolate_dev_value(configured or ".", workspace, profile=profile, target=target)
    candidate = (root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise SvcError("dev-cwd-escapes-workspace", "Dev command working directory escapes the workspace.") from error
    if not candidate.is_dir():
        raise SvcError("dev-cwd-not-directory", "Dev command working directory does not exist.", {"cwd": value})
    return candidate


def _network_error_reason(error: BaseException | None) -> str:
    if isinstance(error, (socket.timeout, TimeoutError)):
        return "timeout"
    if error is None:
        return "unreachable"
    return "unreachable"
