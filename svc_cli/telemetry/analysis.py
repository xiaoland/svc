"""Pure deterministic projections for one validated normalized trajectory.

The module intentionally accepts only the already validated schema-v2 core
objects.  It never opens provider state, reads paths, uses wall-clock time, or
imports a renderer.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .trajectory import (
    RECORD_TYPES,
    TrajectoryError,
    ValidatedBundle,
    ValidatedTrajectory,
    canonical_json_bytes,
)


ANALYZER = {"name": "svc-agent-thread-analyzer", "version": 1, "method": "deterministic-v1"}
DIMENSIONS = (
    "task_evidence", "interaction_transitions", "constraint_evidence", "tool_outcomes",
    "loop_candidates", "lanes", "terminal_coverage", "svc_signals", "context_changes", "coverage",
)
FINDING_CODES = {
    "first-user-turn", "task-reference", "user-turn-boundary", "structured-approval", "context-established", "context-changed",
    "tool-success", "tool-error", "tool-unknown", "tool-pending", "tool-orphan", "tool-late-linked",
    "retry-group", "loop-candidate", "stall-candidate", "recovery-candidate", "explicit-lane", "explicit-parent-link",
    "terminal-status", "svc-task-reference", "svc-cli-call", "svc-test-call", "svc-build-call", "loss-observed",
}
UNKNOWN_CODES = {
    "user-evidence-unavailable", "transition-semantics-unavailable", "constraint-evidence-unavailable", "tool-linkage-unavailable",
    "turn-linkage-unavailable", "concurrency-unavailable", "terminal-evidence-unavailable", "svc-signal-unavailable",
    "context-evidence-unavailable", "coverage-partial", "evidence-conflict", "analysis-limit-reached",
}
_DIMENSION_ORDER = {name: index for index, name in enumerate(DIMENSIONS)}
_FINDING_DIMENSION = {
    "first-user-turn": "task_evidence", "task-reference": "task_evidence", "user-turn-boundary": "interaction_transitions",
    "structured-approval": "interaction_transitions", "context-established": "context_changes", "context-changed": "context_changes",
    "tool-success": "tool_outcomes", "tool-error": "tool_outcomes", "tool-unknown": "tool_outcomes", "tool-pending": "tool_outcomes",
    "tool-orphan": "tool_outcomes", "tool-late-linked": "tool_outcomes", "retry-group": "loop_candidates", "loop-candidate": "loop_candidates",
    "stall-candidate": "loop_candidates", "recovery-candidate": "loop_candidates", "explicit-lane": "lanes", "explicit-parent-link": "lanes",
    "terminal-status": "terminal_coverage", "svc-task-reference": "svc_signals", "svc-cli-call": "svc_signals",
    "svc-test-call": "svc_signals", "svc-build-call": "svc_signals", "loss-observed": "coverage",
}
_UNKNOWN_DIMENSION = {
    "user-evidence-unavailable": "task_evidence", "transition-semantics-unavailable": "interaction_transitions",
    "constraint-evidence-unavailable": "constraint_evidence", "tool-linkage-unavailable": "tool_outcomes",
    "turn-linkage-unavailable": "loop_candidates", "concurrency-unavailable": "lanes", "terminal-evidence-unavailable": "terminal_coverage",
    "svc-signal-unavailable": "svc_signals", "context-evidence-unavailable": "context_changes", "coverage-partial": "coverage",
    "evidence-conflict": "terminal_coverage", "analysis-limit-reached": None,
}
_LOSS_GROUPS = ("dropped", "truncated", "unavailable", "synthesized", "partial_reasons")
_LOSS_CLASS_KEYS = {
    "dropped": {"provider_envelope", "ui_event", "rate_limit_noise", "world_state", "duplicate_bookkeeping", "opaque_metadata", "unsupported_record", "invalid_json", "oversize_record", "excessive_json_depth", "duplicate_tool_result", "absolute_task_reference", "invalid_task_reference", "oversize_task_reference"},
    "truncated": {"timestamp_precision", "workspace_label", "message", "context_content", "context_attribute", "reasoning", "tool_name", "tool_config_names", "tool_arguments", "tool_result", "task_references", "diagnostics"},
    "unavailable": {"reasoning", "tool_linkage", "context", "task_references", "explicit_concurrency", "timestamps", "terminal_events"},
    "synthesized": {"tool_call_id"},
    "partial_reasons": {"source_grew", "source_changed", "source_displaced", "source_read_interrupted", "input_limit", "record_limit", "trajectory_limit"},
}
_ANALYSIS_LIMITS = ("finding", "unknown", "evidence_ref", "metric_entry", "byte")
_DETAIL_KEYS = {"status", "outcome", "signal_kind", "context_kind", "tool_name", "count", "truncated", "late_linked", "retry_count", "task_ref", "source_status", "result_status", "capability", "loss_class"}
_FINDING_DETAIL_KEYS = {
    "first-user-turn": set(),
    "task-reference": {"task_ref", "count"},
    "user-turn-boundary": set(),
    "structured-approval": {"outcome"},
    "context-established": {"context_kind"},
    "context-changed": {"context_kind"},
    "tool-success": {"tool_name", "status"},
    "tool-error": {"tool_name", "status"},
    "tool-unknown": {"tool_name", "status"},
    "tool-pending": {"tool_name", "status"},
    "tool-orphan": {"status"},
    "tool-late-linked": {"tool_name", "status", "late_linked"},
    "retry-group": {"tool_name", "retry_count"},
    "loop-candidate": {"tool_name", "retry_count"},
    "stall-candidate": {"tool_name", "retry_count"},
    "recovery-candidate": {"tool_name", "retry_count"},
    "explicit-lane": set(),
    "explicit-parent-link": set(),
    "terminal-status": {"status", "outcome"},
    "svc-task-reference": {"task_ref", "count", "signal_kind"},
    "svc-cli-call": {"signal_kind", "tool_name", "count"},
    "svc-test-call": {"signal_kind", "tool_name", "count"},
    "svc-build-call": {"signal_kind", "tool_name", "count"},
    "loss-observed": {"loss_class", "count"},
}
_UNKNOWN_DETAIL_KEYS = {
    "user-evidence-unavailable": set(), "transition-semantics-unavailable": set(), "constraint-evidence-unavailable": set(),
    "tool-linkage-unavailable": {"capability"}, "turn-linkage-unavailable": set(), "concurrency-unavailable": {"capability"},
    "terminal-evidence-unavailable": {"capability"}, "svc-signal-unavailable": {"capability"}, "context-evidence-unavailable": {"capability"},
    "coverage-partial": {"source_status", "result_status"}, "evidence-conflict": set(), "analysis-limit-reached": {"count", "truncated"},
}
_METRIC_KEYS = {
    "task_evidence": {"user_turn_count", "user_turn_refs", "task_references"},
    "interaction_transitions": {"boundary_count", "boundaries", "structured_approval_count"},
    "constraint_evidence": {"context_record_count", "task_reference_count", "structured_approval_count", "evidence_refs"},
    "tool_outcomes": {"calls", "results", "success", "error", "unknown", "pending", "orphan", "late_linked", "truncated_results", "retry_groups", "tools"},
    "loop_candidates": {"retry_group_count", "loop_candidate_count", "stall_candidate_count", "recovery_candidate_count", "groups"},
    "lanes": {"actor_count", "lane_count", "concurrency_group_count", "parent_link_count", "actors", "lanes", "concurrency_groups"},
    "terminal_coverage": {"status", "terminal_evidence_refs", "tail_loss"},
    "svc_signals": {"task_references", "svc_cli_calls", "test_calls", "build_calls", "signals"},
    "context_changes": {"context_records", "changes", "by_kind", "change_refs"},
    "coverage": {"records_total", "records_by_type", "messages_by_role", "timestamped_records", "untimestamped_records", "first_timestamp", "last_timestamp", "source_status", "bundle_result_status", "capabilities"},
}


class AnalysisError(ValueError):
    def __init__(self, code: str, message: str, details: Mapping[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = MappingProxyType(dict(details or {}))


@dataclass(frozen=True)
class AnalysisResult:
    payload: Mapping[str, object]
    json_bytes: bytes
    result_status: str
    bundle_id: str

    def as_dict(self) -> Mapping[str, object]:
        return self.payload


def canonical_analysis_bytes(value: Mapping[str, object], *, max_bytes: int = 2_097_152) -> bytes:
    try:
        data = canonical_json_bytes(value, newline=True)
    except TrajectoryError as error:
        raise AnalysisError("invalid-analysis", str(error)) from error
    if len(data) > max_bytes:
        raise AnalysisError("analysis-limit-reached", "Canonical analysis output exceeds its byte bound.")
    return data


def _trim_payload_for_bytes(payload: dict[str, object]) -> None:
    """Drop optional metric arrays as a last-resort byte-bound pass.

    Scalar counts, dimensions, findings, and the loss marker remain intact;
    only bounded previews are removed.  IDs are appended after the existing
    sequence, preserving the stable ordering of already retained evidence.
    """

    metrics = payload["metrics"]
    dimensions = payload["dimensions"]
    unknowns = payload["unknowns"]
    analysis_loss = payload["lossiness"]["analysis"]
    affected: list[tuple[str, int]] = []
    for dimension in DIMENSIONS:
        removed = 0
        metric = metrics[dimension]
        for key, value in list(metric.items()):
            if isinstance(value, list) and value:
                removed += len(value)
                metric[key] = []
        if removed:
            affected.append((dimension, removed))
            dimensions[dimension]["status"] = "partial"
    if not affected:
        raise AnalysisError("analysis-limit-reached", "Required analysis scalars exceed the canonical byte bound.")
    next_id = len(unknowns) + 1
    for dimension, count in affected:
        existing = next((item for item in unknowns if item["code"] == "analysis-limit-reached" and item["dimension"] == dimension), None)
        if existing is not None:
            existing["details"]["count"] += count
            continue
        if len(unknowns) >= 256:
            continue
        identifier = f"u{next_id:06d}"
        next_id += 1
        anchor = next((finding["evidence_refs"][0] for finding in payload["findings"] if finding["dimension"] == dimension and finding["evidence_refs"]), None)
        unknowns.append({"id": identifier, "dimension": dimension, "code": "analysis-limit-reached", "cause": "analysis_limit", "evidence_refs": [anchor] if anchor is not None else [], "details": {"count": count, "truncated": True}})
        dimensions[dimension]["unknown_ids"].append(identifier)
    payload["result_status"] = "partial"
    if "byte" not in analysis_loss["limits_reached"]:
        analysis_loss["limits_reached"].append("byte")
    analysis_loss["limits_reached"] = [item for item in _ANALYSIS_LIMITS if item in analysis_loss["limits_reached"]]
    analysis_loss["metric_entries_omitted"] += sum(count for _, count in affected)


def _error(message: str, **details: object) -> None:
    raise AnalysisError("invalid-analysis", message, details)


def _ref(bundle_id: str, record: Mapping[str, object]) -> dict[str, object]:
    return {"bundle_id": bundle_id, "record_id": record["record_id"], "record_index": record["record_index"]}


def _refs(bundle_id: str, records: Iterable[Mapping[str, object]], limit: int = 32) -> list[dict[str, object]]:
    values = sorted((_ref(bundle_id, item) for item in records), key=lambda item: (item["record_index"], item["record_id"]))
    if len(values) <= limit:
        return values
    if limit > 32:
        return values[:limit]
    head = limit // 2
    return values[:head] + values[-(limit - head):]


def _refs_outcomes(outcomes: list[str], limit: int = 32) -> list[str]:
    if len(outcomes) <= limit:
        return list(outcomes)
    head = limit // 2
    return outcomes[:head] + outcomes[-(limit - head):]


def _candidate_finding(code: str, records: Iterable[Mapping[str, object]], details: Mapping[str, object] | None = None, *, kind: str = "deterministic", confidence: str = "high") -> dict[str, object]:
    return {"dimension": _FINDING_DIMENSION[code], "code": code, "kind": kind, "confidence": confidence, "_records": tuple(records), "details": dict(details or {})}


def _candidate_unknown(code: str, records: Iterable[Mapping[str, object]], *, cause: str, details: Mapping[str, object] | None = None, dimension: str | None = None) -> dict[str, object]:
    target = dimension if code == "analysis-limit-reached" and dimension is not None else _UNKNOWN_DIMENSION[code]
    return {"dimension": target, "code": code, "cause": cause, "_records": tuple(records), "details": dict(details or {})}


def _record_key(record: Mapping[str, object]) -> tuple[int, str]:
    return int(record["record_index"]), str(record["record_id"])


def _loss_bundle(manifest: Mapping[str, object]) -> dict[str, object]:
    loss = manifest["lossiness"]
    source = manifest["source"]
    return {"mode": "bounded_normalized", "source_status": source["source_status"], "result_status": manifest["result_status"], **{group: dict(loss[group]) for group in _LOSS_GROUPS}}


def _apply_relevant_loss(
    statuses: dict[str, str],
    records: tuple[Mapping[str, object], ...],
    loss: Mapping[str, object],
    capabilities: Mapping[str, object],
    *,
    tail_loss: bool,
) -> None:
    """Apply the frozen loss-to-dimension matrix after projections exist."""

    has = {
        "task_evidence": any(record["type"] == "message" and record["role"] == "user" for record in records),
        "interaction_transitions": any(record["type"] == "message" and record["role"] == "user" for record in records) or any(record["type"] == "event" and record["event_kind"] == "approval" for record in records),
        "constraint_evidence": any(record["type"] == "context" for record in records) or any(record["type"] == "event" and record["event_kind"] == "approval" for record in records) or any(record.get("task_refs") for record in records if record["type"] == "message"),
        "tool_outcomes": any(record["type"] in {"tool_call", "tool_result"} for record in records),
        "loop_candidates": any(record["type"] == "tool_call" and "turn_ref" in record for record in records),
        "lanes": any(key in record for record in records for key in ("actor_ref", "parent_actor_ref", "lane_ref", "concurrency_group")),
        "terminal_coverage": any(record["type"] == "event" and record["event_kind"] in {"turn_start", "agent_start", "turn_complete", "turn_abort", "agent_complete", "error"} for record in records),
        "svc_signals": any(record["type"] == "tool_call" and record["arguments_kind"] in {"json", "text"} and record["arguments"] is not None for record in records) or any(record.get("task_refs") for record in records if record["type"] == "message"),
        "context_changes": any(record["type"] == "context" for record in records),
        "coverage": True,
    }
    affected: set[str] = set()
    if any(loss["partial_reasons"].values()) or any(loss["dropped"].get(key, 0) for key in ("unsupported_record", "invalid_json", "oversize_record", "excessive_json_depth")):
        affected.update(DIMENSIONS)
    if loss["dropped"].get("duplicate_tool_result", 0):
        affected.update({"tool_outcomes", "loop_candidates"})
    if (loss["dropped"].get("absolute_task_reference", 0) or loss["dropped"].get("invalid_task_reference", 0) or loss["dropped"].get("oversize_task_reference", 0) or loss["truncated"].get("task_references", 0) or loss["unavailable"].get("task_references", 0)):
        affected.update({"task_evidence", "constraint_evidence", "svc_signals"})
    if loss["truncated"].get("context_content", 0) or loss["truncated"].get("context_attribute", 0) or loss["truncated"].get("tool_config_names", 0) or capabilities["context"] == "partial":
        affected.update({"constraint_evidence", "context_changes"})
    if loss["truncated"].get("tool_name", 0):
        affected.update({"tool_outcomes", "loop_candidates", "svc_signals"})
    if loss["truncated"].get("tool_arguments", 0):
        affected.add("svc_signals")
    if loss["truncated"].get("tool_result", 0):
        affected.add("tool_outcomes")
    if capabilities["tool_linkage"] in {"mixed", "synthesized"} or loss["unavailable"].get("tool_linkage", 0) or loss["synthesized"].get("tool_call_id", 0):
        affected.update({"tool_outcomes", "loop_candidates"})
    if capabilities["explicit_concurrency"] == "unavailable":
        # This is an unavailable projection (and already has its unknown), not
        # a partial one, so it is intentionally omitted here.
        affected.discard("lanes")
    if capabilities["terminal_events"] == "unavailable":
        affected.discard("terminal_coverage")
    if tail_loss:
        affected.add("terminal_coverage")
    for dimension in affected:
        if has[dimension] and statuses[dimension] == "available":
            statuses[dimension] = "partial"


def _base_metrics(records: tuple[Mapping[str, object], ...]) -> dict[str, object]:
    by_type = {key: sum(record["type"] == key for record in records) for key in RECORD_TYPES}
    by_role = {role: sum(record.get("role") == role for record in records if record["type"] == "message") for role in ("user", "assistant")}
    timestamps = [record["timestamp"] for record in records if record["type"] != "meta" and record["timestamp"] is not None]
    return {"records_total": len(records), "records_by_type": by_type, "messages_by_role": by_role, "timestamped_records": len(timestamps), "untimestamped_records": len(records) - 1 - len(timestamps), "first_timestamp": timestamps[0] if timestamps else None, "last_timestamp": timestamps[-1] if timestamps else None}


def _retry_signature(call: Mapping[str, object]) -> str:
    """Return the frozen retry signature, including explicit absent arguments."""

    argument_component = (
        b"absent" if call["arguments_kind"] == "absent"
        else str(call["arguments_fingerprint"]).encode("ascii")
    )
    return hashlib.sha256(
        b"svc-tool-retry-v1\0"
        + str(call["name_fingerprint"]).encode("ascii")
        + b"\0" + argument_component
    ).hexdigest()


def _tool_analysis(records: tuple[Mapping[str, object], ...], bundle_id: str) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], dict[str, list[Mapping[str, object]]]]:
    calls = [record for record in records if record["type"] == "tool_call"]
    results = [record for record in records if record["type"] == "tool_result"]
    call_by_id: dict[str, list[Mapping[str, object]]] = {}
    for call in calls:
        # The first canonical call wins when a malformed external fixture has
        # repeated IDs; the trajectory normalizer normally suffixes duplicates.
        call_by_id.setdefault(str(call["tool_call_id"]), []).append(call)
    findings: list[dict[str, object]] = []
    linked: dict[str, list[Mapping[str, object]]] = {}
    status_counts = {"success": 0, "error": 0, "unknown": 0, "pending": 0, "orphan": 0, "late_linked": 0, "truncated_results": 0}
    tools: dict[str, dict[str, object]] = {}
    # The first structurally valid result is authoritative for each call ID.
    winners: dict[str, tuple[Mapping[str, object], Mapping[str, object], bool]] = {}
    for result in results:
        call_slots = call_by_id.get(str(result["tool_call_id"]), [])
        if not call_slots:
            status_counts["orphan"] += 1
            findings.append(_candidate_finding("tool-orphan", (result,), {"status": result["status"]}))
            continue
        call = call_slots[0]
        call_id = str(call["tool_call_id"])
        if call_id in winners:
            # Duplicate results remain represented by the root result count,
            # but cannot change the winning status or tool summary.
            continue
        late = result["link_status"] == "unresolved"
        winners[call_id] = (call, result, late)
        linked[call_id] = [result]
        key = str(call["name_fingerprint"])
        summary = tools.setdefault(key, {"name": call["name"], "name_fingerprint": key, "calls": 0, "results": 0, "success": 0, "error": 0, "unknown": 0, "pending": 0, "late_linked": 0, "truncated_results": 0, "retry_groups": 0, "first_evidence_ref": _ref(bundle_id, call)})
        summary["results"] += 1
        status = str(result["status"])
        status_counts[status] += 1
        summary[status] += 1
        if late:
            status_counts["late_linked"] += 1
            summary["late_linked"] += 1
            findings.append(_candidate_finding("tool-late-linked", (call, result), {"tool_name": call["name"], "status": status, "late_linked": True}))
        finding_code = {"success": "tool-success", "error": "tool-error", "unknown": "tool-unknown"}[status]
        findings.append(_candidate_finding(finding_code, (call, result), {"tool_name": call["name"], "status": status}))
        if result["content_meta"]["truncated"]:
            summary["truncated_results"] += 1
            status_counts["truncated_results"] += 1
    first_call_for_tool: dict[str, Mapping[str, object]] = {}
    for call in calls:
        key = str(call["name_fingerprint"])
        first_call_for_tool.setdefault(key, call)
        summary = tools.setdefault(key, {"name": call["name"], "name_fingerprint": key, "calls": 0, "results": 0, "success": 0, "error": 0, "unknown": 0, "pending": 0, "late_linked": 0, "truncated_results": 0, "retry_groups": 0, "first_evidence_ref": _ref(bundle_id, call)})
        summary["calls"] += 1
        if str(call["tool_call_id"]) not in winners:
            status_counts["pending"] += 1
            summary["pending"] += 1
            findings.append(_candidate_finding("tool-pending", (call,), {"tool_name": call["name"], "status": "pending"}))
    metrics = {
        "calls": len(calls), "results": len(results), **status_counts, "retry_groups": 0,
        "tools": sorted(tools.values(), key=lambda item: (_record_key(first_call_for_tool[item["name_fingerprint"]]), item["name_fingerprint"])),
    }
    return metrics, findings, [], linked


def _json_string_leaves(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _json_string_leaves(item)
    elif isinstance(value, Mapping):
        for key in sorted(value, key=lambda item: str(item).encode("utf-8")):
            yield from _json_string_leaves(value[key])


def _signal_matches(arguments: Iterable[str]) -> dict[str, int]:
    result = {"svc_cli": 0, "test": 0, "build": 0}
    commands = {"lookup", "status", "init", "adopt", "self-update", "dev", "telemetry"}
    patterns: list[tuple[tuple[str, ...], str]] = []
    for executable in ("svc", "svc.exe"):
        for command in sorted(commands):
            patterns.append(((executable, command), "svc_cli"))
            patterns.append((("pdm", "run", executable, command), "svc_cli"))
    patterns.extend([
        (("pdm", "run", "build-monolith"), "build"),
        (("pdm", "run", "test"), "test"),
        (("pdm", "build"), "build"),
    ])
    patterns.sort(key=lambda item: (-len(item[0]), item[0]))
    for text in arguments:
        tokens = re.findall(r"[A-Za-z0-9_.-]+", text)
        index = 0
        while index < len(tokens):
            for pattern, kind in patterns:
                if tuple(tokens[index:index + len(pattern)]) == pattern:
                    result[kind] += 1
                    index += len(pattern)
                    break
            else:
                index += 1
    return result


def _dimension(value: str, finding_ids: list[str], unknown_ids: list[str], status: str = "available") -> dict[str, object]:
    return {"status": status, "finding_ids": finding_ids, "unknown_ids": unknown_ids}


def _assign_ids(findings: list[dict[str, object]], unknowns: list[dict[str, object]], bundle_id: str) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, list[str]], dict[str, list[str]], int, int]:
    def coalesce(items: list[dict[str, object]]) -> list[dict[str, object]]:
        unique: dict[bytes, dict[str, object]] = {}
        for item in items:
            key = canonical_json_bytes({"dimension": item["dimension"], "code": item["code"], "details": item["details"], "records": sorted(_record_key(record) for record in item["_records"])})
            unique.setdefault(key, item)
        return list(unique.values())

    findings = coalesce(findings)
    unknowns = coalesce(unknowns)

    def sort_key(item: Mapping[str, object]) -> tuple[Any, ...]:
        records = sorted((_record_key(record) for record in item["_records"]), key=lambda value: value)
        first = records[0] if records else (10**9, "")
        details = canonical_json_bytes(item["details"])
        return first + (_DIMENSION_ORDER[item["dimension"]], str(item["code"]), details, tuple(records))
    findings = sorted(findings, key=sort_key)
    unknowns = sorted(unknowns, key=sort_key)
    findings_omitted = 0
    unknowns_omitted = 0
    omitted_by_dimension: dict[str, int] = {dimension: 0 for dimension in DIMENSIONS}
    retained_findings: list[dict[str, object]] = []
    for dimension in DIMENSIONS:
        candidates = [item for item in findings if item["dimension"] == dimension]
        retained_findings.extend(candidates[:25])
        omitted = max(0, len(candidates) - 25)
        findings_omitted += omitted
        omitted_by_dimension[dimension] += omitted
    findings = sorted(retained_findings, key=sort_key)
    if len(findings) > 256:
        findings_omitted += len(findings) - 256
        # Global retention is ordered by the same final sort key; associate
        # each removed candidate with its owning dimension for the reserved
        # limit unknown.
        for item in findings[256:]:
            omitted_by_dimension[item["dimension"]] += 1
        findings = findings[:256]
    for dimension, count in omitted_by_dimension.items():
        if count:
            unknowns.append(_candidate_unknown("analysis-limit-reached", (), cause="analysis_limit", dimension=dimension, details={"count": count, "truncated": True}))
    merged_limits: dict[str, dict[str, object]] = {}
    merged_unknowns: list[dict[str, object]] = []
    for item in unknowns:
        if item["code"] != "analysis-limit-reached":
            merged_unknowns.append(item)
            continue
        dimension = str(item["dimension"])
        prior = merged_limits.get(dimension)
        if prior is None:
            merged_limits[dimension] = item
        else:
            prior["details"]["count"] += item["details"]["count"]
            prior["_records"] = tuple(prior["_records"]) + tuple(item["_records"])
    unknowns = coalesce(merged_unknowns + list(merged_limits.values()))
    unknowns = sorted(unknowns, key=sort_key)
    retained_unknowns: list[dict[str, object]] = []
    for dimension in DIMENSIONS:
        candidates = [item for item in unknowns if item["dimension"] == dimension]
        if len(candidates) > 25:
            unknowns_omitted += len(candidates) - 24
            retained_unknowns.extend(candidates[:24])
            retained_unknowns.append(_candidate_unknown("analysis-limit-reached", candidates[24].get("_records", ()), cause="analysis_limit", dimension=dimension, details={"count": len(candidates) - 24, "truncated": True}))
        else:
            retained_unknowns.extend(candidates)
    merged_retained: dict[str, dict[str, object]] = {}
    non_limit_retained: list[dict[str, object]] = []
    for item in retained_unknowns:
        if item["code"] != "analysis-limit-reached":
            non_limit_retained.append(item)
            continue
        prior = merged_retained.get(str(item["dimension"]))
        if prior is None:
            merged_retained[str(item["dimension"])] = item
        else:
            prior["details"]["count"] += item["details"]["count"]
            prior["_records"] = tuple(prior["_records"]) + tuple(item["_records"])
    unknowns = sorted(non_limit_retained + list(merged_retained.values()), key=sort_key)
    if len(unknowns) > 256:
        unknowns_omitted += len(unknowns) - 256
        unknowns = unknowns[:256]
    finding_ids: dict[int, str] = {}
    output_findings: list[dict[str, object]] = []
    by_dimension_findings: dict[str, list[str]] = {dimension: [] for dimension in DIMENSIONS}
    for index, item in enumerate(findings, 1):
        identifier = f"f{index:06d}"
        finding_ids[id(item)] = identifier
        value = {"id": identifier, "dimension": item["dimension"], "code": item["code"], "kind": item["kind"], "confidence": item["confidence"], "evidence_refs": _refs(bundle_id, item["_records"]), "details": item["details"]}
        output_findings.append(value)
        by_dimension_findings[item["dimension"]].append(identifier)
    by_dimension_unknowns: dict[str, list[str]] = {dimension: [] for dimension in DIMENSIONS}
    output_unknowns: list[dict[str, object]] = []
    for index, item in enumerate(unknowns, 1):
        identifier = f"u{index:06d}"
        value = {"id": identifier, "dimension": item["dimension"], "code": item["code"], "cause": item["cause"], "evidence_refs": _refs(bundle_id, item["_records"]), "details": item["details"]}
        output_unknowns.append(value)
        by_dimension_unknowns[item["dimension"]].append(identifier)
    return output_findings, output_unknowns, by_dimension_findings, by_dimension_unknowns, findings_omitted, unknowns_omitted


def analyze_trajectory(source: ValidatedBundle, *, max_output_bytes: int = 2_097_152) -> AnalysisResult:
    if isinstance(source, ValidatedBundle):
        trajectory, manifest_value, bundle_id = source.trajectory, source.manifest, source.bundle_id
    else:
        _error("Analysis requires a validated schema-v2 bundle with manifest authority.")
    records = trajectory.records
    by_id = {record["record_id"]: record for record in records}
    if len(by_id) != len(records):
        _error("Trajectory contains duplicate record IDs.")
    loss = _loss_bundle(manifest_value)
    findings: list[dict[str, object]] = []
    unknowns: list[dict[str, object]] = []
    metrics: dict[str, object] = {}
    statuses: dict[str, str] = {dimension: "available" for dimension in DIMENSIONS}
    metric_omissions: dict[str, int] = {dimension: 0 for dimension in DIMENSIONS}
    evidence_ref_omissions: dict[str, int] = {dimension: 0 for dimension in DIMENSIONS}

    def bounded_refs(dimension: str, source_records: Iterable[Mapping[str, object]], limit: int) -> list[dict[str, object]]:
        ordered = sorted((_ref(bundle_id, item) for item in source_records), key=lambda item: (item["record_index"], item["record_id"]))
        if len(ordered) > limit:
            evidence_ref_omissions[dimension] += len(ordered) - limit
            if limit > 32:
                return ordered[:limit]
            head = limit // 2
            return ordered[:head] + ordered[-(limit - head):]
        return ordered

    def bounded_array(dimension: str, key: str, limit: int, *, evidence: bool = False) -> None:
        array = metrics[dimension][key]
        if len(array) <= limit:
            return
        omitted = len(array) - limit
        if evidence:
            evidence_ref_omissions[dimension] += omitted
            head = limit // 2
            metrics[dimension][key] = array[:head] + array[-(limit - head):]
        else:
            metric_omissions[dimension] += omitted
            metrics[dimension][key] = array[:limit]

    users = [record for record in records if record["type"] == "message" and record["role"] == "user"]
    task_counts: dict[str, tuple[int, Mapping[str, object]]] = {}
    for user_index, record in enumerate(users):
        if user_index == 0:
            findings.append(_candidate_finding("first-user-turn", (record,), {}))
        for task in record["task_refs"]:
            count, first = task_counts.get(task, (0, record))
            task_counts[task] = count + 1, first
    for task, (count, first) in task_counts.items():
        findings.append(_candidate_finding("task-reference", (first,), {"task_ref": task, "count": count}, kind="observed"))
        findings.append(_candidate_finding("svc-task-reference", (first,), {"task_ref": task, "count": count, "signal_kind": "task_reference"}, kind="observed"))
    if not users:
        unknowns.append(_candidate_unknown("user-evidence-unavailable", (), cause="missing"))
        statuses["task_evidence"] = "unavailable"
    metrics["task_evidence"] = {"user_turn_count": len(users), "user_turn_refs": bounded_refs("task_evidence", users, 2048), "task_references": [{"path": task, "occurrences": count, "first_evidence_ref": _ref(bundle_id, first)} for task, (count, first) in sorted(task_counts.items(), key=lambda item: (_record_key(item[1][1]), item[0].encode("utf-8")))]}

    actions = [record for record in records if (
        (record["type"] == "message" and record["role"] == "assistant")
        or record["type"] == "tool_call"
        or (record["type"] == "event" and record["event_kind"] in {"approval", "agent_start"})
    )]
    approvals = [record for record in records if record["type"] == "event" and record["event_kind"] == "approval"]
    boundaries = []
    for index, user in enumerate(users[1:], 1):
        prior = users[index - 1]
        before = [record for record in actions if _record_key(prior) < _record_key(record) < _record_key(user)]
        following_limit = users[index + 1] if index + 1 < len(users) else None
        after = [record for record in actions if _record_key(user) < _record_key(record) and (following_limit is None or _record_key(record) < _record_key(following_limit))]
        boundary = {"user_ref": _ref(bundle_id, user), "preceding_action_ref": _ref(bundle_id, before[-1]) if before else None, "following_action_ref": _ref(bundle_id, after[0]) if after else None, "approval_refs": bounded_refs("interaction_transitions", [item for item in approvals if _record_key(prior) < _record_key(item) < _record_key(user)], 32)}
        boundaries.append(boundary)
        findings.append(_candidate_finding("user-turn-boundary", (user,), {}))
    for approval in approvals:
        findings.append(_candidate_finding("structured-approval", (approval,), {"outcome": approval["outcome"]}, kind="observed"))
    if not boundaries and not approvals:
        unknowns.append(_candidate_unknown("transition-semantics-unavailable", (), cause="missing"))
        statuses["interaction_transitions"] = "unavailable"
    metrics["interaction_transitions"] = {"boundary_count": len(boundaries), "boundaries": boundaries, "structured_approval_count": len(approvals)}

    contexts = [record for record in records if record["type"] == "context"]
    constraint_refs = contexts + [record for record in users if record["task_refs"]] + approvals
    if not constraint_refs:
        unknowns.append(_candidate_unknown("constraint-evidence-unavailable", (), cause="missing"))
        statuses["constraint_evidence"] = "unavailable"
    metrics["constraint_evidence"] = {"context_record_count": len(contexts), "task_reference_count": sum(len(record["task_refs"]) for record in users), "structured_approval_count": len(approvals), "evidence_refs": bounded_refs("constraint_evidence", constraint_refs, 2048)}

    tool_metrics, tool_findings, _, linked_results = _tool_analysis(records, bundle_id)
    findings.extend(tool_findings)
    if manifest_value["capabilities"]["tool_linkage"] == "absent":
        unknowns.append(_candidate_unknown("tool-linkage-unavailable", (), cause="capability", details={"capability": "tool_linkage"}))
        statuses["tool_outcomes"] = "unavailable"
    metrics["tool_outcomes"] = tool_metrics

    calls = [record for record in records if record["type"] == "tool_call"]
    missing_turn_calls = [call for call in calls if "turn_ref" not in call]
    if missing_turn_calls:
        unknowns.append(_candidate_unknown("turn-linkage-unavailable", missing_turn_calls[:32], cause="missing"))
        statuses["loop_candidates"] = "partial" if len(missing_turn_calls) < len(calls) else "unavailable"
    groups: dict[tuple[object, ...], list[Mapping[str, object]]] = {}
    for call in calls:
        if "turn_ref" not in call:
            continue
        key = (call["turn_ref"], call.get("lane_ref"), _retry_signature(call))
        groups.setdefault(key, []).append(call)
    loop_groups: list[dict[str, object]] = []
    stall_count = 0
    recovery_count = 0
    for key, group in groups.items():
        if len(group) < 2:
            continue
        outcomes: list[str] = []
        for call in group:
            result = linked_results.get(str(call["tool_call_id"]), [])
            outcomes.append(result[0]["status"] if result else "pending")
        name = group[0]["name"]
        common = {"tool_name": name, "name_fingerprint": group[0]["name_fingerprint"], "call_count": len(group), "first_evidence_ref": _ref(bundle_id, group[0]), "last_evidence_ref": _ref(bundle_id, group[-1]), "outcomes": _refs_outcomes(outcomes)}
        loop_groups.append({"kind": "retry", **common})
        findings.append(_candidate_finding("retry-group", (group[0], group[-1]), {"tool_name": name, "retry_count": len(group) - 1}))
        if len(group) >= 3:
            loop_groups.append({"kind": "loop", **common})
            findings.append(_candidate_finding("loop-candidate", (group[0], group[-1]), {"tool_name": name, "retry_count": len(group) - 1}, kind="heuristic", confidence="medium"))
            if outcomes[-1] in {"error", "unknown", "pending"} and "success" not in outcomes:
                stall_count += 1
                loop_groups.append({"kind": "stall", **common})
                findings.append(_candidate_finding("stall-candidate", (group[0], group[-1]), {"tool_name": name, "retry_count": len(group) - 1}, kind="heuristic", confidence="medium"))
        if len(group) >= 2 and "error" in outcomes and "success" in outcomes and outcomes.index("error") < outcomes.index("success"):
            loop_groups.append({"kind": "recovery", **common})
            recovery_count += 1
            findings.append(_candidate_finding("recovery-candidate", (group[0], group[-1]), {"tool_name": name, "retry_count": len(group) - 1}, kind="heuristic", confidence="medium"))
    kind_order = {"retry": 0, "recovery": 1, "loop": 2, "stall": 3}
    loop_groups.sort(key=lambda item: (_record_key(next(call for call in calls if call["record_id"] == item["first_evidence_ref"]["record_id"])), _record_key(next(call for call in calls if call["record_id"] == item["last_evidence_ref"]["record_id"])), kind_order[item["kind"]], item["name_fingerprint"]))
    retry_group_count = sum(item["kind"] == "retry" for item in loop_groups)
    loop_candidate_count = sum(item["kind"] == "loop" for item in loop_groups)
    for summary in metrics["tool_outcomes"]["tools"]:
        summary["retry_groups"] = sum(item["kind"] == "retry" and item["name_fingerprint"] == summary["name_fingerprint"] for item in loop_groups)
    metrics["loop_candidates"] = {"retry_group_count": retry_group_count, "loop_candidate_count": loop_candidate_count, "stall_candidate_count": stall_count, "recovery_candidate_count": recovery_count, "groups": loop_groups}
    metrics["tool_outcomes"]["retry_groups"] = retry_group_count

    actor_refs = sorted({record[key] for record in records for key in ("actor_ref", "parent_actor_ref") if key in record})
    lane_refs = sorted({record["lane_ref"] for record in records if "lane_ref" in record})
    concurrency_refs = sorted({record["concurrency_group"] for record in records if "concurrency_group" in record})
    parent_pairs = sorted({(record["actor_ref"], record["parent_actor_ref"]) for record in records if "actor_ref" in record and "parent_actor_ref" in record})
    for lane in lane_refs:
        first = next(record for record in records if record.get("lane_ref") == lane)
        findings.append(_candidate_finding("explicit-lane", (first,), {} , kind="observed"))
    for actor, parent in parent_pairs:
        first = next(record for record in records if record.get("actor_ref") == actor and record.get("parent_actor_ref") == parent)
        findings.append(_candidate_finding("explicit-parent-link", (first,), {}, kind="observed"))
    if manifest_value["capabilities"]["explicit_concurrency"] == "unavailable":
        unknowns.append(_candidate_unknown("concurrency-unavailable", (), cause="capability", details={"capability": "explicit_concurrency"}))
        statuses["lanes"] = "unavailable"
    metrics["lanes"] = {"actor_count": len(actor_refs), "lane_count": len(lane_refs), "concurrency_group_count": len(concurrency_refs), "parent_link_count": len(parent_pairs), "actors": actor_refs, "lanes": lane_refs, "concurrency_groups": concurrency_refs}

    terminal = [record for record in records if record["type"] == "event" and record["event_kind"] in {"turn_complete", "turn_abort", "agent_complete", "error"}]
    starts = [record for record in records if record["type"] == "event" and record["event_kind"] in {"turn_start", "agent_start"}]
    terminal_refs = bounded_refs("terminal_coverage", starts + terminal, 32)
    tail_loss = any(loss["partial_reasons"].values()) or any(loss["dropped"].get(key, 0) for key in ("unsupported_record", "invalid_json", "oversize_record", "excessive_json_depth"))
    if manifest_value["capabilities"]["terminal_events"] == "unavailable":
        status = "unknown"
        unknowns.append(_candidate_unknown("terminal-evidence-unavailable", (), cause="capability", details={"capability": "terminal_events"}))
        statuses["terminal_coverage"] = "unavailable"
    elif terminal:
        by_source: dict[bytes, list[Mapping[str, object]]] = {}
        for candidate in terminal:
            by_source.setdefault(canonical_json_bytes(candidate["source_ref"]), []).append(candidate)
        conflicting = next((group for group in by_source.values() if len({(item["event_kind"], item["outcome"]) for item in group}) > 1), None)
        if conflicting is not None:
            status = "unknown"
            unknowns.append(_candidate_unknown("evidence-conflict", conflicting, cause="conflict"))
            unknowns.append(_candidate_unknown("terminal-evidence-unavailable", conflicting, cause="ambiguity"))
            statuses["terminal_coverage"] = "unavailable"
            metrics["terminal_coverage"] = {"status": status, "terminal_evidence_refs": terminal_refs, "tail_loss": tail_loss}
            # Continue with the remaining projections; terminal status is
            # intentionally not emitted for a contradictory source position.
            terminal = []
        else:
            winner = terminal[-1]
            if winner["event_kind"] == "turn_abort" or winner["outcome"] == "aborted": status = "aborted"
            elif winner["outcome"] == "completed": status = "completed"
            elif winner["outcome"] == "error" or winner["event_kind"] == "error": status = "error"
            else: status = "unknown"
            findings.append(_candidate_finding("terminal-status", (winner,), {"status": status, "outcome": winner["outcome"]}, kind="deterministic"))
            if status == "unknown":
                unknowns.append(_candidate_unknown("terminal-evidence-unavailable", (winner,), cause="ambiguity"))
    elif starts:
        status = "open"
        findings.append(_candidate_finding("terminal-status", (starts[-1],), {"status": status, "outcome": None}, kind="deterministic"))
    else:
        status = "unknown"
        unknowns.append(_candidate_unknown("terminal-evidence-unavailable", (), cause="loss" if tail_loss else "missing"))
        statuses["terminal_coverage"] = "unavailable"
    metrics["terminal_coverage"] = {"status": status, "terminal_evidence_refs": terminal_refs, "tail_loss": tail_loss}

    signal_findings: list[dict[str, object]] = []
    signals = []
    if task_counts:
        first_task_record = min((first for _, first in task_counts.values()), key=_record_key)
        signals.append({"kind": "task_reference", "count": sum(count for count, _ in task_counts.values()), "first_evidence_ref": _ref(bundle_id, first_task_record)})
    for record in calls:
        if record["arguments"] is None:
            continue
        if record["arguments_meta"]["truncated"] and record["arguments_kind"] == "json":
            # A retained JSON preview is intentionally not parsed or scanned.
            continue
        if record["arguments_kind"] == "json":
            try:
                parsed_arguments = json.loads(record["arguments"])
            except (TypeError, ValueError):
                continue
            argument_strings = _json_string_leaves(parsed_arguments)
        else:
            argument_strings = (record["arguments"],)
        matches = _signal_matches(argument_strings)
        for kind, count in matches.items():
            if count:
                code = {"svc_cli": "svc-cli-call", "test": "svc-test-call", "build": "svc-build-call"}[kind]
                signal_findings.append(_candidate_finding(code, (record,), {"signal_kind": kind, "tool_name": record["name"], "count": count}, kind="heuristic", confidence="medium"))
                signals.append({"kind": kind, "count": count, "first_evidence_ref": _ref(bundle_id, record)})
    findings.extend(signal_findings)
    has_scannable_arguments = any(record["arguments_kind"] in {"json", "text"} and record["arguments"] is not None for record in calls)
    if manifest_value["capabilities"]["task_references"] == "unavailable" and not task_counts and not has_scannable_arguments:
        unknowns.append(_candidate_unknown("svc-signal-unavailable", (), cause="capability", details={"capability": "task_references"}))
        statuses["svc_signals"] = "unavailable"
    aggregated_signals: dict[str, dict[str, object]] = {}
    for signal in signals:
        prior = aggregated_signals.get(signal["kind"])
        if prior is None:
            aggregated_signals[signal["kind"]] = dict(signal)
        else:
            prior["count"] += signal["count"]
            if signal["first_evidence_ref"]["record_index"] < prior["first_evidence_ref"]["record_index"]:
                prior["first_evidence_ref"] = signal["first_evidence_ref"]
    signals = list(aggregated_signals.values())
    signal_order = {"task_reference": 0, "svc_cli": 1, "test": 2, "build": 3}
    signals.sort(key=lambda item: signal_order[item["kind"]])
    metrics["svc_signals"] = {"task_references": sum(count for count, _ in task_counts.values()), "svc_cli_calls": sum(item["count"] for item in signals if item["kind"] == "svc_cli"), "test_calls": sum(item["count"] for item in signals if item["kind"] == "test"), "build_calls": sum(item["count"] for item in signals if item["kind"] == "build"), "signals": signals}

    context_changes = []
    context_first: dict[tuple[object, object], Mapping[str, object]] = {}
    for record in contexts:
        key = (record["context_kind"], record.get("actor_ref"))
        prior = context_first.get(key)
        if prior is None:
            context_first[key] = record
            findings.append(_candidate_finding("context-established", (record,), {"context_kind": record["context_kind"]}))
        elif prior["fingerprint"] != record["fingerprint"]:
            context_changes.append((prior, record))
            findings.append(_candidate_finding("context-changed", (prior, record), {"context_kind": record["context_kind"]}))
            context_first[key] = record
    if manifest_value["capabilities"]["context"] == "absent":
        unknowns.append(_candidate_unknown("context-evidence-unavailable", (), cause="capability", details={"capability": "context"}))
        statuses["context_changes"] = "unavailable"
    metrics["context_changes"] = {"context_records": len(contexts), "changes": len(context_changes), "by_kind": {kind: sum(record["context_kind"] == kind for record in contexts) for kind in ("system", "developer", "tool_config", "turn")}, "change_refs": bounded_refs("context_changes", [item for pair in context_changes for item in pair], 512)}

    # Apply all metric cardinality bounds in one deterministic pass so scalar
    # totals remain complete while retained arrays stay bounded.
    bounded_array("task_evidence", "task_references", 2048)
    bounded_array("interaction_transitions", "boundaries", 2048)
    bounded_array("tool_outcomes", "tools", 512)
    bounded_array("loop_candidates", "groups", 512)
    bounded_array("lanes", "actors", 512)
    bounded_array("lanes", "lanes", 512)
    bounded_array("lanes", "concurrency_groups", 512)
    bounded_array("svc_signals", "signals", 512)
    limit_anchors = {
        "task_evidence": users,
        "interaction_transitions": users + approvals,
        "constraint_evidence": constraint_refs,
        "tool_outcomes": [record for record in records if record["type"] in {"tool_call", "tool_result"}],
        "loop_candidates": calls,
        "lanes": [record for record in records if any(key in record for key in ("actor_ref", "parent_actor_ref", "lane_ref", "concurrency_group"))],
        "terminal_coverage": starts + terminal,
        "svc_signals": calls + users,
        "context_changes": contexts,
        "coverage": [records[0]],
    }
    for dimension in DIMENSIONS:
        omissions = metric_omissions[dimension] + evidence_ref_omissions[dimension]
        if omissions:
            anchor = min(limit_anchors[dimension], key=_record_key) if limit_anchors[dimension] else None
            unknowns.append(_candidate_unknown("analysis-limit-reached", (anchor,) if anchor is not None else (), cause="analysis_limit", dimension=dimension, details={"count": omissions, "truncated": True}))
            if statuses[dimension] == "available":
                statuses[dimension] = "partial"

    coverage_metrics = _base_metrics(records)
    coverage_metrics.update({"source_status": loss["source_status"], "bundle_result_status": loss["result_status"], "capabilities": dict(manifest_value["capabilities"])})
    metrics["coverage"] = coverage_metrics
    for group, values in loss.items():
        if group in {"source_status", "result_status", "mode"}:
            continue
        for key, count in values.items():
            if count:
                findings.append(_candidate_finding("loss-observed", (records[0],), {"loss_class": f"{group}.{key}", "count": count}, kind="observed"))
    if manifest_value["result_status"] == "partial":
        unknowns.append(_candidate_unknown("coverage-partial", (records[0],), cause="loss", details={"source_status": loss["source_status"], "result_status": loss["result_status"]}))
        statuses["coverage"] = "partial"
    _apply_relevant_loss(statuses, records, loss, manifest_value["capabilities"], tail_loss=tail_loss)

    output_findings, output_unknowns, finding_ids, unknown_ids, findings_omitted, unknowns_omitted = _assign_ids(findings, unknowns, bundle_id)
    if findings_omitted or unknowns_omitted:
        limited_dimensions = {item["dimension"] for item in output_unknowns if item["code"] == "analysis-limit-reached"}
        for dimension in limited_dimensions:
            if statuses[dimension] == "available":
                statuses[dimension] = "partial"
    dimensions = {dimension: _dimension(dimension, finding_ids[dimension], unknown_ids[dimension], statuses[dimension]) for dimension in DIMENSIONS}
    evidence_omitted_total = sum(evidence_ref_omissions.values())
    metric_omitted_total = sum(metric_omissions.values())
    analysis_loss = {"limits_reached": [], "findings_omitted": findings_omitted, "unknowns_omitted": unknowns_omitted, "evidence_refs_omitted": evidence_omitted_total, "metric_entries_omitted": metric_omitted_total}
    if findings_omitted:
        analysis_loss["limits_reached"].append("finding")
    if unknowns_omitted:
        analysis_loss["limits_reached"].append("unknown")
    if evidence_omitted_total:
        analysis_loss["limits_reached"].append("evidence_ref")
    if metric_omitted_total:
        analysis_loss["limits_reached"].append("metric_entry")
    if findings_omitted or unknowns_omitted or evidence_omitted_total or metric_omitted_total:
        payload_status = "partial"
    else:
        payload_status = "partial" if manifest_value["result_status"] == "partial" else "ready"
    payload: dict[str, object] = {"format": "svc-agent-thread-analysis", "schema_version": 1, "bundle_id": bundle_id, "analyzer": ANALYZER, "result_status": payload_status, "dimensions": dimensions, "metrics": metrics, "findings": output_findings, "unknowns": output_unknowns, "lossiness": {"bundle": loss, "analysis": analysis_loss}}
    validate_analysis(payload, trajectory=source)
    try:
        encoded = canonical_analysis_bytes(payload, max_bytes=max_output_bytes)
    except AnalysisError as error:
        if error.code != "analysis-limit-reached":
            raise
        _trim_payload_for_bytes(payload)
        validate_analysis(payload, trajectory=source)
        encoded = canonical_analysis_bytes(payload, max_bytes=max_output_bytes)
    return AnalysisResult(MappingProxyType(payload), encoded, payload["result_status"], bundle_id)


def _nonnegative(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _validate_evidence_ref(value: object, bundle_id: str, trajectory: ValidatedTrajectory | None) -> None:
    if not isinstance(value, Mapping) or set(value) != {"bundle_id", "record_id", "record_index"}:
        _error("Analysis evidence reference is invalid.")
    if value["bundle_id"] != bundle_id or not isinstance(value["record_id"], str) or not re.fullmatch(r"r[0-9]{6}", value["record_id"]) or not _nonnegative(value["record_index"]):
        _error("Analysis evidence reference is invalid.")
    if trajectory is not None:
        matched = next((record for record in trajectory.records if record["record_id"] == value["record_id"]), None)
        if matched is None or matched["record_index"] != value["record_index"]:
            _error("Analysis evidence reference does not resolve in the trajectory.")


def _validate_metric_evidence(value: object, bundle_id: str, trajectory: ValidatedTrajectory | None, *, max_items: int = 2048, allow_null: bool = False) -> None:
    if value is None and allow_null:
        return
    if not isinstance(value, Mapping):
        _error("Metric evidence reference is invalid.")
    _validate_evidence_ref(value, bundle_id, trajectory)


def _validate_metric_arrays(metrics: Mapping[str, object], bundle_id: str, trajectory: ValidatedTrajectory | None, capabilities: Mapping[str, object]) -> None:
    task = metrics["task_evidence"]
    if len(task["user_turn_refs"]) > 2048 or len(task["task_references"]) > 2048:
        _error("Task metric arrays exceed bounds.")
    for ref in task["user_turn_refs"]:
        _validate_evidence_ref(ref, bundle_id, trajectory)
    for item in task["task_references"]:
        path_parts = item.get("path", "").split("/") if isinstance(item.get("path"), str) else []
        if set(item) != {"path", "occurrences", "first_evidence_ref"} or not isinstance(item["path"], str) or len(item["path"]) > 1024 or len(path_parts) < 3 or path_parts[0] != "tasks" or path_parts[-1] != "packet.md" or any(part in {"", ".", ".."} for part in path_parts[1:-1]) or not _nonnegative(item["occurrences"]):
            _error("Task reference metric is invalid.")
        _validate_evidence_ref(item["first_evidence_ref"], bundle_id, trajectory)

    transitions = metrics["interaction_transitions"]
    if len(transitions["boundaries"]) > 2048:
        _error("Transition metric array exceeds bounds.")
    for item in transitions["boundaries"]:
        if set(item) != {"user_ref", "preceding_action_ref", "following_action_ref", "approval_refs"} or len(item["approval_refs"]) > 32:
            _error("Transition summary is invalid.")
        _validate_evidence_ref(item["user_ref"], bundle_id, trajectory)
        _validate_metric_evidence(item["preceding_action_ref"], bundle_id, trajectory, allow_null=True)
        _validate_metric_evidence(item["following_action_ref"], bundle_id, trajectory, allow_null=True)
        for ref in item["approval_refs"]:
            _validate_evidence_ref(ref, bundle_id, trajectory)

    constraint = metrics["constraint_evidence"]
    if len(constraint["evidence_refs"]) > 2048:
        _error("Constraint evidence array exceeds bounds.")
    for ref in constraint["evidence_refs"]:
        _validate_evidence_ref(ref, bundle_id, trajectory)

    tools = metrics["tool_outcomes"]
    if len(tools["tools"]) > 512:
        _error("Tool metric array exceeds bounds.")
    for item in tools["tools"]:
        expected = {"name", "name_fingerprint", "calls", "results", "success", "error", "unknown", "pending", "late_linked", "truncated_results", "retry_groups", "first_evidence_ref"}
        if set(item) != expected or not isinstance(item["name"], str) or len(item["name"]) > 256 or not re.fullmatch(r"[0-9a-f]{64}", str(item["name_fingerprint"])):
            _error("Tool summary is invalid.")
        if any(not _nonnegative(item[key]) for key in expected - {"name", "name_fingerprint", "first_evidence_ref"}):
            _error("Tool summary count is invalid.")
        _validate_evidence_ref(item["first_evidence_ref"], bundle_id, trajectory)

    loops = metrics["loop_candidates"]
    if len(loops["groups"]) > 512:
        _error("Loop metric array exceeds bounds.")
    for item in loops["groups"]:
        expected = {"kind", "tool_name", "name_fingerprint", "call_count", "first_evidence_ref", "last_evidence_ref", "outcomes"}
        if set(item) != expected or item["kind"] not in {"retry", "loop", "stall", "recovery"} or not isinstance(item["tool_name"], str) or len(item["tool_name"]) > 256 or not re.fullmatch(r"[0-9a-f]{64}", str(item["name_fingerprint"])) or not _nonnegative(item["call_count"]) or not 2 <= item["call_count"]:
            _error("Loop summary is invalid.")
        if len(item["outcomes"]) > 32 or any(outcome not in {"success", "error", "unknown", "pending"} for outcome in item["outcomes"]):
            _error("Loop outcomes are invalid.")
        _validate_evidence_ref(item["first_evidence_ref"], bundle_id, trajectory)
        _validate_evidence_ref(item["last_evidence_ref"], bundle_id, trajectory)

    lanes = metrics["lanes"]
    for key in ("actors", "lanes", "concurrency_groups"):
        if len(lanes[key]) > 512 or any(not isinstance(item, str) or len(item) > 128 or not item.isascii() for item in lanes[key]):
            _error("Lane metric array is invalid.")

    terminal = metrics["terminal_coverage"]
    if len(terminal["terminal_evidence_refs"]) > 32 or terminal["status"] not in {"completed", "error", "aborted", "open", "unknown"} or not isinstance(terminal["tail_loss"], bool):
        _error("Terminal metric is invalid.")
    for ref in terminal["terminal_evidence_refs"]:
        _validate_evidence_ref(ref, bundle_id, trajectory)

    signals = metrics["svc_signals"]
    if len(signals["signals"]) > 512:
        _error("SVC signal metric array exceeds bounds.")
    for item in signals["signals"]:
        if set(item) != {"kind", "count", "first_evidence_ref"} or item["kind"] not in {"task_reference", "svc_cli", "test", "build"} or not _nonnegative(item["count"]):
            _error("SVC signal summary is invalid.")
        _validate_evidence_ref(item["first_evidence_ref"], bundle_id, trajectory)

    context = metrics["context_changes"]
    if len(context["change_refs"]) > 512 or set(context["by_kind"]) != {"system", "developer", "tool_config", "turn"}:
        _error("Context metric is invalid.")
    for ref in context["change_refs"]:
        _validate_evidence_ref(ref, bundle_id, trajectory)
    coverage = metrics["coverage"]
    if set(coverage["records_by_type"]) != set(RECORD_TYPES) or set(coverage["messages_by_role"]) != {"user", "assistant"}:
        _error("Coverage metric maps are invalid.")
    if any(not _nonnegative(number) for number in coverage["records_by_type"].values()) or any(not _nonnegative(number) for number in coverage["messages_by_role"].values()):
        _error("Coverage metric counts are invalid.")
    if coverage["first_timestamp"] is not None and (not isinstance(coverage["first_timestamp"], str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z", coverage["first_timestamp"])):
        _error("Coverage first timestamp is invalid.")
    if coverage["last_timestamp"] is not None and (not isinstance(coverage["last_timestamp"], str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z", coverage["last_timestamp"])):
        _error("Coverage last timestamp is invalid.")
    if not isinstance(coverage["capabilities"], Mapping) or set(coverage["capabilities"]) != {"reasoning", "tool_linkage", "context", "task_references", "explicit_concurrency", "timestamps", "terminal_events"}:
        _error("Coverage capability map is invalid.")
    allowed_capabilities = {
        "reasoning": {"full", "summary", "opaque", "absent"}, "tool_linkage": {"explicit", "mixed", "synthesized", "absent"},
        "context": {"full", "partial", "absent"}, "task_references": {"available", "unavailable"},
        "explicit_concurrency": {"available", "unavailable"}, "timestamps": {"full", "partial", "absent"}, "terminal_events": {"available", "unavailable"},
    }
    if any(coverage["capabilities"][key] not in values for key, values in allowed_capabilities.items()):
        _error("Coverage capability value is invalid.")


def validate_analysis(value: Mapping[str, object], *, trajectory: ValidatedTrajectory | ValidatedBundle | None = None) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _error("Analysis result must be an object.")
    required = {"format", "schema_version", "bundle_id", "analyzer", "result_status", "dimensions", "metrics", "findings", "unknowns", "lossiness"}
    if set(value) != required or value["format"] != "svc-agent-thread-analysis" or value["schema_version"] != 1 or not isinstance(value["bundle_id"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["bundle_id"]):
        _error("Analysis top-level schema is invalid.")
    if value["analyzer"] != ANALYZER or value["result_status"] not in {"ready", "partial"}:
        _error("Analysis analyzer/status is invalid.")
    dimensions = value["dimensions"]
    if not isinstance(dimensions, Mapping) or set(dimensions) != set(DIMENSIONS):
        _error("Analysis dimensions have an invalid shape.")
    for dimension, entry in dimensions.items():
        if not isinstance(entry, Mapping) or set(entry) != {"status", "finding_ids", "unknown_ids"} or entry["status"] not in {"available", "partial", "unavailable"} or not isinstance(entry["finding_ids"], list) or not isinstance(entry["unknown_ids"], list):
            _error("Analysis dimension entry is invalid.", dimension=dimension)
    if not isinstance(value["findings"], list) or not isinstance(value["unknowns"], list) or len(value["findings"]) > 256 or len(value["unknowns"]) > 256:
        _error("Analysis findings/unknowns exceed bounds.")
    finding_ids: set[str] = set()
    for index, finding in enumerate(value["findings"], 1):
        if not isinstance(finding, Mapping) or set(finding) != {"id", "dimension", "code", "kind", "confidence", "evidence_refs", "details"} or finding["id"] != f"f{index:06d}" or finding["dimension"] not in DIMENSIONS or finding["code"] not in FINDING_CODES or finding["kind"] not in {"observed", "deterministic", "heuristic"} or finding["confidence"] not in {"high", "medium"} or not isinstance(finding["evidence_refs"], list) or not 1 <= len(finding["evidence_refs"]) <= 32 or not isinstance(finding["details"], Mapping):
            _error("Analysis finding is invalid.")
        if finding["dimension"] != _FINDING_DIMENSION[finding["code"]] or set(finding["details"]) != _FINDING_DETAIL_KEYS[finding["code"]]:
            _error("Analysis finding code/details are invalid.")
        validated = trajectory if isinstance(trajectory, ValidatedTrajectory) else trajectory.trajectory if isinstance(trajectory, ValidatedBundle) else None
        for ref in finding["evidence_refs"]:
            _validate_evidence_ref(ref, value["bundle_id"], validated)
        finding_ids.add(finding["id"])
    unknown_ids: set[str] = set()
    for index, unknown in enumerate(value["unknowns"], 1):
        if not isinstance(unknown, Mapping) or set(unknown) != {"id", "dimension", "code", "cause", "evidence_refs", "details"} or unknown["id"] != f"u{index:06d}" or unknown["dimension"] not in DIMENSIONS or unknown["code"] not in UNKNOWN_CODES or unknown["cause"] not in {"capability", "missing", "loss", "ambiguity", "conflict", "analysis_limit"} or not isinstance(unknown["evidence_refs"], list) or len(unknown["evidence_refs"]) > 32 or not isinstance(unknown["details"], Mapping):
            _error("Analysis unknown is invalid.")
        expected_unknown_details = _UNKNOWN_DETAIL_KEYS[unknown["code"]]
        if unknown["code"] == "terminal-evidence-unavailable" and unknown["cause"] != "capability":
            expected_unknown_details = set()
        if unknown["code"] in {"tool-linkage-unavailable", "concurrency-unavailable", "svc-signal-unavailable", "context-evidence-unavailable"} and unknown["cause"] != "capability":
            _error("Capability unknown has an invalid cause.")
        if (unknown["code"] != "analysis-limit-reached" and unknown["dimension"] != _UNKNOWN_DIMENSION[unknown["code"]]) or set(unknown["details"]) != expected_unknown_details:
            _error("Analysis unknown code/details are invalid.")
        validated = trajectory if isinstance(trajectory, ValidatedTrajectory) else trajectory.trajectory if isinstance(trajectory, ValidatedBundle) else None
        for ref in unknown["evidence_refs"]:
            _validate_evidence_ref(ref, value["bundle_id"], validated)
        unknown_ids.add(unknown["id"])
    for dimension in DIMENSIONS:
        if sum(item["dimension"] == dimension for item in value["findings"]) > 25 or sum(item["dimension"] == dimension for item in value["unknowns"]) > 25:
            _error("Analysis per-dimension finding/unknown bound exceeded.", dimension=dimension)
    finding_membership = {identifier: 0 for identifier in finding_ids}
    unknown_membership = {identifier: 0 for identifier in unknown_ids}
    for dimension, entry in dimensions.items():
        if any(identifier not in finding_ids for identifier in entry["finding_ids"]) or any(identifier not in unknown_ids for identifier in entry["unknown_ids"]):
            _error("Dimension references an unknown finding/unknown ID.")
        for identifier in entry["finding_ids"]:
            finding = value["findings"][int(identifier[1:]) - 1]
            if finding["dimension"] != dimension:
                _error("Dimension references a finding owned by another dimension.")
            finding_membership[identifier] += 1
        for identifier in entry["unknown_ids"]:
            unknown = value["unknowns"][int(identifier[1:]) - 1]
            if unknown["dimension"] != dimension:
                _error("Dimension references an unknown owned by another dimension.")
            unknown_membership[identifier] += 1
    if any(count != 1 for count in finding_membership.values()) or any(count != 1 for count in unknown_membership.values()):
        _error("Every finding and unknown must be referenced exactly once by dimensions.")
    metrics = value["metrics"]
    if not isinstance(metrics, Mapping) or set(metrics) != set(DIMENSIONS):
        _error("Analysis metrics have an invalid shape.")
    for dimension, metric in metrics.items():
        if not isinstance(metric, Mapping) or set(metric) != _METRIC_KEYS[dimension]:
            _error("Analysis metric entry has an invalid shape.", dimension=dimension)
    scalar_keys = {
        "task_evidence": ("user_turn_count",),
        "interaction_transitions": ("boundary_count", "structured_approval_count"),
        "constraint_evidence": ("context_record_count", "task_reference_count", "structured_approval_count"),
        "tool_outcomes": ("calls", "results", "success", "error", "unknown", "pending", "orphan", "late_linked", "truncated_results", "retry_groups"),
        "loop_candidates": ("retry_group_count", "loop_candidate_count", "stall_candidate_count", "recovery_candidate_count"),
        "lanes": ("actor_count", "lane_count", "concurrency_group_count", "parent_link_count"),
        "terminal_coverage": (),
        "svc_signals": ("task_references", "svc_cli_calls", "test_calls", "build_calls"),
        "context_changes": ("context_records", "changes"),
        "coverage": ("records_total", "timestamped_records", "untimestamped_records"),
    }
    for dimension, keys in scalar_keys.items():
        for key in keys:
            if not _nonnegative(metrics[dimension][key]):
                _error("Analysis metric scalar is invalid.", metric=dimension, key=key)
    validated = trajectory if isinstance(trajectory, ValidatedTrajectory) else trajectory.trajectory if isinstance(trajectory, ValidatedBundle) else None
    _validate_metric_arrays(metrics, value["bundle_id"], validated, metrics["coverage"]["capabilities"])
    loss = value["lossiness"]
    if not isinstance(loss, Mapping) or set(loss) != {"bundle", "analysis"} or not isinstance(loss["bundle"], Mapping) or not isinstance(loss["analysis"], Mapping):
        _error("Analysis lossiness has an invalid shape.")
    if set(loss["bundle"]) != {"mode", "source_status", "result_status", "dropped", "truncated", "unavailable", "synthesized", "partial_reasons"}:
        _error("Analysis bundle lossiness is invalid.")
    if loss["bundle"]["mode"] != "bounded_normalized" or loss["bundle"]["source_status"] not in {"stable", "grew", "changed", "displaced"} or loss["bundle"]["result_status"] not in {"ready", "partial"}:
        _error("Analysis bundle lossiness scalar is invalid.")
    for group in ("dropped", "truncated", "unavailable", "synthesized", "partial_reasons"):
        if not isinstance(loss["bundle"][group], Mapping) or set(loss["bundle"][group]) != _LOSS_CLASS_KEYS[group] or any(not _nonnegative(number) for number in loss["bundle"][group].values()):
            _error("Analysis bundle lossiness map is invalid.")
    if set(loss["analysis"]) != {"limits_reached", "findings_omitted", "unknowns_omitted", "evidence_refs_omitted", "metric_entries_omitted"} or not isinstance(loss["analysis"]["limits_reached"], list) or any(item not in _ANALYSIS_LIMITS for item in loss["analysis"]["limits_reached"]) or len(set(loss["analysis"]["limits_reached"])) != len(loss["analysis"]["limits_reached"]) or loss["analysis"]["limits_reached"] != [item for item in _ANALYSIS_LIMITS if item in loss["analysis"]["limits_reached"]]:
        _error("Analysis local lossiness is invalid.")
    for key in ("findings_omitted", "unknowns_omitted", "evidence_refs_omitted", "metric_entries_omitted"):
        if not isinstance(loss["analysis"][key], int) or isinstance(loss["analysis"][key], bool) or loss["analysis"][key] < 0:
            _error("Analysis local loss count is invalid.")
    capability_keys = {"reasoning", "tool_linkage", "context", "task_references", "explicit_concurrency", "timestamps", "terminal_events"}
    for item in value["findings"] + value["unknowns"]:
        for key, detail in item["details"].items():
            if key in {"count", "retry_count"} and not _nonnegative(detail):
                _error("Analysis detail count is invalid.")
            if key == "status" and detail not in {"success", "error", "unknown", "pending", "completed", "aborted", "open"}:
                _error("Analysis status detail is invalid.")
            if key == "outcome" and detail not in {None, "requested", "granted", "denied", "cancelled", "unknown", "completed", "error", "aborted"}:
                _error("Analysis outcome detail is invalid.")
            if key == "context_kind" and detail not in {"system", "developer", "tool_config", "turn"}:
                _error("Analysis context detail is invalid.")
            if key == "task_ref" and (not isinstance(detail, str) or not re.fullmatch(r"tasks/(?:[^/]+/)+packet\.md", detail) or len(detail) > 1024):
                _error("Analysis task reference detail is invalid.")
            if key == "truncated" and not isinstance(detail, bool):
                _error("Analysis detail truncated flag is invalid.")
            if key == "late_linked" and detail is not True:
                _error("Analysis late-link detail is invalid.")
            if key == "tool_name" and (not isinstance(detail, str) or len(detail) > 256):
                _error("Analysis tool name detail is invalid.")
            if key == "capability" and detail not in capability_keys:
                _error("Analysis capability detail is invalid.")
            if key == "signal_kind" and detail not in {"task_reference", "svc_cli", "test", "build"}:
                _error("Analysis signal detail is invalid.")
            if key == "loss_class":
                if not isinstance(detail, str) or "." not in detail:
                    _error("Analysis loss detail is invalid.")
                group, loss_key = detail.split(".", 1)
                if group not in _LOSS_CLASS_KEYS or loss_key not in _LOSS_CLASS_KEYS[group]:
                    _error("Analysis loss detail is invalid.")
    return value


__all__ = ["ANALYZER", "AnalysisError", "AnalysisResult", "DIMENSIONS", "FINDING_CODES", "UNKNOWN_CODES", "analyze_trajectory", "canonical_analysis_bytes", "validate_analysis"]
