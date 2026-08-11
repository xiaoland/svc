"""Operator runtime composition for one Issue-to-thread binding."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
import hashlib
import hmac
from pathlib import Path
from collections.abc import Callable
import time
import uuid

from aiohttp import ClientSession, ClientTimeout, web

from github_agent_bridge.app_server import (
    DEFAULT_PROVIDER_ENVIRONMENT_NAMES,
    AppServerClient,
    AppServerError,
    AppServerExited,
    AppServerProtocolError,
    AppServerRemoteError,
    provider_environment,
)
from github_agent_bridge.config import BridgeConfig, load_secret
from github_agent_bridge.github_api import GitHubApiError, GitHubAppClient
from github_agent_bridge.ingress import (
    IngressDependencies,
    create_health_app,
    create_ingress_app,
)
from github_agent_bridge.mirror_publisher import TurnMirrorPublisher
from github_agent_bridge.protocol_probe import inspect_protocol_identity
from github_agent_bridge.provider_adapter import CodexProviderAdapter
from github_agent_bridge.quick_tunnel import WranglerQuickTunnel
from github_agent_bridge.reconciliation import GitHubReconciler
from github_agent_bridge.store import (
    PROVIDER_DELIVERY_UNKNOWN_STATUS,
    Binding,
    StateConflict,
    TransportStore,
)
from github_agent_bridge.turn_controller import (
    BindingTurnController,
    ProviderTurnRecoveryPending,
)


class BridgeRuntimeError(RuntimeError):
    """A bounded operator-facing runtime failure."""


@dataclass(slots=True)
class RuntimeHealth:
    status: str = "starting"
    binding_id: str | None = None
    repository: str | None = None
    issue_number: int | None = None
    provider: str = "disconnected"
    reconciliation: str = "pending"
    last_turn_status: str | None = None
    last_mirror_error: str | None = None
    tunnel: str = "disabled"
    scheduler: str = "unknown"
    active_turn: bool = False
    provider_failures: int = 0
    provider_retry_at: float | None = None

    def snapshot(self) -> dict[str, object]:
        return {
            key: value
            for key, value in asdict(self).items()
            if value is not None
        }


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    binding_id: str
    thread_address: str
    public_webhook_url: str | None


PROVIDER_STABLE_SECONDS = 30.0


class ProviderConnectionSupervisor:
    """Mutable transport connection for one immutable Issue/thread binding."""

    def __init__(
        self,
        provider: CodexProviderAdapter,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._provider = provider
        self._clock = clock
        self._connected_at = clock()

    @property
    def thread_address(self) -> str:
        return self._provider.thread_address

    async def start_turn(self, events):
        return await self._provider.start_turn(events)

    async def steer_turn(self, turn_id, events) -> None:
        await self._provider.steer_turn(turn_id, events)

    async def next_message(self, *, timeout: float):
        return await self._provider.next_message(timeout=timeout)

    def persisted_turn_messages(self, turn_id: str):
        return self._provider.persisted_turn_messages(turn_id)

    def connected_seconds(self) -> float:
        return max(0.0, self._clock() - self._connected_at)

    async def next_transport_failure(self, *, timeout: float) -> AppServerError:
        return await asyncio.wait_for(
            self._provider.wait_terminated(), timeout=timeout
        )

    async def replace(self, provider: CodexProviderAdapter) -> None:
        previous = self._provider
        if provider.thread_address != previous.thread_address:
            try:
                await provider.close()
            except (AppServerError, OSError):
                pass
            raise AppServerProtocolError(
                "provider reconnect changed the opaque thread address"
            )
        self._provider = provider
        self._connected_at = self._clock()
        try:
            await previous.close()
        except (AppServerError, OSError):
            pass

    async def close(self) -> None:
        await self._provider.close()


async def serve_bridge(
    *,
    config: BridgeConfig,
    repository_full_name: str,
    issue_number: int,
    wrangler_executable: Path | None = None,
    stop_event: asyncio.Event | None = None,
    on_started: Callable[[RuntimeResult], None] | None = None,
) -> RuntimeResult:
    """Run until stopped; invoking with Wrangler mutates the App webhook URL."""

    if issue_number < 1:
        raise ValueError("issue_number must be positive")
    if not config.paths.provider_cwd.is_dir():
        raise BridgeRuntimeError("configured provider cwd is not a directory")
    if not config.paths.collaboration_instructions.is_file():
        raise BridgeRuntimeError(
            "configured project-scope collaboration instructions are unavailable"
        )
    instruction_digest = "sha256:" + hashlib.sha256(
        config.paths.collaboration_instructions.read_bytes()
    ).hexdigest()
    protocol_identity = await inspect_protocol_identity(
        codex_executable=config.app_server.executable
    )
    if (
        protocol_identity.app_server_version != config.app_server.version
        or protocol_identity.stable_schema_sha256
        != config.app_server.stable_schema_sha256
        or protocol_identity.experimental_schema_sha256
        != config.app_server.experimental_schema_sha256
    ):
        raise BridgeRuntimeError(
            "installed app-server does not match the configured protocol pin"
        )
    private_key = load_secret(config.github.private_key)
    webhook_secret = load_secret(config.github.webhook_secret)
    owner_id = f"wrapper-{uuid.uuid4()}"
    store = await TransportStore.open(config.paths.state_database)
    owner = await store.acquire_owner(owner_id, 30.0)
    app_server: AppServerClient | None = None
    provider: CodexProviderAdapter | None = None
    supervised_provider: ProviderConnectionSupervisor | None = None
    ingress_runner: web.AppRunner | None = None
    health_runner: web.AppRunner | None = None
    tunnel: WranglerQuickTunnel | None = None
    previous_webhook_url: str | None = None
    health = RuntimeHealth(
        repository=repository_full_name,
        issue_number=issue_number,
    )
    public_webhook_url: str | None = None
    stopping = stop_event if stop_event is not None else asyncio.Event()

    try:
        async with ClientSession(timeout=ClientTimeout(total=15.0)) as session:
            github = GitHubAppClient(
                session,
                app_id=config.github.app_id,
                private_key=private_key,
            )
            issue = await github.issue_reference(
                repository_full_name, issue_number
            )
            binding = await store.binding_for_issue(issue.issue_node_id)

            provider_names = DEFAULT_PROVIDER_ENVIRONMENT_NAMES.union(
                config.app_server.environment_allowlist
            )
            app_server = await AppServerClient.start(
                (
                    str(config.app_server.executable),
                    "app-server",
                    "--stdio",
                ),
                environment=provider_environment(names=frozenset(provider_names)),
            )
            if binding is None:
                provider = await CodexProviderAdapter.start_new(
                    app_server,
                    issue_url=issue.issue_url,
                    provider_cwd=config.paths.provider_cwd,
                    writable_roots=config.paths.provider_writable_roots,
                )
                binding = Binding(
                    binding_id=str(uuid.uuid4()),
                    repository_node_id=issue.repository_node_id,
                    repository_full_name=issue.repository_full_name,
                    issue_node_id=issue.issue_node_id,
                    issue_number=issue.issue_number,
                    issue_url=issue.issue_url,
                    thread_address=provider.thread_address,
                    agent_identity=config.github.agent_login,
                    wrapper_identity=config.github.wrapper_login,
                    trusted_permission="triage",
                    instruction_digest=instruction_digest,
                )
                await store.put_binding(owner, binding)
            else:
                _require_runtime_binding(
                    binding,
                    repository_full_name=repository_full_name,
                    issue_number=issue_number,
                    instruction_digest=instruction_digest,
                    agent_identity=config.github.agent_login,
                    wrapper_identity=config.github.wrapper_login,
                )
                provider = await CodexProviderAdapter.connect(
                    app_server,
                    binding=binding,
                    provider_cwd=config.paths.provider_cwd,
                    writable_roots=config.paths.provider_writable_roots,
                )
            supervised_provider = ProviderConnectionSupervisor(provider)
            health.binding_id = binding.binding_id
            health.provider = "connected"

            reconciler = GitHubReconciler(
                github,
                store,
                owner,
                self_logins=frozenset(
                    {config.github.agent_login, config.github.wrapper_login}
                ),
                quiet_window_seconds=config.timing.quiet_window_seconds,
            )
            await reconciler.reconcile_binding(binding)
            health.reconciliation = "current"

            mirror = TurnMirrorPublisher(
                github,
                store,
                owner,
                max_comment_bytes=config.timing.mirror_comment_bytes,
            )
            startup_scheduler = await store.scheduler_snapshot(binding.binding_id)
            if startup_scheduler.active_turn_handle is None:
                await store.restart_pending_quiet_window(
                    owner,
                    binding.binding_id,
                    observed_at=time.time(),
                    quiet_window_seconds=config.timing.quiet_window_seconds,
                )
            controller = BindingTurnController(
                store,
                owner,
                supervised_provider,
                mirror,
                mirror_interval_seconds=config.timing.mirror_interval_seconds,
            )
            ingress = create_ingress_app(
                IngressDependencies(
                    store=store,
                    owner_token=owner,
                    webhook_secret=webhook_secret,
                    self_logins=frozenset(
                        {config.github.agent_login, config.github.wrapper_login}
                    ),
                    quiet_window_seconds=config.timing.quiet_window_seconds,
                ),
                expose_health=False,
            )
            ingress_runner = web.AppRunner(ingress, access_log=None)
            await ingress_runner.setup()
            site = web.TCPSite(
                ingress_runner,
                str(config.ingress.host),
                config.ingress.port,
            )
            await site.start()
            health_runner = web.AppRunner(
                create_health_app(health.snapshot), access_log=None
            )
            await health_runner.setup()
            health_site = web.TCPSite(
                health_runner,
                str(config.ingress.host),
                config.ingress.health_port,
            )
            await health_site.start()

            if wrangler_executable is not None:
                origin = f"http://{config.ingress.host}:{config.ingress.port}"
                tunnel = await WranglerQuickTunnel.start(
                    wrangler_executable=wrangler_executable,
                    origin_url=origin,
                    environment=provider_environment(
                        names=frozenset({"HOME", "PATH"})
                    ),
                )
                previous = await github.webhook_configuration()
                previous_webhook_url = previous.url
                public_webhook_url = (
                    tunnel.public_url.rstrip("/") + "/webhooks/github"
                )
                await _verify_public_ingress(
                    session,
                    public_webhook_url,
                    webhook_secret=webhook_secret,
                )
                await github.update_webhook_configuration(
                    url=public_webhook_url,
                    webhook_secret=webhook_secret,
                )
                health.tunnel = "connected"

            health.status = "running"
            started = RuntimeResult(
                binding_id=binding.binding_id,
                thread_address=binding.thread_address,
                public_webhook_url=public_webhook_url,
            )
            if on_started is not None:
                on_started(started)
            tasks = [
                asyncio.create_task(
                    _lease_loop(store, owner, stopping), name="lease-renewal"
                ),
                asyncio.create_task(
                    _reconciliation_loop(
                        reconciler,
                        binding,
                        stopping,
                        interval_seconds=config.timing.reconciliation_interval_seconds,
                        health=health,
                    ),
                    name="github-reconciliation",
                ),
                asyncio.create_task(
                    _controller_loop(
                        controller,
                        supervised_provider,
                        reconciler,
                        store,
                        binding,
                        config,
                        stopping,
                        health,
                    ),
                    name="binding-turn-controller",
                ),
            ]
            if tunnel is not None:
                tasks.append(
                    asyncio.create_task(
                        _tunnel_watch(tunnel, stopping, health),
                        name="quick-tunnel-watch",
                    )
                )
            stop_wait = asyncio.create_task(
                stopping.wait(), name="runtime-stop-wait"
            )
            try:
                done, _ = await asyncio.wait(
                    (*tasks, stop_wait),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if stop_wait not in done:
                    for task in done:
                        task.result()
            finally:
                stop_wait.cancel()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(
                    stop_wait, *tasks, return_exceptions=True
                )
                health.status = "stopping"
                if previous_webhook_url is not None:
                    await github.update_webhook_configuration(
                        url=previous_webhook_url,
                        webhook_secret=webhook_secret,
                    )
            return started
    finally:
        if tunnel is not None:
            await tunnel.close()
        if ingress_runner is not None:
            await ingress_runner.cleanup()
        if health_runner is not None:
            await health_runner.cleanup()
        if supervised_provider is not None:
            await supervised_provider.close()
        elif provider is not None:
            await provider.close()
        elif app_server is not None:
            await app_server.close()
        try:
            await store.release_owner(owner)
        except Exception:
            pass
        await store.close()


async def _lease_loop(
    store: TransportStore,
    owner,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), 10.0)
        except TimeoutError:
            await store.renew_owner(owner, 30.0)


async def _reconciliation_loop(
    reconciler: GitHubReconciler,
    binding: Binding,
    stop_event: asyncio.Event,
    *,
    interval_seconds: float,
    health: RuntimeHealth,
) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), interval_seconds)
            continue
        except TimeoutError:
            pass
        try:
            await reconciler.reconcile_binding(binding)
        except GitHubApiError:
            health.reconciliation = "unavailable"
        else:
            health.reconciliation = "current"


async def _controller_loop(
    controller: BindingTurnController,
    provider: ProviderConnectionSupervisor,
    reconciler: GitHubReconciler,
    store: TransportStore,
    binding: Binding,
    config: BridgeConfig,
    stop_event: asyncio.Event,
    health: RuntimeHealth,
) -> None:
    while not stop_event.is_set():
        await reconciler.resolve_pending_permissions(binding)
        scheduler = await store.scheduler_snapshot(binding.binding_id)
        if scheduler.transport_status in {
            "starting",
            PROVIDER_DELIVERY_UNKNOWN_STATUS,
        }:
            health.status = "degraded"
            health.provider = "operator-required"
            health.scheduler = scheduler.transport_status
            health.active_turn = scheduler.active_turn_handle is not None
            await stop_event.wait()
            return
        try:
            if scheduler.active_turn_handle is None:
                result = await controller.run_one_ready_turn(binding)
            else:
                result = await controller.resume_active_turn(
                    binding,
                    active_turn_handle=scheduler.active_turn_handle,
                )
            if result is None:
                try:
                    failure = await provider.next_transport_failure(timeout=0.25)
                except TimeoutError:
                    failure = None
                if failure is not None:
                    raise failure
        except ProviderTurnRecoveryPending:
            scheduler = await store.scheduler_snapshot(binding.binding_id)
            health.status = "degraded"
            health.provider = "operator-required"
            health.scheduler = scheduler.transport_status
            health.active_turn = scheduler.active_turn_handle is not None
            await stop_event.wait()
            return
        except AppServerError as error:
            scheduler = await store.scheduler_snapshot(binding.binding_id)
            health.status = "degraded"
            health.provider = "unavailable"
            health.scheduler = scheduler.transport_status
            health.active_turn = scheduler.active_turn_handle is not None
            if _provider_error_requires_operator(error):
                health.provider = _provider_operator_status(error)
                await stop_event.wait()
                return
            if provider.connected_seconds() >= PROVIDER_STABLE_SECONDS:
                health.provider_failures = 0
            if not await _reconnect_provider(
                provider,
                config=config,
                binding=binding,
                stop_event=stop_event,
                health=health,
            ):
                if not stop_event.is_set():
                    await stop_event.wait()
                return
            continue
        scheduler = await store.scheduler_snapshot(binding.binding_id)
        health.scheduler = scheduler.transport_status
        health.active_turn = scheduler.active_turn_handle is not None
        if result is not None:
            health.last_turn_status = result.terminal_status
            health.last_mirror_error = result.mirror_error
            if result.mirror_error is not None and health.active_turn:
                try:
                    await asyncio.wait_for(
                        stop_event.wait(), config.timing.mirror_interval_seconds
                    )
                except TimeoutError:
                    pass
            continue
        continue


async def _reconnect_provider(
    supervisor: ProviderConnectionSupervisor,
    *,
    config: BridgeConfig,
    binding: Binding,
    stop_event: asyncio.Event,
    health: RuntimeHealth,
) -> bool:
    while not stop_event.is_set():
        delay = _provider_retry_delay(health.provider_failures)
        health.provider_failures += 1
        health.provider_retry_at = time.time() + delay
        try:
            await asyncio.wait_for(stop_event.wait(), delay)
            return False
        except TimeoutError:
            pass
        try:
            replacement = await _connect_existing_provider(config, binding)
        except (AppServerError, OSError) as error:
            if _provider_error_requires_operator(error):
                health.provider = _provider_operator_status(error)
                health.provider_retry_at = None
                return False
            continue
        await supervisor.replace(replacement)
        health.status = "running"
        health.provider = "connected"
        health.provider_retry_at = None
        return True
    return False


async def _connect_existing_provider(
    config: BridgeConfig,
    binding: Binding,
) -> CodexProviderAdapter:
    provider_names = DEFAULT_PROVIDER_ENVIRONMENT_NAMES.union(
        config.app_server.environment_allowlist
    )
    client = await AppServerClient.start(
        (
            str(config.app_server.executable),
            "app-server",
            "--stdio",
        ),
        environment=provider_environment(names=frozenset(provider_names)),
    )
    try:
        return await CodexProviderAdapter.connect(
            client,
            binding=binding,
            provider_cwd=config.paths.provider_cwd,
            writable_roots=config.paths.provider_writable_roots,
        )
    except BaseException:
        await client.close()
        raise


def _provider_error_requires_operator(error: BaseException) -> bool:
    if isinstance(error, AppServerProtocolError):
        return True
    if isinstance(error, AppServerRemoteError):
        return True
    return not isinstance(error, (AppServerExited, OSError))


def _provider_operator_status(error: BaseException) -> str:
    if isinstance(error, AppServerRemoteError) and isinstance(error.data, dict):
        candidates = (error.data, error.data.get("error"))
        if any(
            isinstance(candidate, dict)
            and candidate.get("codexErrorInfo") == "unauthorized"
            for candidate in candidates
        ):
            return "authentication-required"
    return "operator-required"


def _provider_retry_delay(consecutive_failures: int) -> float:
    if consecutive_failures < 0:
        raise ValueError("consecutive_failures must not be negative")
    return min(float(2 ** min(consecutive_failures, 5)), 30.0)


async def _tunnel_watch(
    tunnel: WranglerQuickTunnel,
    stop_event: asyncio.Event,
    health: RuntimeHealth,
) -> None:
    tunnel_wait = asyncio.create_task(tunnel.wait_terminated())
    stop_wait = asyncio.create_task(stop_event.wait())
    try:
        done, _ = await asyncio.wait(
            (tunnel_wait, stop_wait),
            return_when=asyncio.FIRST_COMPLETED,
        )
        if tunnel_wait in done and not stop_event.is_set():
            health.tunnel = "unavailable"
            await stop_event.wait()
    finally:
        tunnel_wait.cancel()
        stop_wait.cancel()
        await asyncio.gather(tunnel_wait, stop_wait, return_exceptions=True)


async def _verify_public_ingress(
    session: ClientSession,
    webhook_url: str,
    *,
    webhook_secret: bytes,
    attempts: int = 10,
) -> None:
    """Prove the public tunnel preserves signed bytes before mutating GitHub."""

    if attempts < 1:
        raise ValueError("attempts must be positive")
    body = b'{"hook_id":1,"zen":"wrapper ingress verification"}'
    signature = "sha256=" + hmac.new(
        webhook_secret, body, hashlib.sha256
    ).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Delivery": f"wrapper-probe-{uuid.uuid4()}",
        "X-GitHub-Event": "ping",
        "X-Hub-Signature-256": signature,
    }
    for attempt in range(attempts):
        try:
            async with session.post(
                webhook_url, data=body, headers=headers
            ) as response:
                payload = await response.json(content_type=None)
                if response.status == 202 and payload == {"outcome": "verified"}:
                    return
        except Exception:
            pass
        if attempt + 1 < attempts:
            await asyncio.sleep(1.0)
    raise BridgeRuntimeError(
        "public tunnel did not preserve the verified webhook ingress contract"
    )


def _require_runtime_binding(
    binding: Binding,
    *,
    repository_full_name: str,
    issue_number: int,
    instruction_digest: str,
    agent_identity: str,
    wrapper_identity: str,
) -> None:
    if (
        binding.repository_full_name != repository_full_name
        or binding.issue_number != issue_number
    ):
        raise StateConflict("local binding target does not match requested Issue")
    if binding.instruction_digest != instruction_digest:
        raise BridgeRuntimeError(
            "project-scope collaboration instructions changed; explicit rebind required"
        )
    if (
        binding.agent_identity.casefold() != agent_identity.casefold()
        or binding.wrapper_identity.casefold() != wrapper_identity.casefold()
    ):
        raise BridgeRuntimeError(
            "configured GitHub identities do not match durable binding"
        )
