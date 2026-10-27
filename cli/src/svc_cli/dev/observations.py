"""Independent named observations; checked time never refreshes provider data time."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal
from pydantic import JsonValue, ValidationError

from ..config import ExecProbe, HttpProbe, ObservationConfig
from ..errors import Failure, SvcError
from ..model import ValueModel
from .identity import interpolate_dev_argv, interpolate_dev_value
from .readiness import probe_http, probe_tcp, probe_exec, resolve_dev_cwd
from .resources import Resource
from .models import Observation, parse_json


class ProviderObservation(ValueModel):
    schema_version: Literal[1]
    state: Literal["satisfied", "unsatisfied", "unknown"]
    value: JsonValue = None
    message: str | None = None
    data_at: str | None = None
    instance: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def observe(resource: Resource, key: str, config: ObservationConfig) -> Observation:
    checked = datetime.now(timezone.utc)
    source = config.probe.kind
    base = dict(
        key=key,
        label=config.label or key,
        source=source,
        checked_at=checked.isoformat(),
    )
    try:
        probe = config.probe
        if isinstance(probe, HttpProbe):
            endpoint = interpolate_dev_value(
                probe.url, resource.workspace, target=resource.key
            )
            raw = probe_http(probe, endpoint, timeout=probe.timeout)
        elif isinstance(probe, ExecProbe):
            argv = interpolate_dev_argv(
                probe.argv, resource.workspace, target=resource.key
            )
            endpoint = "exec:" + "\0".join(argv)
            cwd = resolve_dev_cwd(
                resource.workspace.root, probe.cwd, resource.workspace, resource.key
            )
            raw = probe_exec(probe, argv, cwd, timeout=probe.timeout)
        else:
            host = interpolate_dev_value(
                probe.host, resource.workspace, target=resource.key
            )
            endpoint = f"tcp://{host}:{probe.port}"
            raw = probe_tcp(probe, host, timeout=probe.timeout)
        checked = datetime.now(timezone.utc)
        base["source"] = endpoint
        provider = None
        state: Literal["satisfied", "unsatisfied", "unknown"] = "unknown"
        if isinstance(probe, ExecProbe):
            if raw.output_truncated or raw.exit_code is None:
                raise ValueError(f"观察未完成：{raw.reason}")
            if probe.format == "json":
                if raw.exit_code != 0:
                    raise ValueError(f"JSON 观察命令退出 {raw.exit_code}")
                provider = ProviderObservation.model_validate(
                    parse_json(raw.output or "")
                )
                state = provider.state
            elif raw.exit_code in {0, 1}:
                state = "satisfied" if raw.exit_code == 0 else "unsatisfied"
            else:
                raise ValueError(f"观察命令退出 {raw.exit_code}")
        elif raw.responded:
            state = "satisfied" if raw.healthy else "unsatisfied"
        else:
            raise ValueError(f"无法判定：{raw.reason}")
        data_time = checked
        if provider and provider.data_at:
            data_time = datetime.fromisoformat(provider.data_at.replace("Z", "+00:00"))
            if data_time.tzinfo is None or data_time > checked:
                raise ValueError(
                    "provider data_at must include a timezone and cannot be in the future"
                )
        expires = data_time + timedelta(seconds=config.ttl)
        stale = expires < datetime.now(timezone.utc)
        instance = provider.instance if provider else None
        if (
            config.purpose == "runtime-readiness"
            and resource.coordination
            and resource.coordination.scope == "worktree"
        ):
            expected = resource.coordination.workspace_instance
            if instance is not None and instance != expected:
                raise ValueError("观察实例与所选协调工作树不一致")
            if instance is None:
                if expected not in endpoint:
                    raise ValueError("运行就绪观察没有工作树实例证明")
                instance = expected
        return Observation(
            key=key,
            label=config.label or key,
            source=base["source"],
            checked_at=checked.isoformat(),
            state=state,
            data_at=data_time.isoformat(),
            expires_at=expires.isoformat(),
            stale=stale,
            value=provider.value if provider else None,
            message=provider.message if provider else raw.reason,
            instance=instance,
        )
    except (SvcError, ValueError, ValidationError, OSError) as error:
        failure = (
            error.snapshot()
            if isinstance(error, SvcError)
            else Failure(code="observation-failed", message=str(error), details={})
        )
        return Observation(
            key=key,
            label=config.label or key,
            source=base["source"],
            checked_at=checked.isoformat(),
            state="unknown",
            error=failure,
            message=failure.message,
        )


def observe_resource(
    resource: Resource, keys: list[str] | None = None
) -> tuple[Observation, ...]:
    return tuple(
        observe(resource, key, facet)
        for key, facet in resource.config.observations.items()
        if (key in keys if keys is not None else facet.automatic)
    )


def satisfied(observations: tuple[Observation, ...]) -> bool:
    now = datetime.now(timezone.utc)
    return bool(observations) and all(
        x.state == "satisfied"
        and not x.stale
        and x.expires_at is not None
        and datetime.fromisoformat(x.expires_at) >= now
        for x in observations
    )
