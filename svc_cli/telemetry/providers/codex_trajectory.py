"""Bounded Codex rollout to ``svc.trajectory/v1`` translation.

This module owns provider field interpretation only. It deliberately does not
open files, retain a trajectory, or publish a bundle. The executable trajectory
schema owns its one shared format constant; ``CodexRolloutProvider`` supplies a
descriptor-bound stream and a sink, and the sink returns ``False`` when the
core has reached its record/trajectory bound.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import PurePosixPath
import re
from typing import Any, BinaryIO, Mapping, Sequence

from ...errors import SvcError
from ..agent_threads import (
    NormalizationResult,
    NormalizedRecordSink,
    NormalizationStatus,
    ResolvedThread,
    SourceStatus,
)
from ..trajectory import TRAJECTORY_SCHEMA


DEFAULT_BOUNDS: dict[str, int] = {
    "source_bytes": 256 * 1024 * 1024,
    "native_line_bytes": 4 * 1024 * 1024,
    "native_json_depth": 64,
    "records": 50_000,
    "message_context_code_points": 16_384,
    "reasoning_code_points": 8_192,
    "tool_name_code_points": 256,
    "tool_arguments_code_points": 20_000,
    "tool_result_code_points": 2_500,
    "workspace_label_code_points": 256,
    "context_attribute_code_points": 512,
    "tool_config_names": 256,
    "task_reference_code_points": 1_024,
    "task_reference_occurrences": 2_048,
    "diagnostics": 256,
}

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TOKEN = re.compile(r"(?<![A-Za-z0-9_./-])tasks/[^\s\x00<>\"'`\[\]{}()\\]+")
_TRAILING = ".,;:!?。！？；：、"
_RELATION_KEYS = {
    "turn": ("turn_ref", "turn_id", "turnId", "turn"),
    "actor": ("actor_ref", "actor_id", "actorId", "actor"),
    "parent": ("parent_actor_ref", "parent_actor_id", "parentActorId", "parent_actor"),
    "lane": ("lane_ref", "lane_id", "laneId", "lane"),
    "concurrency": ("concurrency_group", "concurrency_group_id", "concurrencyGroup"),
}
_CAPABILITIES = {
    "reasoning": "absent",
    "tool_linkage": "explicit",
    "context": "absent",
    "task_references": "available",
    "explicit_concurrency": "unavailable",
    "timestamps": "absent",
    "terminal_events": "unavailable",
}
_LOSS_KEYS = {
    "dropped": (
        "provider_envelope", "ui_event", "rate_limit_noise", "world_state",
        "duplicate_bookkeeping", "opaque_metadata", "unsupported_record",
        "invalid_json", "oversize_record", "excessive_json_depth",
        "duplicate_tool_result", "absolute_task_reference", "invalid_task_reference",
        "oversize_task_reference",
    ),
    "truncated": (
        "timestamp_precision", "workspace_label", "message", "context_content",
        "context_attribute", "reasoning", "tool_name", "tool_config_names",
        "tool_arguments", "tool_result", "task_references", "diagnostics",
    ),
    "unavailable": (
        "reasoning", "tool_linkage", "context", "task_references",
        "explicit_concurrency", "timestamps", "terminal_events",
    ),
    "synthesized": ("tool_call_id",),
    "partial_reasons": (
        "source_grew", "source_changed", "source_read_interrupted",
        "input_limit", "record_limit", "trajectory_limit",
    ),
}


def _empty_lossiness() -> dict[str, dict[str, int]]:
    return {name: {key: 0 for key in keys} for name, keys in _LOSS_KEYS.items()}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value: {value}")


def _json_loads(value: bytes | str) -> Any:
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return json.loads(
        value,
        object_pairs_hook=_reject_duplicate_pairs,
        parse_constant=_reject_constant,
    )


def _depth(value: Any, current: int = 1) -> int:
    if isinstance(value, dict):
        return max((current, *(_depth(child, current + 1) for child in value.values())))
    if isinstance(value, list):
        return max((current, *(_depth(child, current + 1) for child in value)))
    return current


def _sha(domain: bytes, value: bytes) -> str:
    return hashlib.sha256(domain + value).hexdigest()


def native_ref(kind: str, provider_id: str, value: str) -> str:
    domain = provider_id.encode() + b"\0" + kind.encode() + b"\0native\0"
    return f"{kind}_{_sha(domain, value.encode())}"


def synthetic_ref(kind: str, provider_id: str, event_index: int, component_index: int) -> str:
    marker = b"synthetic" if kind == "call" else b"orphan-result"
    domain = (
        provider_id.encode()
        + b"\0call\0"
        + marker
        + b"\0"
        + str(event_index).encode()
        + b"\0"
        + str(component_index).encode()
    )
    return f"call_{_sha(domain, b'')}"


def _bounded(value: Any, limit: int, strategy: str = "head_tail") -> tuple[str, dict[str, Any]]:
    text = value if isinstance(value, str) else str(value)
    observed = len(text)
    if observed <= limit:
        return text, {
            "truncated": False,
            "observed_code_points": observed,
            "retained_code_points": observed,
            "strategy": "none",
        }
    if strategy == "head":
        retained = text[:limit]
    else:
        head = (limit + 1) // 2
        retained = text[:head] + text[-(limit - head):]
    return retained, {
        "truncated": True,
        "observed_code_points": observed,
        "retained_code_points": len(retained),
        "strategy": strategy,
    }


def _timestamp(value: Any) -> tuple[str | None, bool]:
    if value is None:
        return None, False
    try:
        if isinstance(value, bool):
            raise ValueError
        original_fraction: str | None = None
        if isinstance(value, (int, float)):
            if not math.isfinite(float(value)):
                raise ValueError
            number = float(value)
            if abs(number) > 1_000_000_000_000:
                number /= 1000
            parsed = datetime.fromtimestamp(number, timezone.utc)
        elif isinstance(value, str):
            text = value.strip()
            fraction_match = re.search(r"\.([0-9]+)(?:Z|[+-][0-9]{2}:[0-9]{2})$", text)
            if fraction_match:
                original_fraction = fraction_match.group(1)
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            parsed = parsed.astimezone(timezone.utc)
        else:
            raise ValueError
        # Keep nanosecond precision even though ``datetime`` stores only
        # microseconds: the date/second comes from the parsed value and the
        # retained fractional text is normalized independently.
        rendered = parsed.replace(microsecond=0).isoformat(timespec="seconds").replace("+00:00", "Z")
        if original_fraction is None:
            micro = parsed.microsecond
            original_fraction = f"{micro:06d}" if micro else ""
        fraction = original_fraction[:9].rstrip("0")
        if fraction:
            rendered = rendered[:-1] + f".{fraction}Z"
        return rendered, True
    except (TypeError, ValueError, OverflowError, OSError):
        return None, False


def _timestamp_fraction_digits(value: Any) -> int:
    if not isinstance(value, str):
        return 0
    match = re.search(r"\.([0-9]+)(?:Z|[+-][0-9]{2}:[0-9]{2})$", value.strip())
    return len(match.group(1)) if match else 0


def _find(payload: Mapping[str, Any], keys: tuple[str, ...]) -> Any | None:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _payload_map(payload: Any) -> Mapping[str, Any]:
    return payload if isinstance(payload, Mapping) else {}


def _normalized_text(value: Any) -> str:
    """Render provider-visible structured text deterministically."""

    if isinstance(value, str):
        return value
    if isinstance(value, (Mapping, list)):
        return _canonical(value).decode("utf-8")
    return str(value)


def _relation(payload: Mapping[str, Any], kind: str, provider_id: str) -> str | None:
    passthrough = payload.get("internal_chat_message_metadata_passthrough")
    passthrough_map = passthrough if isinstance(passthrough, Mapping) else {}
    nested_keys = {
        "turn": ("turn_id", "turnId", "turn_ref"),
        "actor": ("author", "actor", "actor_id", "actorId"),
        "lane": ("recipient", "lane", "lane_id", "laneId"),
        "parent": ("parent_actor", "parent_actor_id", "parentActorId"),
        "concurrency": ("concurrency_group", "concurrency_group_id", "concurrencyGroup"),
    }
    value = _find(passthrough_map, nested_keys[kind])
    if value is None:
        value = _find(payload, _RELATION_KEYS[kind])
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        if kind not in {"actor", "lane"}:
            return None
        text = _canonical(value).decode("utf-8")
    else:
        text = str(value)
    if not text:
        return None
    ref_kind = "actor" if kind == "parent" else kind
    if text.startswith(f"{ref_kind}_") and _HEX64.fullmatch(text[len(ref_kind) + 1:]):
        return text
    return native_ref(ref_kind, provider_id, text)


def _relations(payload: Mapping[str, Any], provider_id: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for key in ("turn", "actor", "parent", "lane", "concurrency"):
        value = _relation(payload, key, provider_id)
        if value is not None:
            target = "parent_actor_ref" if key == "parent" else ("concurrency_group" if key == "concurrency" else f"{key}_ref")
            result[target] = value
    return result


def _known_ui_loss(marker: str, payload: Mapping[str, Any]) -> tuple[str, str] | None:
    """Classify known non-trajectory provider shapes without calling them unknown."""

    raw = str(payload.get("type") or payload.get("event") or payload.get("kind") or "").lower()
    text = f"{marker}:{raw}"
    if any(token in text for token in ("token_count", "rate_limit", "rate-limit")):
        return "rate_limit_noise", "rate_limit"
    if any(token in text for token in ("world_state", "world-state")):
        return "world_state", "world_state"
    if raw in {"task_started", "task_start", "task_complete", "task_completed", "turn_aborted", "context_compacted"}:
        return None
    if (marker.startswith("event_msg:") and any(token in text for token in ("user_message", "agent_message", "agent_reasoning"))) or any(token in text for token in ("thread_ui", "thread_activity", "thread_event", "thread_started", "thread_ended", "thread_name_updated", "thread_renamed", "thread_rolled_back", "inter-agent", "inter_agent", "inter_agent_activity", "interagent", "sub-agent", "sub_agent", "sub_agent_activity", "subagent", "agent_activity", "collab_activity")) or ("compacted" in text and raw not in {"context_compacted"}):
        return "ui_event", "ui"
    if any(token in text for token in ("duplicate", "bookkeeping")):
        return "duplicate_bookkeeping", "duplicate"
    return None


def _completion_kind(marker: str, payload: Mapping[str, Any]) -> bool:
    raw = str(payload.get("type") or payload.get("event") or payload.get("kind") or "").lower()
    text = f"{marker}:{raw}"
    return any(token in text for token in (
        "exec_command_end", "exec_command_completed", "patch_apply_end", "patch_apply_completed",
        "mcp_tool_call_end", "mcp_tool_call_completed", "collab_call_end", "collab_tool_call_end",
        "collab_completion", "sub_agent_end", "sub_agent_completed", "web_search_end",
        "collab_agent_spawn_end", "collab_waiting_end", "collab_agent_interaction_end",
    ))


def _completion_status(payload: Mapping[str, Any]) -> str:
    success = payload.get("success")
    if isinstance(success, bool):
        return "success" if success else "error"
    exit_code = payload.get("exit_code")
    if isinstance(exit_code, int) and not isinstance(exit_code, bool):
        return "success" if exit_code == 0 else "error"
    raw_value = _find(payload, ("status", "outcome", "result"))
    if isinstance(raw_value, Mapping):
        keys = {str(key).lower() for key in raw_value}
        if keys & {"err", "error", "failed", "failure", "aborted", "cancelled"}:
            return "error"
        if keys & {"ok", "success", "completed", "complete", "done"}:
            return "success"
        return "unknown"
    raw = str(raw_value or "").lower()
    if raw in {"success", "completed", "complete", "done", "ok"}:
        return "success"
    if raw in {"error", "failed", "failure", "aborted", "cancelled"}:
        return "error"
    return "unknown"


def _source_ref(event_index: int, line: int, component: str, component_index: int = 0) -> dict[str, Any]:
    # Both coordinates are frozen provider-stream coordinates, zero-based:
    # ``event_index`` counts physical JSONL events and ``line`` counts the
    # physical line containing the envelope/component.
    return {
        "event_index": event_index,
        "line": line,
        "component_index": component_index,
        "component": component,
    }


def _task_refs(
    text: str,
    *,
    reference_limit: int,
    occurrence_limit: int,
    retained_before: int,
    loss: dict[str, dict[str, int]],
) -> tuple[list[str], list[tuple[str, dict[str, Any]]]]:
    found: list[str] = []
    seen: set[str] = set()
    diagnostics: list[tuple[str, dict[str, Any]]] = []
    # Absolute roots are consumed before relative matching so an embedded
    # ``tasks/`` suffix can never be reinterpreted as a safe relative ref.
    absolute_pattern = re.compile(
        r"(?<![\w])(?:/|[A-Za-z]:[\\/]|\\\\|//)"
        r"[^\s<>\"'`\[\]{}()]*tasks[\\/][^\s<>\"'`\[\]{}()]*packet\.md"
    )
    uri_pattern = re.compile(
        r"(?<![\w])[A-Za-z][A-Za-z0-9+.-]*://"
        r"[^\s<>\"'`\[\]{}()]*tasks/[^\s<>\"'`\[\]{}()]*packet\.md"
    )
    invalid_backslash_pattern = re.compile(
        r"(?<![\w])tasks\\[^\s<>\"'`\[\]{}()]*packet\.md"
    )
    consumed = text
    # URI candidates contain a ``//`` substring that also resembles a UNC
    # root.  Classify the complete URI first, then classify filesystem roots,
    # so one candidate has exactly one frozen loss class.
    for invalid in uri_pattern.finditer(consumed):
        loss["dropped"]["invalid_task_reference"] += 1
        diagnostics.append(("invalid-task-reference-dropped", {}))
    consumed = uri_pattern.sub(" ", consumed)
    for absolute in absolute_pattern.finditer(consumed):
        loss["dropped"]["absolute_task_reference"] += 1
        diagnostics.append(("absolute-task-reference-dropped", {}))
    consumed = absolute_pattern.sub(" ", consumed)
    for invalid in invalid_backslash_pattern.finditer(consumed):
        loss["dropped"]["invalid_task_reference"] += 1
        diagnostics.append(("invalid-task-reference-dropped", {}))
    consumed = invalid_backslash_pattern.sub(" ", consumed)

    for match in _TOKEN.finditer(consumed):
        candidate = match.group(0).rstrip(_TRAILING)
        if len(candidate) > reference_limit:
            loss["dropped"]["oversize_task_reference"] += 1
            diagnostics.append(
                (
                    "task-reference-oversize-dropped",
                    {
                        "observed_code_points": len(candidate),
                        "retained_code_points": 0,
                    },
                )
            )
            continue
        try:
            path = PurePosixPath(candidate)
            if (
                path.is_absolute()
                or path.as_posix() != candidate
                or len(path.parts) < 3
                or path.parts[0] != "tasks"
                or path.parts[-1] != "packet.md"
                or any(part in {"", ".", ".."} for part in path.parts)
            ):
                raise ValueError
        except ValueError:
            loss["dropped"]["invalid_task_reference"] += 1
            diagnostics.append(("invalid-task-reference-dropped", {}))
            continue
        if candidate not in seen:
            found.append(candidate)
            seen.add(candidate)
    available = max(0, occurrence_limit - retained_before)
    if len(found) > available:
        observed = retained_before + len(found)
        omitted = len(found) - available
        found = found[:available]
        loss["truncated"]["task_references"] += omitted
        diagnostics.append(
            (
                "task-reference-limit-reached",
                {"observed_count": observed, "limit_count": occurrence_limit},
            )
        )
    return found, diagnostics


def _workspace(provider_id: str, payload: Mapping[str, Any], limit: int) -> dict[str, Any]:
    value = _find(payload, ("cwd", "workspace", "working_directory", "workingDirectory"))
    if not isinstance(value, str) or not value:
        return {
            "status": "missing", "flavor": None, "label": None, "ref": None,
            "label_truncated": False, "observed_code_points": 0, "retained_code_points": 0,
        }
    if value.startswith("\\\\") or value.startswith("//"):
        flavor = "unc"
    elif re.match(r"^[A-Za-z]:[\\/]", value):
        flavor = "windows"
    else:
        flavor = "posix"
    normalized = value.replace("\\", "/")
    label = normalized.rstrip("/").rsplit("/", 1)[-1] or normalized
    retained, metadata = _bounded(label, limit, "head")
    digest = _sha(provider_id.encode() + b"\0workspace\0" + flavor.encode() + b"\0", value.encode())
    return {
        "status": "present", "flavor": flavor, "label": retained, "ref": f"workspace_{digest}",
        "label_truncated": metadata["truncated"],
        "observed_code_points": metadata["observed_code_points"],
        "retained_code_points": metadata["retained_code_points"],
    }


class CodexTrajectoryNormalizer:
    """Translate one Codex rollout stream into bounded normalized records."""

    provider_id = "codex"
    adapter_id = "codex-rollout-v1"
    source_format = "rollout-v1"

    def normalize(
        self,
        stream: BinaryIO,
        resolved: ResolvedThread,
        sink: NormalizedRecordSink,
        bounds: Mapping[str, int] | None = None,
    ) -> NormalizationResult:
        effective = dict(DEFAULT_BOUNDS)
        if bounds:
            effective.update({key: int(value) for key, value in bounds.items() if isinstance(value, int) and not isinstance(value, bool) and value > 0})
        loss = _empty_lossiness()
        diagnostics: list[dict[str, Any]] = []
        diagnostic_keys: set[tuple[str, bytes]] = set()
        counts: dict[str, Any] = {
            "source_bytes_read": 0,
            "source_events_seen": 0,
            "records_emitted": 0,
            "trajectory_bytes": 0,
            "records_by_type": {kind: 0 for kind in ("meta", "message", "reasoning", "tool_call", "tool_result", "context", "event")},
            "messages_by_role": {"user": 0, "assistant": 0},
            "tool_calls": 0,
            "tool_results": 0,
            "task_references": 0,
            "diagnostics_emitted": 0,
            "diagnostics_suppressed": 0,
        }
        capabilities = dict(_CAPABILITIES)
        emitted = 0
        event_index = -1
        line_no = 0
        stopped = False
        call_occurrences: dict[str, int] = {}
        result_occurrences: dict[str, int] = {}
        completion_cache: dict[str, dict[str, Any]] = {}
        tool_call_count = 0
        explicit_tool_call_count = 0
        synthesized_tool_call_count = 0
        task_references_retained = 0
        saw_tool = False
        context_kinds: set[str] = set()
        saw_reasoning = False
        saw_valid_timestamp = False
        saw_invalid_timestamp = False
        saw_terminal = False
        saw_concurrency = False
        workspace = {"status": "missing", "flavor": None, "label": None, "ref": None, "label_truncated": False, "observed_code_points": 0, "retained_code_points": 0}
        initial_size = effective["source_bytes"]
        initial_extent = min(initial_size, effective["source_bytes"])
        remaining_extent = initial_extent
        input_limited = initial_size > effective["source_bytes"]

        def add_diagnostic(code: str, severity: str, action: str, source: dict[str, Any] | None, details: dict[str, Any] | None = None) -> None:
            nonlocal diagnostics
            detail = details or {}
            key = (code, _canonical(detail))
            if key in diagnostic_keys:
                for item in diagnostics:
                    if item["code"] == code and item["details"] == detail:
                        item["count"] += 1
                        return
            diagnostic_keys.add(key)
            diagnostics.append({"code": code, "severity": severity, "action": action, "count": 1, "record_ref": None, "source_ref": source, "details": detail})

        def emit(record: dict[str, Any]) -> bool:
            nonlocal emitted, stopped
            if emitted >= effective["records"]:
                loss["partial_reasons"]["record_limit"] += 1
                add_diagnostic(
                    "record-limit-reached",
                    "warning",
                    "partial",
                    record.get("source_ref"),
                    {
                        "observed_count": emitted + 1,
                        "limit_count": effective["records"],
                    },
                )
                stopped = True
                return False
            if not sink(record):
                loss["partial_reasons"]["record_limit"] += 1
                add_diagnostic(
                    "record-limit-reached",
                    "warning",
                    "partial",
                    record.get("source_ref"),
                    {
                        "observed_count": emitted + 1,
                        "limit_count": effective["records"],
                    },
                )
                stopped = True
                return False
            emitted += 1
            counts["records_emitted"] = emitted
            record_type = record["type"]
            counts["records_by_type"][record_type] += 1
            return True

        def read_initial_line() -> bytes:
            nonlocal remaining_extent
            if remaining_extent <= 0:
                return b""
            requested = min(
                effective["native_line_bytes"] + 1,
                remaining_extent,
            )
            raw = stream.readline(requested)
            remaining_extent -= len(raw)
            return raw

        # The meta record must be first, yet its workspace projection is
        # derived from the provider's leading session metadata.  Stage only
        # that first bounded line. Later appends are outside this initial
        # descriptor-bound extent and can never enter the trajectory.
        pending: tuple[bytes, int, int] | None = None
        try:
            first = read_initial_line()
        except OSError as error:
            raise SvcError("thread-source-unreadable", "Codex rollout source cannot be read.") from error
        if first:
            line_no = 1
            event_index = 0
            counts["source_bytes_read"] = len(first)
            counts["source_events_seen"] = 1
            pending = (first, line_no, event_index)
            try:
                first_value = _json_loads(first.rstrip(b"\r\n"))
                if isinstance(first_value, Mapping) and first_value.get("type") == "session_meta":
                    first_payload = _payload_map(first_value.get("payload"))
                    workspace = _workspace(self.provider_id, first_payload, effective["workspace_label_code_points"])
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
                pass

        thread_ref = native_ref("thread", self.provider_id, resolved.thread_id)
        meta_payload: dict[str, Any] = {
            "type": "meta", "record_id": "r000000", "record_index": 0,
            "timestamp": None, "source_ref": {"event_index": None, "component": "meta"},
            "trajectory_schema": TRAJECTORY_SCHEMA, "provider_id": self.provider_id,
            "adapter_id": self.adapter_id, "source_format": self.source_format,
            "thread_ref": thread_ref, "workspace": workspace,
            "content_profile": "bounded-normalized-v1",
        }
        if not emit(meta_payload):
            return self._result(resolved, thread_ref, workspace, capabilities, counts, loss, diagnostics)

        def common(kind: str, timestamp: str | None, source: dict[str, Any], payload: Mapping[str, Any], index: int) -> dict[str, Any]:
            record: dict[str, Any] = {
                "type": kind, "record_id": f"r{index:06d}", "record_index": index,
                "timestamp": timestamp, "source_ref": source,
            }
            record.update(_relations(payload, self.provider_id))
            return record

        def parse_component(value: Any, line: int, source: dict[str, Any]) -> None:
            nonlocal event_index, workspace, saw_tool, saw_reasoning, saw_valid_timestamp, saw_invalid_timestamp, saw_terminal, saw_concurrency, tool_call_count, explicit_tool_call_count, synthesized_tool_call_count, task_references_retained
            if stopped:
                return
            if not isinstance(value, Mapping):
                loss["dropped"]["unsupported_record"] += 1
                add_diagnostic("unsupported-record-dropped", "warning", "drop", source, {"record_type": "unknown"})
                return
            native_type = str(value.get("type", ""))
            payload = _payload_map(value.get("payload"))
            top_passthrough = value.get("internal_chat_message_metadata_passthrough")
            if isinstance(top_passthrough, Mapping) and "internal_chat_message_metadata_passthrough" not in payload:
                payload = dict(payload)
                payload["internal_chat_message_metadata_passthrough"] = top_passthrough
            inner_type = str(payload.get("type", ""))
            marker = f"{native_type}:{inner_type}".lower()
            loss["dropped"]["provider_envelope"] += 1
            add_diagnostic(
                "noise-record-dropped",
                "info",
                "drop",
                source,
                {"record_type": "envelope"},
            )
            if native_type == "session_meta":
                candidate = _find(payload, ("id", "thread_id", "threadId", "session_id", "sessionId"))
                if candidate is not None and str(candidate) != resolved.thread_id:
                    raise SvcError("thread-source-incompatible", "Rollout source identity changed during normalization.")
                workspace = _workspace(self.provider_id, payload, effective["workspace_label_code_points"])
                if workspace["label_truncated"]:
                    loss["truncated"]["workspace_label"] += 1
                    add_diagnostic("workspace-label-truncated", "info", "truncate", source, {"observed_code_points": workspace["observed_code_points"], "retained_code_points": workspace["retained_code_points"]})
                return
            timestamp, valid_timestamp = _timestamp(value.get("timestamp"))
            saw_valid_timestamp |= valid_timestamp
            fraction_digits = _timestamp_fraction_digits(value.get("timestamp"))
            if valid_timestamp and fraction_digits > 9:
                loss["truncated"]["timestamp_precision"] += 1
                add_diagnostic("timestamp-precision-truncated", "info", "truncate", source, {"observed_digits": fraction_digits, "retained_digits": 9})
            if value.get("timestamp") is not None and not valid_timestamp:
                saw_invalid_timestamp = True
                add_diagnostic("timestamp-invalid", "warning", "unavailable", source)
            if any(key in _relations(payload, self.provider_id) for key in ("lane_ref", "parent_actor_ref", "concurrency_group")):
                saw_concurrency = True
            if _completion_kind(marker, payload):
                raw_id = _find(payload, ("tool_call_id", "call_id", "callId", "id", "command_id", "commandId"))
                if raw_id is not None and str(raw_id):
                    completion_cache[str(raw_id)] = {
                        "status": _completion_status(payload),
                        "relations": _relations(payload, self.provider_id),
                    }
                loss["dropped"]["ui_event"] += 1
                add_diagnostic("noise-record-dropped", "info", "drop", source, {"record_type": "ui"})
                return
            known_loss = _known_ui_loss(marker, payload)
            if known_loss is not None:
                loss_key, record_type = known_loss
                loss["dropped"][loss_key] += 1
                add_diagnostic("noise-record-dropped", "info", "drop", source, {"record_type": record_type})
                return
            semantic_role = str(payload.get("role") or "").lower()
            is_message = "message" in marker or inner_type in {"agent_message", "user_message", "assistant_message"} or native_type in {"message", "assistant_message", "user_message", "event_msg"} and inner_type in {"agent_message", "user_message", "assistant_message", ""}
            if is_message and semantic_role not in {"developer", "system"}:
                role = str(payload.get("role", "")).lower()
                if role not in {"user", "assistant"}:
                    role = "assistant" if "assistant" in marker or "agent" in marker else "user"
                content_value = _find(payload, ("content", "text", "message"))
                if content_value is None:
                    content_value = ""
                full_content = content_value if isinstance(content_value, str) else json.dumps(content_value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                task_refs, task_diagnostics = _task_refs(
                    full_content,
                    reference_limit=effective["task_reference_code_points"],
                    occurrence_limit=effective["task_reference_occurrences"],
                    retained_before=task_references_retained,
                    loss=loss,
                )
                for code, details in task_diagnostics:
                    add_diagnostic(
                        code,
                        (
                            "warning"
                            if code in {
                                "task-reference-oversize-dropped",
                                "task-reference-limit-reached",
                            }
                            else "info"
                        ),
                        "truncate" if code == "task-reference-limit-reached" else "drop",
                        source,
                        details,
                    )
                task_references_retained += len(task_refs)
                content, content_meta = _bounded(full_content, effective["message_context_code_points"])
                if content_meta["truncated"]:
                    loss["truncated"]["message"] += 1
                    add_diagnostic("message-truncated", "info", "truncate", source, {"observed_code_points": content_meta["observed_code_points"], "retained_code_points": content_meta["retained_code_points"]})
                counts["task_references"] += len(task_refs)
                counts["messages_by_role"][role] += 1
                record = common("message", timestamp, source, payload, emitted)
                record.update({"role": role, "content": content, "content_meta": content_meta, "task_refs": task_refs})
                if not emit(record):
                    return
                return
            if "reason" in marker:
                saw_reasoning = True
                opaque = any(
                    key in payload
                    for key in (
                        "encrypted",
                        "encrypted_content",
                        "encrypted_reasoning",
                        "ciphertext",
                        "opaque",
                    )
                )
                raw = _find(payload, ("content", "summary", "text", "reasoning"))
                if raw is None:
                    if capabilities["reasoning"] == "absent":
                        capabilities["reasoning"] = "opaque"
                    loss["unavailable"]["reasoning"] += 1
                    add_diagnostic(
                        "reasoning-unavailable",
                        "info",
                        "unavailable",
                        source,
                        {"capability": "opaque"},
                    )
                    return
                if opaque:
                    # Codex can expose a plaintext summary beside an opaque
                    # full-reasoning payload. The summary is the strongest
                    # obtainable representation and remains valid evidence;
                    # the unavailable full representation is still declared.
                    loss["unavailable"]["reasoning"] += 1
                    add_diagnostic(
                        "reasoning-unavailable",
                        "info",
                        "unavailable",
                        source,
                        {"capability": "opaque"},
                    )
                content, content_meta = _bounded(raw, effective["reasoning_code_points"])
                if content_meta["truncated"]:
                    loss["truncated"]["reasoning"] += 1
                    add_diagnostic("reasoning-truncated", "info", "truncate", source, {"observed_code_points": content_meta["observed_code_points"], "retained_code_points": content_meta["retained_code_points"]})
                capabilities["reasoning"] = "summary"
                record = common("reasoning", timestamp, source, payload, emitted)
                record.update({"reasoning_kind": "summary", "content": content, "content_meta": content_meta})
                emit(record)
                return
            is_web_terminal = inner_type == "web_search_call" and str(payload.get("status") or "").lower() in {"completed", "complete", "failed", "error", "cancelled"}
            is_custom_call = inner_type in {"custom_tool_call", "tool_search_call", "web_search_call"} and not any(token in marker for token in ("output", "result", "end")) and not is_web_terminal
            if (any(token in marker for token in ("function_call", "functioncall", "custom_tool_call", "tool_call")) and not any(token in marker for token in ("output", "result"))) or is_custom_call:
                saw_tool = True
                tool_call_count += 1
                raw_id = _find(payload, ("tool_call_id", "call_id", "callId", "id"))
                if raw_id is None or not str(raw_id):
                    synthesized_tool_call_count += 1
                    loss["synthesized"]["tool_call_id"] += 1
                    call_id = synthetic_ref("call", self.provider_id, event_index, 0)
                    add_diagnostic("tool-call-id-synthesized", "warning", "synthesize", source, {"occurrence": 1})
                else:
                    explicit_tool_call_count += 1
                    base_id = native_ref("call", self.provider_id, str(raw_id))
                    occurrence = call_occurrences.get(base_id, 0) + 1
                    call_occurrences[base_id] = occurrence
                    call_id = base_id if occurrence == 1 else f"{base_id}_d{occurrence:06d}"
                    if occurrence > 1:
                        add_diagnostic("duplicate-tool-call-id", "warning", "synthesize", source, {"occurrence": occurrence})
                name_value = _find(payload, ("name", "tool_name", "toolName"))
                if name_value is None and isinstance(payload.get("function"), Mapping):
                    name_value = payload["function"].get("name")
                if name_value is None:
                    name_value = {"custom_tool_call": "custom_tool", "tool_search_call": "tool_search", "web_search_call": "web_search"}.get(inner_type)
                name, name_meta = _bounded(name_value or "unknown", effective["tool_name_code_points"], "head")
                if name_meta["truncated"]:
                    loss["truncated"]["tool_name"] += 1
                    add_diagnostic("tool-name-truncated", "info", "truncate", source, {"content_kind": "tool_call_name", "observed_code_points": name_meta["observed_code_points"], "retained_code_points": name_meta["retained_code_points"]})
                argument_value = _find(payload, ("arguments", "input", "parameters", "args"))
                arguments_kind = "absent"
                arguments: str | None = None
                arguments_fingerprint: str | None = None
                arguments_meta = {"truncated": False, "observed_code_points": 0, "retained_code_points": 0, "strategy": "none"}
                if argument_value is not None:
                    try:
                        parsed = _json_loads(argument_value) if isinstance(argument_value, str) else argument_value
                        arguments = _canonical(parsed).decode("utf-8")
                        arguments_kind = "json"
                    except (TypeError, ValueError, UnicodeDecodeError):
                        arguments = argument_value if isinstance(argument_value, str) else str(argument_value)
                        arguments_kind = "text"
                        add_diagnostic("tool-arguments-text", "info", "normalize", source, {"arguments_kind": "text"})
                    arguments_fingerprint = _sha(b"svc-tool-arguments-v1\0", arguments.encode("utf-8"))
                    arguments, arguments_meta = _bounded(arguments, effective["tool_arguments_code_points"])
                    if arguments_meta["truncated"]:
                        loss["truncated"]["tool_arguments"] += 1
                        add_diagnostic("tool-arguments-truncated", "info", "truncate", source, {"observed_code_points": arguments_meta["observed_code_points"], "retained_code_points": arguments_meta["retained_code_points"]})
                name_fingerprint = _sha(b"svc-tool-name-v1\0", str(name_value or "unknown").encode("utf-8"))
                record = common("tool_call", timestamp, source, payload, emitted)
                record.update({"tool_call_id": call_id, "name": name, "name_meta": name_meta, "name_fingerprint": name_fingerprint, "arguments_kind": arguments_kind, "arguments": arguments, "arguments_meta": arguments_meta, "arguments_fingerprint": arguments_fingerprint})
                emit(record)
                return
            is_custom_output = inner_type in {
                "custom_tool_call_output",
                "tool_search_call_output",
                "tool_search_output",
            }
            is_web_output = inner_type == "web_search_call" and (
                str(payload.get("status") or "").lower() in {"completed", "complete", "failed", "error", "cancelled"}
                or str(payload.get("action") or "").lower() in {"end", "completed"}
            )
            if any(token in marker for token in ("function_output", "function_call_output", "tool_result", "tool_output", "tool_result")) or is_custom_output or is_web_output:
                saw_tool = True
                raw_id = _find(payload, ("tool_call_id", "call_id", "callId", "id"))
                result_base_id: str | None
                result_explicit_occurrence: int | None
                if raw_id is None or not str(raw_id):
                    call_id = synthetic_ref("result", self.provider_id, event_index, 0)
                    result_base_id = None
                    result_explicit_occurrence = None
                else:
                    result_base_id = native_ref("call", self.provider_id, str(raw_id))
                    occurrence_value = _find(
                        payload,
                        ("call_occurrence", "callOccurrence", "occurrence"),
                    )
                    result_explicit_occurrence = (
                        occurrence_value
                        if isinstance(occurrence_value, int)
                        and not isinstance(occurrence_value, bool)
                        and occurrence_value >= 1
                        else None
                    )
                    call_id = (
                        result_base_id
                        if result_explicit_occurrence in (None, 1)
                        else f"{result_base_id}_d{result_explicit_occurrence:06d}"
                    )
                result_occurrence = result_occurrences.get(call_id, 0) + 1
                result_occurrences[call_id] = result_occurrence
                if result_occurrence > 1:
                    loss["dropped"]["duplicate_tool_result"] += 1
                    add_diagnostic(
                        "duplicate-tool-result",
                        "warning",
                        "drop",
                        source,
                        {"occurrence": result_occurrence},
                    )
                    return
                raw_content_value = _find(
                    payload,
                    ("content", "output", "result", "text", "execution"),
                )
                raw_content = (
                    ""
                    if raw_content_value is None
                    else _normalized_text(raw_content_value)
                )
                content, content_meta = _bounded(raw_content, effective["tool_result_code_points"])
                if content_meta["truncated"]:
                    loss["truncated"]["tool_result"] += 1
                    add_diagnostic("tool-result-truncated", "info", "truncate", source, {"observed_code_points": content_meta["observed_code_points"], "retained_code_points": content_meta["retained_code_points"]})
                cached_completion = completion_cache.get(str(raw_id)) if raw_id is not None else None
                status_raw = str(_find(payload, ("status", "outcome")) or "").lower()
                if (
                    cached_completion is not None
                    and cached_completion["status"] in {"success", "error"}
                ):
                    status_raw = str(cached_completion["status"])
                if status_raw in {"completed", "complete", "done", "ok"}:
                    status_raw = "success"
                elif status_raw in {"failed", "failure", "aborted", "cancelled"}:
                    status_raw = "error"
                if status_raw not in {"success", "error", "unknown"}:
                    status_raw = "error" if any(key in payload for key in ("error", "error_message", "exception")) else "unknown"
                record = common("tool_result", timestamp, source, payload, emitted)
                if cached_completion is not None and isinstance(cached_completion.get("relations"), Mapping):
                    record.update(cached_completion["relations"])
                realized_occurrences = (
                    call_occurrences.get(result_base_id, 0)
                    if result_base_id is not None
                    else 0
                )
                target_occurrence = result_explicit_occurrence or 1
                record.update({
                    "tool_call_id": call_id,
                    "content": content,
                    "content_meta": content_meta,
                    "status": status_raw,
                    "link_status": (
                        "linked"
                        if realized_occurrences >= target_occurrence
                        else "unresolved"
                    ),
                })
                counts["tool_results"] += 1
                emit(record)
                return
            context_kind = str(
                _find(payload, ("context_kind", "context_type"))
                or inner_type
                or native_type
            ).lower()
            if semantic_role in {"developer", "system"}:
                context_kind = semantic_role
            elif (
                context_kind in {
                    "turn_context",
                    "turn-context",
                    "thread_settings_applied",
                }
            ):
                context_kind = "turn"
            if context_kind in {"system", "developer", "tool_config", "turn"} or native_type == "context":
                if context_kind not in {"system", "developer", "tool_config", "turn"}:
                    context_kind = "turn"
                context_kinds.add(context_kind)
                context_content: str | None = None
                content_meta = {"truncated": False, "observed_code_points": 0, "retained_code_points": 0, "strategy": "none"}
                if isinstance(payload.get("context"), Mapping):
                    context_source = payload["context"]
                elif (
                    inner_type == "thread_settings_applied"
                    and isinstance(payload.get("thread_settings"), Mapping)
                ):
                    context_source = payload["thread_settings"]
                else:
                    context_source = payload
                if context_kind in {"system", "developer"}:
                    raw = _find(context_source, ("content", "text", "value"))
                    if raw is not None:
                        context_content, content_meta = _bounded(
                            _normalized_text(raw),
                            effective["message_context_code_points"],
                        )
                        if content_meta["truncated"]:
                            loss["truncated"]["context_content"] += 1
                            add_diagnostic("context-content-truncated", "info", "truncate", source, {"content_kind": context_kind, "observed_code_points": content_meta["observed_code_points"], "retained_code_points": content_meta["retained_code_points"]})
                attributes: dict[str, Any] = {}
                attrs_meta: dict[str, Any] = {}
                attribute_aliases = {
                    "model": (("model", None),),
                    "reasoning_effort": (
                        ("reasoning_effort", None),
                        ("effort", None),
                    ),
                    "approval_mode": (
                        ("approval_mode", None),
                        ("approval_policy", None),
                    ),
                    "sandbox_mode": (
                        ("sandbox_mode", None),
                        ("sandbox_policy", "type"),
                        ("permission_profile", "type"),
                        ("active_permission_profile", "id"),
                    ),
                    "collaboration_mode": (
                        ("collaboration_mode", "mode"),
                    ),
                }
                for key, aliases in attribute_aliases.items():
                    raw = None
                    for provider_key, nested_key in aliases:
                        candidate = context_source.get(provider_key)
                        if nested_key is not None:
                            candidate = (
                                candidate.get(nested_key)
                                if isinstance(candidate, Mapping)
                                else candidate
                            )
                        if candidate is not None and not isinstance(
                            candidate,
                            (Mapping, list),
                        ):
                            raw = candidate
                            break
                    if raw is not None:
                        retained, metadata = _bounded(raw, effective["context_attribute_code_points"], "head")
                        attributes[key] = retained
                        attrs_meta[key] = metadata
                        if metadata["truncated"]:
                            loss["truncated"]["context_attribute"] += 1
                            add_diagnostic("context-attribute-truncated", "info", "truncate", source, {"content_kind": key, "observed_code_points": metadata["observed_code_points"], "retained_code_points": metadata["retained_code_points"]})
                names = context_source.get("tool_names")
                if isinstance(names, list):
                    emitted_names: list[dict[str, Any]] = []
                    for item in sorted({str(item) for item in names})[: effective["tool_config_names"]]:
                        retained, metadata = _bounded(item, effective["tool_name_code_points"], "head")
                        emitted_names.append({"name": retained, "name_meta": metadata, "name_fingerprint": _sha(b"svc-tool-name-v1\0", item.encode())})
                    attributes["tool_names"] = emitted_names
                    attrs_meta["tool_names"] = {"observed_items": len(names), "retained_items": len(emitted_names), "truncated": len(set(map(str, names))) > len(emitted_names)}
                    if attrs_meta["tool_names"]["truncated"]:
                        loss["truncated"]["tool_config_names"] += 1
                        add_diagnostic("tool-config-name-limit-reached", "warning", "truncate", source, {"observed_count": len(set(map(str, names))), "limit_count": effective["tool_config_names"]})
                canonical_context = {"context_kind": context_kind, "content": context_content, "content_meta": content_meta, "attributes": attributes, "attributes_meta": attrs_meta}
                fingerprint = _sha(b"svc-context-v1\0", _canonical(canonical_context))
                record = common("context", timestamp, source, payload, emitted)
                record.update({"context_kind": context_kind, "content": context_content, "content_meta": content_meta, "attributes": attributes, "attributes_meta": attrs_meta, "fingerprint": fingerprint})
                emit(record)
                return
            event_kind = _event_kind(marker, payload)
            if event_kind is not None:
                saw_terminal |= event_kind in {"turn_start", "turn_complete", "turn_abort", "agent_start", "agent_complete", "error"}
                outcome = _event_outcome(event_kind, payload)
                record = common("event", timestamp, source, payload, emitted)
                record.update({"event_kind": event_kind, "outcome": outcome})
                emit(record)
                return
            loss["dropped"]["unsupported_record"] += 1
            add_diagnostic("unsupported-record-dropped", "warning", "drop", source, {"record_type": "unknown"})

        while not stopped:
            if pending is not None:
                raw, line_no, event_index = pending
                pending = None
            else:
                if remaining_extent <= 0:
                    if input_limited:
                        loss["partial_reasons"]["input_limit"] += 1
                        add_diagnostic(
                            "input-limit-reached",
                            "warning",
                            "partial",
                            None,
                            {
                                "observed_bytes": counts["source_bytes_read"],
                                "limit_bytes": effective["source_bytes"],
                            },
                        )
                    break
                try:
                    raw = read_initial_line()
                except OSError:
                    loss["partial_reasons"]["source_read_interrupted"] += 1
                    add_diagnostic(
                        "source-read-interrupted",
                        "error",
                        "partial",
                        (
                            _source_ref(
                                event_index + 1,
                                line_no,
                                "envelope",
                            )
                            if event_index >= 0
                            else None
                        ),
                    )
                    break
                if not raw:
                    break
                line_no += 1
                event_index += 1
                counts["source_bytes_read"] += len(raw)
                counts["source_events_seen"] += 1
            source = _source_ref(event_index, max(0, line_no - 1), "envelope")
            if len(raw) > effective["native_line_bytes"]:
                loss["dropped"]["oversize_record"] += 1
                add_diagnostic("record-oversize-dropped", "warning", "drop", source, {"observed_bytes": len(raw), "limit_bytes": effective["native_line_bytes"]})
                continue
            try:
                value = _json_loads(raw.rstrip(b"\r\n"))
                if _depth(value) > effective["native_json_depth"]:
                    raise RecursionError
                parse_component(value, line_no, source)
            except RecursionError:
                loss["dropped"]["excessive_json_depth"] += 1
                add_diagnostic("json-depth-exceeded", "warning", "drop", source, {"observed_depth": effective["native_json_depth"] + 1, "limit_depth": effective["native_json_depth"]})
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
                loss["dropped"]["invalid_json"] += 1
                add_diagnostic("invalid-json-line", "warning", "drop", source)

        if saw_tool:
            if explicit_tool_call_count and synthesized_tool_call_count:
                capabilities["tool_linkage"] = "mixed"
            elif synthesized_tool_call_count:
                capabilities["tool_linkage"] = "synthesized"
            else:
                capabilities["tool_linkage"] = "explicit"
            counts["tool_calls"] = tool_call_count
        if context_kinds:
            capabilities["context"] = (
                "full"
                if context_kinds == {"system", "developer", "tool_config", "turn"}
                else "partial"
            )
        if saw_reasoning and capabilities["reasoning"] == "absent":
            capabilities["reasoning"] = "opaque"
        if saw_valid_timestamp and saw_invalid_timestamp:
            capabilities["timestamps"] = "partial"
        elif saw_valid_timestamp:
            capabilities["timestamps"] = "full"
        elif saw_invalid_timestamp:
            capabilities["timestamps"] = "partial"
        if saw_terminal:
            capabilities["terminal_events"] = "available"
        if saw_concurrency:
            capabilities["explicit_concurrency"] = "available"
        if (
            loss["dropped"]["invalid_json"]
            or loss["dropped"]["oversize_record"]
            or loss["dropped"]["excessive_json_depth"]
            or loss["dropped"]["unsupported_record"]
            or loss["dropped"]["duplicate_tool_result"]
            or any(loss["partial_reasons"].values())
        ):
            result_status = NormalizationStatus.PARTIAL
        else:
            result_status = NormalizationStatus.READY
        missing_coordinate = 2**63 - 1
        diagnostics.sort(
            key=lambda item: (
                tuple(
                    (
                        item["source_ref"].get(key, missing_coordinate)
                        if isinstance(item["source_ref"], Mapping)
                        else missing_coordinate
                    )
                    for key in (
                        "event_index",
                        "line",
                        "byte_offset",
                        "component_index",
                    )
                ),
                str(item["code"]).encode("ascii"),
                _canonical(item["details"]),
            )
        )
        if len(diagnostics) > effective["diagnostics"]:
            regular_count = len(diagnostics)
            keep_count = max(0, effective["diagnostics"] - 1)
            suppressed = diagnostics[keep_count:]
            counts["diagnostics_suppressed"] = sum(int(item["count"]) for item in suppressed)
            diagnostics = diagnostics[:keep_count]
            loss["truncated"]["diagnostics"] = counts["diagnostics_suppressed"]
            diagnostics.append({"code": "diagnostic-limit-reached", "severity": "warning", "action": "truncate", "count": 1, "record_ref": None, "source_ref": None, "details": {"observed_count": regular_count, "limit_count": effective["diagnostics"]}})
        counts["diagnostics_emitted"] = sum(int(item["count"]) for item in diagnostics)
        return self._result(resolved, thread_ref, workspace, capabilities, counts, loss, diagnostics, result_status)

    def _result(self, resolved: ResolvedThread, thread_ref: str, workspace: Mapping[str, Any], capabilities: Mapping[str, str], counts: Mapping[str, Any], loss: Mapping[str, Any], diagnostics: Sequence[Mapping[str, Any]], result_status: NormalizationStatus = NormalizationStatus.READY) -> NormalizationResult:
        return NormalizationResult(
            provider_id=self.provider_id, adapter_id=self.adapter_id, source_format=self.source_format,
            thread_ref=thread_ref, workspace=workspace, source_status=SourceStatus.STABLE,
            result_status=result_status, capabilities=capabilities, counts=counts,
            lossiness=loss, diagnostics=tuple(diagnostics),
        )


def _event_kind(marker: str, payload: Mapping[str, Any]) -> str | None:
    raw = str(payload.get("event_kind") or payload.get("event") or payload.get("kind") or payload.get("type") or "").lower()
    aliases = {
        "task_started": "turn_start", "task_start": "turn_start", "task_complete": "turn_complete",
        "task_completed": "turn_complete", "turn_aborted": "turn_abort", "context_compacted": "compaction",
    }
    if raw in aliases:
        return aliases[raw]
    for candidate in ("turn_start", "turn_complete", "turn_abort", "agent_start", "agent_complete", "compaction", "approval", "error"):
        if candidate in marker or raw == candidate:
            return candidate
    return None


def _event_outcome(event_kind: str, payload: Mapping[str, Any]) -> str | None:
    raw = str(payload.get("outcome") or payload.get("status") or "").lower()
    if event_kind == "approval":
        return raw if raw in {"requested", "granted", "denied", "cancelled", "unknown"} else "unknown"
    if event_kind in {"turn_complete", "agent_complete"}:
        return raw if raw in {"completed", "error", "aborted", "unknown"} else "unknown"
    if event_kind == "turn_abort":
        return "aborted"
    if event_kind == "error":
        return "error"
    return None


__all__ = ["CodexTrajectoryNormalizer", "DEFAULT_BOUNDS", "native_ref"]
