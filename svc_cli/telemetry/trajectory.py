"""Provider-neutral schema-v2 trajectory primitives.

This module deliberately has no provider, archive, or UI dependencies.  It is
the small executable boundary shared by normalizers and later bundle readers:
records are validated before they become durable JSONL, and a collector writes
canonical bytes incrementally to a caller-owned sink.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import re
from types import MappingProxyType
from typing import BinaryIO, Iterable, Mapping, Any


TRAJECTORY_SCHEMA = "svc.trajectory/v1"
CONTENT_PROFILE = "bounded-normalized-v1"

MAX_SOURCE_BYTES = 268_435_456
MAX_NATIVE_LINE_BYTES = 4_194_304
MAX_NATIVE_JSON_DEPTH = 64
MAX_RECORDS = 50_000
MAX_TRAJECTORY_BYTES = 33_554_432
MAX_WORKSPACE_LABEL_CODE_POINTS = 256
MAX_MESSAGE_CONTEXT_CODE_POINTS = 16_384
MAX_REASONING_CODE_POINTS = 8_192
MAX_TOOL_NAME_CODE_POINTS = 256
MAX_TOOL_ARGUMENTS_CODE_POINTS = 20_000
MAX_TOOL_RESULT_CODE_POINTS = 2_500
MAX_CONTEXT_ATTRIBUTE_KEYS = 6
MAX_CONTEXT_ATTRIBUTE_CODE_POINTS = 512
MAX_TOOL_CONFIG_NAMES = 256
MAX_TASK_REFERENCE_CODE_POINTS = 1_024
MAX_TASK_REFERENCE_OCCURRENCES = 2_048
MAX_STRUCTURAL_LABEL_ASCII = 128

RECORD_TYPES = ("meta", "message", "reasoning", "tool_call", "tool_result", "context", "event")
RELATIONSHIP_KEYS = ("turn_ref", "actor_ref", "parent_actor_ref", "lane_ref", "concurrency_group")
REF_PREFIXES = {"thread", "turn", "call", "actor", "lane", "concurrency", "workspace"}
_HEX_REF = re.compile(r"^(?:thread|turn|call|actor|lane|concurrency|workspace)_[0-9a-f]{64}(?:_d[0-9]{6})?$")
_RECORD_ID = re.compile(r"^r[0-9]{6}$")
_COMPONENT = re.compile(r"^[a-z][a-z0-9_-]{0,127}$")
_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$"
)


class TrajectoryError(ValueError):
    """Stable executable trajectory error with a machine-readable code."""

    def __init__(self, code: str, message: str, details: Mapping[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = MappingProxyType(dict(details or {}))

    def as_dict(self) -> dict[str, object]:
        value: dict[str, object] = {"code": self.code, "message": self.message}
        if self.details:
            value["details"] = dict(self.details)
        return value


@dataclass(frozen=True)
class NormalizationPolicy:
    """The frozen schema-v2 policy and resource bounds."""

    profile: str = CONTENT_PROFILE
    sensitivity: str = "acknowledged"
    redaction: str = "none"
    noise_policy: str = "structural-v1"
    task_reference_policy: str = "lexical-relative-packet-v1"
    timestamp_policy: str = "utc-rfc3339-nanosecond-v1"
    source_bytes: int = MAX_SOURCE_BYTES
    native_line_bytes: int = MAX_NATIVE_LINE_BYTES
    native_json_depth: int = MAX_NATIVE_JSON_DEPTH
    records: int = MAX_RECORDS
    trajectory_bytes: int = MAX_TRAJECTORY_BYTES
    schema_v2_zip_bytes: int = 67_108_864
    manifest_bytes: int = 1_048_576
    workspace_label_code_points: int = MAX_WORKSPACE_LABEL_CODE_POINTS
    message_context_code_points: int = MAX_MESSAGE_CONTEXT_CODE_POINTS
    reasoning_code_points: int = MAX_REASONING_CODE_POINTS
    tool_name_code_points: int = MAX_TOOL_NAME_CODE_POINTS
    tool_arguments_code_points: int = MAX_TOOL_ARGUMENTS_CODE_POINTS
    tool_result_code_points: int = MAX_TOOL_RESULT_CODE_POINTS
    context_attribute_keys: int = MAX_CONTEXT_ATTRIBUTE_KEYS
    context_attribute_code_points: int = MAX_CONTEXT_ATTRIBUTE_CODE_POINTS
    tool_config_names: int = MAX_TOOL_CONFIG_NAMES
    task_reference_code_points: int = MAX_TASK_REFERENCE_CODE_POINTS
    task_reference_occurrences: int = MAX_TASK_REFERENCE_OCCURRENCES
    structural_label_ascii: int = MAX_STRUCTURAL_LABEL_ASCII
    diagnostics: int = 256
    diagnostic_detail_keys: int = 16
    diagnostic_detail_ascii: int = 128


DEFAULT_NORMALIZATION_POLICY = NormalizationPolicy()


def policy_dict(policy: NormalizationPolicy = DEFAULT_NORMALIZATION_POLICY) -> Mapping[str, object]:
    """Return the exact manifest policy object as ordinary JSON-ready data."""

    if not isinstance(policy, NormalizationPolicy):
        raise TrajectoryError("invalid-policy", "Normalization policy has an invalid type.")
    bounds = {
        "source_bytes": policy.source_bytes,
        "native_line_bytes": policy.native_line_bytes,
        "native_json_depth": policy.native_json_depth,
        "records": policy.records,
        "trajectory_bytes": policy.trajectory_bytes,
        "schema_v2_zip_bytes": policy.schema_v2_zip_bytes,
        "manifest_bytes": policy.manifest_bytes,
        "workspace_label_code_points": policy.workspace_label_code_points,
        "message_context_code_points": policy.message_context_code_points,
        "reasoning_code_points": policy.reasoning_code_points,
        "tool_name_code_points": policy.tool_name_code_points,
        "tool_arguments_code_points": policy.tool_arguments_code_points,
        "tool_result_code_points": policy.tool_result_code_points,
        "context_attribute_keys": policy.context_attribute_keys,
        "context_attribute_code_points": policy.context_attribute_code_points,
        "tool_config_names": policy.tool_config_names,
        "task_reference_code_points": policy.task_reference_code_points,
        "task_reference_occurrences": policy.task_reference_occurrences,
        "structural_label_ascii": policy.structural_label_ascii,
        "diagnostics": policy.diagnostics,
        "diagnostic_detail_keys": policy.diagnostic_detail_keys,
        "diagnostic_detail_ascii": policy.diagnostic_detail_ascii,
    }
    return {
        "profile": policy.profile,
        "sensitivity": policy.sensitivity,
        "redaction": policy.redaction,
        "noise_policy": policy.noise_policy,
        "task_reference_policy": policy.task_reference_policy,
        "timestamp_policy": policy.timestamp_policy,
        "bounds": bounds,
    }


def _fail(message: str, *, code: str = "invalid-trajectory", **details: object) -> None:
    raise TrajectoryError(code, message, details)


def _is_bool(value: object) -> bool:
    return isinstance(value, bool)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_string(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        return False
    return not any(0xD800 <= ord(char) <= 0xDFFF for char in value)


def _exact_keys(value: Mapping[str, object], required: set[str], optional: set[str] = set()) -> None:
    keys = set(value)
    allowed = required | optional
    if not required <= keys or not keys <= allowed:
        missing = sorted(required - keys)
        extra = sorted(keys - allowed)
        _fail("Record keys do not match the schema.", missing=missing, extra=extra)


def _check_ref(value: object, *, prefix: str | None = None) -> None:
    if not isinstance(value, str) or not _HEX_REF.fullmatch(value):
        _fail("Relationship reference has an invalid hash shape.")
    if prefix is not None and not value.startswith(prefix + "_"):
        _fail("Relationship reference has an invalid kind.")
    if re.search(r"_d[0-9]{6}$", value) and prefix != "call":
        _fail("Only duplicate call references may carry an occurrence suffix.")


def _check_timestamp(value: object) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value):
        _fail("Timestamp must be UTC RFC 3339 with seconds and a Z suffix.")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        _fail("Timestamp is not a valid UTC instant.")


def _check_bounded_text(value: object, meta: object, *, max_code_points: int, allow_null: bool = False) -> None:
    if value is None and allow_null:
        if not isinstance(meta, Mapping):
            _fail("Null text requires bounded metadata.")
        _exact_keys(meta, {"truncated", "observed_code_points", "retained_code_points", "strategy"})
        if meta.get("truncated") is not False or meta.get("observed_code_points") != 0 or meta.get("retained_code_points") != 0 or meta.get("strategy") != "none":
            _fail("Null text metadata must have zero counts.")
        return
    if not _is_string(value) or not isinstance(meta, Mapping):
        _fail("Bounded text has an invalid value or metadata object.")
    _exact_keys(meta, {"truncated", "observed_code_points", "retained_code_points", "strategy"})
    observed = meta["observed_code_points"]
    retained = meta["retained_code_points"]
    strategy = meta["strategy"]
    if not _is_bool(meta["truncated"]) or not _is_int(observed) or not _is_int(retained):
        _fail("Bounded text metadata has invalid scalar types.")
    if observed < 0 or retained < 0 or retained != len(value) or retained > max_code_points or observed < retained:
        _fail("Bounded text metadata is inconsistent with retained content.")
    if strategy not in {"none", "head", "head_tail"}:
        _fail("Bounded text strategy is invalid.")
    if (strategy == "none") != (not meta["truncated"]):
        _fail("Bounded text truncation flag and strategy disagree.")
    if strategy == "none" and observed != retained:
        _fail("Untruncated text must retain all observed code points.")


def _check_source_ref(value: object, *, meta: bool) -> None:
    if not isinstance(value, Mapping):
        _fail("source_ref must be an object.")
    if meta:
        _exact_keys(value, {"event_index", "component"})
        if value["event_index"] is not None or value["component"] != "meta":
            _fail("Meta source_ref is invalid.")
        return
    if "event_index" not in value or not _is_int(value["event_index"]) or value["event_index"] < 0:
        _fail("Provider source_ref requires a non-negative event_index.")
    allowed = {"event_index", "line", "byte_offset", "component_index", "component"}
    if not set(value) <= allowed:
        _fail("source_ref contains an unsupported key.")
    for key in ("line", "byte_offset", "component_index"):
        if key in value and (not _is_int(value[key]) or value[key] < 0):
            _fail("source_ref offsets must be non-negative integers.")
    if "component" in value and (not isinstance(value["component"], str) or not _COMPONENT.fullmatch(value["component"])):
        _fail("source_ref component is invalid.")


def _valid_task_ref(value: object) -> bool:
    if not isinstance(value, str) or len(value) > MAX_TASK_REFERENCE_CODE_POINTS or "\\" in value:
        return False
    parts = value.split("/")
    return len(parts) >= 3 and parts[0] == "tasks" and parts[-1] == "packet.md" and all(part not in {"", ".", ".."} for part in parts[1:-1])


def _check_workspace(value: object) -> None:
    if not isinstance(value, Mapping):
        _fail("workspace must be an object.")
    _exact_keys(value, {"status", "flavor", "label", "ref", "label_truncated", "observed_code_points", "retained_code_points"})
    status = value["status"]
    if status not in {"present", "missing"}:
        _fail("workspace status is invalid.")
    if status == "missing":
        if value["flavor"] is not None or value["label"] is not None or value["ref"] is not None:
            _fail("Missing workspace cannot expose path-derived values.")
        if value["observed_code_points"] != 0 or value["retained_code_points"] != 0:
            _fail("Missing workspace must have zero counts.")
    else:
        if value["flavor"] not in {"posix", "windows", "unc"} or value["ref"] is None:
            _fail("Present workspace has invalid flavor/ref.")
        if not _is_string(value["label"]):
            _fail("Present workspace must retain a lexical label string.")
        _check_ref(value["ref"], prefix="workspace")
        _check_bounded_text(value["label"], {
            "truncated": value["label_truncated"],
            "observed_code_points": value["observed_code_points"],
            "retained_code_points": value["retained_code_points"],
            "strategy": "head" if value["label_truncated"] else "none",
        }, max_code_points=MAX_WORKSPACE_LABEL_CODE_POINTS, allow_null=True)
    if not _is_bool(value["label_truncated"]) or not _is_int(value["observed_code_points"]) or not _is_int(value["retained_code_points"]):
        _fail("workspace bounds metadata has invalid types.")


def _check_attributes(value: object, meta: object) -> None:
    if not isinstance(value, Mapping) or not isinstance(meta, Mapping):
        _fail("Context attributes must be objects.")
    allowed = {"model", "reasoning_effort", "approval_mode", "sandbox_mode", "collaboration_mode", "tool_names"}
    if not set(value) <= allowed or set(meta) != set(value):
        _fail("Context attributes keys are inconsistent.")
    if len(value) > MAX_CONTEXT_ATTRIBUTE_KEYS:
        _fail("Context attribute key bound exceeded.")
    for key, item in value.items():
        if key == "tool_names":
            if not isinstance(item, list) or not isinstance(meta[key], Mapping):
                _fail("tool_names context attribute is invalid.")
            _exact_keys(meta[key], {"observed_items", "retained_items", "truncated"})
            if not _is_int(meta[key]["observed_items"]) or not _is_int(meta[key]["retained_items"]) or not _is_bool(meta[key]["truncated"]):
                _fail("tool_names metadata has invalid types.")
            if (
                meta[key]["observed_items"] < meta[key]["retained_items"]
                or meta[key]["retained_items"] < 0
                or len(item) != meta[key]["retained_items"]
                or len(item) > MAX_TOOL_CONFIG_NAMES
            ):
                _fail("tool_names metadata count is inconsistent.")
            for name in item:
                if not isinstance(name, Mapping):
                    _fail("tool_names entries must be objects.")
                _exact_keys(name, {"name", "name_meta", "name_fingerprint"})
                _check_bounded_text(name["name"], name["name_meta"], max_code_points=MAX_TOOL_NAME_CODE_POINTS)
                if not isinstance(name["name_fingerprint"], str) or not re.fullmatch(r"[0-9a-f]{64}", name["name_fingerprint"]):
                    _fail("tool name fingerprint is invalid.")
            names = [entry["name"].encode("utf-8") for entry in item]
            if names != sorted(names) or len(set(names)) != len(names):
                _fail("tool_names must be sorted and deduplicated by retained UTF-8 name.")
            continue
        if not isinstance(item, str):
            _fail("Context scalar attributes must be strings.")
        _check_bounded_text(item, meta[key], max_code_points=MAX_CONTEXT_ATTRIBUTE_CODE_POINTS)


def _fingerprint(prefix: bytes, value: bytes) -> str:
    return hashlib.sha256(prefix + value).hexdigest()


def _validate_tool_fingerprints(record: Mapping[str, object]) -> None:
    name_meta = record["name_meta"]
    if isinstance(name_meta, Mapping) and name_meta.get("truncated") is False:
        expected = _fingerprint(b"svc-tool-name-v1\0", str(record["name"]).encode("utf-8"))
        if record["name_fingerprint"] != expected:
            _fail("Tool name fingerprint does not match canonical name.")
    kind = record["arguments_kind"]
    arguments = record["arguments"]
    if kind == "absent":
        return
    assert isinstance(arguments, str)
    arguments_meta = record["arguments_meta"]
    argument_bytes: bytes
    if kind == "json":
        try:
            parsed = _strict_loads(arguments.encode("utf-8"))
            argument_bytes = canonical_json_bytes(parsed)
        except TrajectoryError:
            _fail("Untruncated JSON tool arguments are not canonical.")
        if isinstance(arguments_meta, Mapping) and arguments_meta.get("truncated") is False and argument_bytes.decode("utf-8") != arguments:
            _fail("JSON tool arguments must use canonical compact sorted-key encoding.")
    else:
        argument_bytes = arguments.encode("utf-8")
    if isinstance(arguments_meta, Mapping) and arguments_meta.get("truncated") is False:
        expected = _fingerprint(b"svc-tool-arguments-v1\0", argument_bytes)
        if record["arguments_fingerprint"] != expected:
            _fail("Tool argument fingerprint does not match canonical arguments.")


def _validate_context_fingerprint(record: Mapping[str, object]) -> None:
    payload = {
        "context_kind": record["context_kind"],
        "content": record["content"],
        "content_meta": record["content_meta"],
        "attributes": record["attributes"],
        "attributes_meta": record["attributes_meta"],
    }
    expected = _fingerprint(b"svc-context-v1\0", canonical_json_bytes(payload))
    if record["fingerprint"] != expected:
        _fail("Context fingerprint does not match canonical context.")


def validate_record(record: Mapping[str, object], *, expected_index: int | None = None) -> Mapping[str, object]:
    """Validate one schema-v1 trajectory record and return it unchanged."""

    if not isinstance(record, Mapping):
        _fail("Trajectory records must be JSON objects.")
    if not isinstance(record.get("type"), str) or record["type"] not in RECORD_TYPES:
        _fail("Trajectory record type is invalid.")
    record_type = record["type"]
    required = {"type", "record_id", "record_index", "timestamp", "source_ref"}
    optional = set(RELATIONSHIP_KEYS)
    fields = {
        "meta": {"trajectory_schema", "provider_id", "adapter_id", "source_format", "thread_ref", "workspace", "content_profile"},
        "message": {"role", "content", "content_meta", "task_refs"},
        "reasoning": {"reasoning_kind", "content", "content_meta"},
        "tool_call": {"tool_call_id", "name", "name_meta", "name_fingerprint", "arguments_kind", "arguments", "arguments_meta", "arguments_fingerprint"},
        "tool_result": {"tool_call_id", "content", "content_meta", "status", "link_status"},
        "context": {"context_kind", "content", "content_meta", "attributes", "attributes_meta", "fingerprint"},
        "event": {"event_kind", "outcome"},
    }[record_type]
    _exact_keys(record, required | fields, optional)
    if record_type == "meta" and any(key in record for key in optional):
        _fail("Meta records cannot carry relationship references.")
    if not isinstance(record["record_id"], str) or not _RECORD_ID.fullmatch(record["record_id"]):
        _fail("record_id has invalid form.")
    if not _is_int(record["record_index"]) or record["record_index"] < 0:
        _fail("record_index must be non-negative.")
    if expected_index is not None and record["record_index"] != expected_index:
        _fail("record_index is not contiguous.")
    if record["record_id"] != f"r{record['record_index']:06d}":
        _fail("record_id does not match record_index.")
    _check_timestamp(record["timestamp"])
    _check_source_ref(record["source_ref"], meta=record_type == "meta")
    for key in optional:
        if key in record:
            prefix = {"turn_ref": "turn", "actor_ref": "actor", "parent_actor_ref": "actor", "lane_ref": "lane", "concurrency_group": "concurrency"}[key]
            _check_ref(record[key], prefix=prefix)

    if record_type == "meta":
        if record["timestamp"] is not None or record["trajectory_schema"] != TRAJECTORY_SCHEMA or record["content_profile"] != CONTENT_PROFILE:
            _fail("Meta record has invalid schema/profile/timestamp.")
        for key in ("provider_id", "adapter_id", "source_format"):
            if not isinstance(record[key], str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", record[key]):
                _fail("Meta provider identity is invalid.")
        _check_ref(record["thread_ref"], prefix="thread")
        _check_workspace(record["workspace"])
    elif record_type == "message":
        if record["role"] not in {"user", "assistant"} or not isinstance(record["task_refs"], list):
            _fail("Message role/task_refs are invalid.")
        _check_bounded_text(record["content"], record["content_meta"], max_code_points=MAX_MESSAGE_CONTEXT_CODE_POINTS)
        if len(record["task_refs"]) > MAX_TASK_REFERENCE_OCCURRENCES:
            _fail("Task-reference occurrence bound exceeded.")
        if len(set(record["task_refs"])) != len(record["task_refs"]):
            _fail("Task references must be unique within one message.")
        for ref in record["task_refs"]:
            if not _valid_task_ref(ref):
                _fail("Task reference is invalid.")
    elif record_type == "reasoning":
        if record["reasoning_kind"] not in {"full", "summary"}:
            _fail("Reasoning kind is invalid.")
        _check_bounded_text(record["content"], record["content_meta"], max_code_points=MAX_REASONING_CODE_POINTS)
    elif record_type == "tool_call":
        _check_ref(record["tool_call_id"], prefix="call")
        _check_bounded_text(record["name"], record["name_meta"], max_code_points=MAX_TOOL_NAME_CODE_POINTS)
        if not isinstance(record["name_fingerprint"], str) or not re.fullmatch(r"[0-9a-f]{64}", record["name_fingerprint"]):
            _fail("Tool name fingerprint is invalid.")
        if record["arguments_kind"] not in {"json", "text", "absent"}:
            _fail("Tool arguments kind is invalid.")
        _check_bounded_text(record["arguments"], record["arguments_meta"], max_code_points=MAX_TOOL_ARGUMENTS_CODE_POINTS, allow_null=True)
        if record["arguments_kind"] == "absent" and (record["arguments"] is not None or record["arguments_fingerprint"] is not None):
            _fail("Absent tool arguments must be null.")
        if record["arguments_kind"] != "absent" and (record["arguments"] is None or not isinstance(record["arguments_fingerprint"], str) or not re.fullmatch(r"[0-9a-f]{64}", record["arguments_fingerprint"] or "")):
            _fail("Tool arguments fingerprint/value is invalid.")
        _validate_tool_fingerprints(record)
    elif record_type == "tool_result":
        _check_ref(record["tool_call_id"], prefix="call")
        _check_bounded_text(record["content"], record["content_meta"], max_code_points=MAX_TOOL_RESULT_CODE_POINTS)
        if record["status"] not in {"success", "error", "unknown"} or record["link_status"] not in {"linked", "unresolved"}:
            _fail("Tool result status/link status is invalid.")
    elif record_type == "context":
        if record["context_kind"] not in {"system", "developer", "tool_config", "turn"}:
            _fail("Context kind is invalid.")
        if record["context_kind"] in {"tool_config", "turn"} and record["content"] is not None:
            _fail("Tool-config/turn context content must be null.")
        _check_bounded_text(record["content"], record["content_meta"], max_code_points=MAX_MESSAGE_CONTEXT_CODE_POINTS, allow_null=True)
        _check_attributes(record["attributes"], record["attributes_meta"])
        if not isinstance(record["fingerprint"], str) or not re.fullmatch(r"[0-9a-f]{64}", record["fingerprint"]):
            _fail("Context fingerprint is invalid.")
        _validate_context_fingerprint(record)
    else:
        kinds = {"turn_start", "turn_complete", "turn_abort", "agent_start", "agent_complete", "compaction", "approval", "error"}
        if record["event_kind"] not in kinds:
            _fail("Event kind is invalid.")
        outcome = record["outcome"]
        allowed = {
            "approval": {"requested", "granted", "denied", "cancelled", "unknown"},
            "turn_complete": {"completed", "error", "aborted", "unknown"},
            "agent_complete": {"completed", "error", "aborted", "unknown"},
            "turn_abort": {"aborted"},
            "error": {"error"},
            "turn_start": {None}, "agent_start": {None}, "compaction": {None},
        }[record["event_kind"]]
        if outcome not in allowed:
            _fail("Event outcome is incompatible with event kind.")
    return record


def canonical_json_bytes(value: object, *, newline: bool = False) -> bytes:
    """Encode strict compact/sorted-key UTF-8 JSON."""

    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        encoded = text.encode("utf-8", errors="strict")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise TrajectoryError("invalid-json", "Value cannot be encoded as canonical JSON.") from error
    return encoded + (b"\n" if newline else b"")


def _strict_loads(data: bytes) -> object:
    try:
        text = data.decode("utf-8", errors="strict")
        def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    _fail("Duplicate JSON object key.", code="invalid-json")
                result[key] = value
            return result
        value = json.loads(text, object_pairs_hook=reject_duplicates, parse_constant=lambda _: _fail("Non-finite JSON number.", code="invalid-json"))
    except TrajectoryError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TrajectoryError("invalid-json", "Trajectory line is not valid UTF-8 JSON.") from error
    return value


def _json_depth(value: object, depth: int = 1) -> int:
    if isinstance(value, Mapping):
        return max([depth, *(_json_depth(item, depth + 1) for item in value.values())])
    if isinstance(value, list):
        return max([depth, *(_json_depth(item, depth + 1) for item in value)])
    return depth


@dataclass(frozen=True)
class EncodedTrajectory:
    trajectory_bytes: bytes | None
    trajectory_sha256: str
    trajectory_size: int
    records: int
    records_by_type: Mapping[str, int]
    messages_by_role: Mapping[str, int]
    tool_calls: int
    tool_results: int
    task_references: int


class TrajectoryCollector:
    """Incremental canonical trajectory writer with exact caps."""

    def __init__(self, output: BinaryIO | None = None, *, policy: NormalizationPolicy = DEFAULT_NORMALIZATION_POLICY) -> None:
        self._owned = output is None
        self._output = output or io.BytesIO()
        self._policy = policy
        self._digest = hashlib.sha256()
        self._size = 0
        self._records = 0
        self._records_by_type = {name: 0 for name in RECORD_TYPES}
        self._messages_by_role = {"user": 0, "assistant": 0}
        self._tool_calls = 0
        self._tool_results = 0
        self._task_references = 0
        self._finished = False
        self._limit_reason: str | None = None
        self._limit_observed: int | None = None
        self._limit_value: int | None = None

    @property
    def limit_reason(self) -> str | None:
        return self._limit_reason

    @property
    def limit_observed(self) -> int | None:
        return self._limit_observed

    @property
    def limit_value(self) -> int | None:
        return self._limit_value

    @property
    def records(self) -> int:
        return self._records

    def emit(self, record: Mapping[str, object]) -> bool:
        if self._finished:
            _fail("Trajectory collector is already finished.", code="collector-finished")
        validate_record(record, expected_index=self._records)
        if _json_depth(record) > self._policy.native_json_depth:
            _fail("Trajectory JSON depth bound exceeded.", code="json-depth-exceeded")
        if self._records == 0 and record["type"] != "meta":
            _fail("Trajectory must begin with a meta record.")
        if self._records > 0 and record["type"] == "meta":
            _fail("Trajectory may contain only one leading meta record.")
        if self._records >= self._policy.records:
            self._limit_reason = "record_limit"
            self._limit_observed = self._records + 1
            self._limit_value = self._policy.records
            return False
        line = canonical_json_bytes(record, newline=True)
        if self._size + len(line) > self._policy.trajectory_bytes:
            self._limit_reason = "trajectory_limit"
            self._limit_observed = self._size + len(line)
            self._limit_value = self._policy.trajectory_bytes
            return False
        try:
            self._output.write(line)
        except OSError as error:
            raise TrajectoryError("trajectory-write-failed", "Trajectory sink could not be written.") from error
        self._digest.update(line)
        self._size += len(line)
        self._records += 1
        record_type = str(record["type"])
        self._records_by_type[record_type] += 1
        if record_type == "message":
            self._messages_by_role[str(record["role"])] += 1
            self._task_references += len(record["task_refs"])
        elif record_type == "tool_call":
            self._tool_calls += 1
        elif record_type == "tool_result":
            self._tool_results += 1
        return True

    def finish(self) -> EncodedTrajectory:
        if self._finished:
            _fail("Trajectory collector is already finished.", code="collector-finished")
        self._finished = True
        if self._records == 0:
            _fail("Trajectory must contain a meta record.")
        if self._records_by_type["meta"] != 1:
            _fail("Trajectory must contain exactly one leading meta record.")
        data = self._output.getvalue() if self._owned and isinstance(self._output, io.BytesIO) else None
        return EncodedTrajectory(
            trajectory_bytes=data,
            trajectory_sha256=self._digest.hexdigest(),
            trajectory_size=self._size,
            records=self._records,
            records_by_type=MappingProxyType(dict(self._records_by_type)),
            messages_by_role=MappingProxyType(dict(self._messages_by_role)),
            tool_calls=self._tool_calls,
            tool_results=self._tool_results,
            task_references=self._task_references,
        )


def encode_trajectory(records: Iterable[Mapping[str, object]], *, policy: NormalizationPolicy = DEFAULT_NORMALIZATION_POLICY, output: BinaryIO | None = None) -> EncodedTrajectory:
    collector = TrajectoryCollector(output, policy=policy)
    for record in records:
        if not collector.emit(record):
            break
    return collector.finish()


@dataclass(frozen=True)
class ValidatedTrajectory:
    records: tuple[Mapping[str, object], ...]
    trajectory_bytes: bytes
    trajectory_sha256: str


def validate_trajectory_bytes(data: bytes, *, policy: NormalizationPolicy = DEFAULT_NORMALIZATION_POLICY) -> ValidatedTrajectory:
    if not isinstance(data, bytes):
        _fail("Trajectory input must be bytes.")
    if len(data) > policy.trajectory_bytes:
        _fail("Trajectory byte bound exceeded.", code="trajectory-limit-reached")
    if not data or not data.endswith(b"\n"):
        _fail("Trajectory must be LF terminated.")
    records: list[Mapping[str, object]] = []
    offset = 0
    for line in data.splitlines(keepends=True):
        if not line.endswith(b"\n") or line == b"\n":
            _fail("Trajectory contains an empty or unterminated line.")
        if len(line) > policy.native_line_bytes:
            _fail("Trajectory line bound exceeded.", code="record-oversize-dropped")
        value = _strict_loads(line[:-1])
        if _json_depth(value) > policy.native_json_depth:
            _fail("Trajectory JSON depth bound exceeded.", code="json-depth-exceeded")
        if not isinstance(value, Mapping):
            _fail("Trajectory lines must contain objects.")
        canonical = canonical_json_bytes(value, newline=True)
        if canonical != line:
            _fail("Trajectory line is not canonical JSONL.")
        validate_record(value, expected_index=len(records))
        records.append(value)
        if len(records) > policy.records:
            _fail("Trajectory record bound exceeded.", code="record-limit-reached")
        offset += len(line)
    if not records or records[0]["type"] != "meta" or sum(record["type"] == "meta" for record in records) != 1:
        _fail("Trajectory must contain exactly one leading meta record.")
    return ValidatedTrajectory(tuple(records), data, hashlib.sha256(data).hexdigest())


# ---- schema-v2 bundle ---------------------------------------------------

BUNDLE_FORMAT = "svc-agent-thread-bundle"
BUNDLE_SCHEMA_VERSION = 2
MAX_SCHEMA_V2_ZIP_BYTES = 67_108_864
MAX_MANIFEST_BYTES = 1_048_576
_MANIFEST_ROOT = {
    "format", "schema_version", "trajectory", "bundle_id", "exporter", "generated_at",
    "source", "policy", "result_status", "capabilities", "counts", "lossiness", "diagnostics",
}
_CAPABILITY_VALUES = {
    "reasoning": {"full", "summary", "opaque", "absent"},
    "tool_linkage": {"explicit", "mixed", "synthesized", "absent"},
    "context": {"full", "partial", "absent"},
    "task_references": {"available", "unavailable"},
    "explicit_concurrency": {"available", "unavailable"},
    "timestamps": {"full", "partial", "absent"},
    "terminal_events": {"available", "unavailable"},
}
_LOSS_KEYS = {
    "dropped": ("provider_envelope", "ui_event", "rate_limit_noise", "world_state", "duplicate_bookkeeping", "opaque_metadata", "unsupported_record", "invalid_json", "oversize_record", "excessive_json_depth", "duplicate_tool_result", "absolute_task_reference", "invalid_task_reference", "oversize_task_reference"),
    "truncated": ("timestamp_precision", "workspace_label", "message", "context_content", "context_attribute", "reasoning", "tool_name", "tool_config_names", "tool_arguments", "tool_result", "task_references", "diagnostics"),
    "unavailable": ("reasoning", "tool_linkage", "context", "task_references", "explicit_concurrency", "timestamps", "terminal_events"),
    "synthesized": ("tool_call_id",),
    "partial_reasons": ("source_grew", "source_changed", "source_displaced", "source_read_interrupted", "input_limit", "record_limit", "trajectory_limit"),
}
_COUNT_KEYS = ("source_bytes_read", "source_events_seen", "records_emitted", "trajectory_bytes", "records_by_type", "messages_by_role", "tool_calls", "tool_results", "task_references", "diagnostics_emitted", "diagnostics_suppressed")
_DIAGNOSTIC_DETAIL_KEYS = {"record_type", "content_kind", "observed_bytes", "limit_bytes", "observed_code_points", "retained_code_points", "observed_digits", "retained_digits", "observed_depth", "limit_depth", "observed_count", "limit_count", "occurrence", "capability", "arguments_kind", "source_status"}
_DIAGNOSTIC_RECORD_TYPES = {"envelope", "ui", "rate_limit", "world_state", "duplicate", "opaque", "unknown"}
_DIAGNOSTIC_CONTENT_KINDS = {"system", "developer", "model", "reasoning_effort", "approval_mode", "sandbox_mode", "collaboration_mode", "tool_call_name", "tool_config_name"}
_DIAGNOSTIC_SPECS = {
    "noise-record-dropped": ("drop", "info", {"record_type"}), "unsupported-record-dropped": ("drop", "warning", {"record_type"}),
    "invalid-json-line": ("drop", "warning", set()), "record-oversize-dropped": ("drop", "warning", {"observed_bytes", "limit_bytes"}),
    "json-depth-exceeded": ("drop", "warning", {"observed_depth", "limit_depth"}), "timestamp-invalid": ("unavailable", "warning", set()),
    "timestamp-precision-truncated": ("truncate", "info", {"observed_digits", "retained_digits"}), "workspace-label-truncated": ("truncate", "info", {"observed_code_points", "retained_code_points"}),
    "message-truncated": ("truncate", "info", {"observed_code_points", "retained_code_points"}), "context-content-truncated": ("truncate", "info", {"content_kind", "observed_code_points", "retained_code_points"}),
    "context-attribute-truncated": ("truncate", "info", {"content_kind", "observed_code_points", "retained_code_points"}), "reasoning-truncated": ("truncate", "info", {"observed_code_points", "retained_code_points"}),
    "reasoning-unavailable": ("unavailable", "info", {"capability"}), "tool-name-truncated": ("truncate", "info", {"content_kind", "observed_code_points", "retained_code_points"}),
    "tool-config-name-limit-reached": ("truncate", "warning", {"observed_count", "limit_count"}), "tool-arguments-text": ("normalize", "info", {"arguments_kind"}),
    "tool-arguments-truncated": ("truncate", "info", {"observed_code_points", "retained_code_points"}), "tool-result-truncated": ("truncate", "info", {"observed_code_points", "retained_code_points"}),
    "tool-call-id-synthesized": ("synthesize", "warning", {"occurrence"}), "duplicate-tool-call-id": ("synthesize", "warning", {"occurrence"}),
    "duplicate-tool-result": ("drop", "warning", {"occurrence"}), "orphan-tool-result": ("unavailable", "warning", set()),
    "absolute-task-reference-dropped": ("drop", "info", set()), "invalid-task-reference-dropped": ("drop", "info", set()),
    "task-reference-oversize-dropped": ("drop", "warning", {"observed_code_points", "retained_code_points"}), "source-grew-during-collection": ("partial", "warning", {"source_status"}),
    "source-changed-during-collection": ("partial", "warning", {"source_status"}), "source-displaced-during-collection": ("partial", "warning", {"source_status"}),
    "source-read-interrupted": ("partial", "error", set()), "input-limit-reached": ("partial", "warning", {"observed_bytes", "limit_bytes"}),
    "record-limit-reached": ("partial", "warning", {"observed_count", "limit_count"}), "trajectory-limit-reached": ("partial", "warning", {"observed_bytes", "limit_bytes"}),
    "task-reference-limit-reached": ("truncate", "warning", {"observed_count", "limit_count"}), "diagnostic-limit-reached": ("truncate", "warning", {"observed_count", "limit_count"}),
}


@dataclass(frozen=True)
class ValidatedBundle:
    manifest: Mapping[str, object]
    trajectory: ValidatedTrajectory
    bundle_id: str
    path: Any = None


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _read_trajectory_source(source: bytes | BinaryIO | EncodedTrajectory) -> bytes:
    if isinstance(source, EncodedTrajectory):
        if source.trajectory_bytes is None:
            _fail("Encoded trajectory has no retained bytes; pass the rewindable source.")
        return source.trajectory_bytes
    if isinstance(source, bytes):
        return source
    if not hasattr(source, "read") or not hasattr(source, "seek") or not hasattr(source, "tell"):
        _fail("Trajectory source must be bytes or a rewindable binary stream.")
    try:
        position = source.tell()
        source.seek(0)
        data = source.read(MAX_TRAJECTORY_BYTES + 1)
        source.seek(position)
    except (OSError, ValueError) as error:
        raise TrajectoryError("trajectory-read-failed", "Trajectory source could not be read.") from error
    if not isinstance(data, bytes):
        _fail("Trajectory source returned non-bytes.")
    return data


def _identity_metadata(manifest: Mapping[str, object]) -> dict[str, object]:
    exporter = manifest["exporter"]
    return {
        "normalizer_name": exporter["normalizer_name"],
        "normalizer_version": exporter["normalizer_version"],
        "source": manifest["source"],
        "policy": manifest["policy"],
        "result_status": manifest["result_status"],
        "capabilities": manifest["capabilities"],
        "counts": manifest["counts"],
        "lossiness": manifest["lossiness"],
        "diagnostics": manifest["diagnostics"],
    }


def build_bundle_id(manifest: Mapping[str, object], trajectory_bytes: bytes) -> str:
    identity = canonical_json_bytes(_identity_metadata(manifest))
    return hashlib.sha256(b"svc-agent-thread-bundle-v2\0" + trajectory_bytes + b"\0" + identity).hexdigest()


def _validate_lossiness(lossiness: object) -> dict[str, dict[str, int]]:
    if not isinstance(lossiness, Mapping):
        _fail("Manifest lossiness must be an object.")
    result: dict[str, dict[str, int]] = {}
    for group, keys in _LOSS_KEYS.items():
        if not isinstance(lossiness.get(group), Mapping) or set(lossiness[group]) != set(keys):
            _fail("Manifest lossiness map has an invalid shape.")
        group_value: dict[str, int] = {}
        for key in keys:
            value = lossiness[group][key]
            if not _is_int(value) or value < 0:
                _fail("Manifest lossiness values must be non-negative integers.")
            group_value[key] = value
        result[group] = group_value
    return result


def zero_lossiness() -> dict[str, dict[str, int]]:
    return {group: {key: 0 for key in keys} for group, keys in _LOSS_KEYS.items()}


def _validate_counts(counts: object, encoded: EncodedTrajectory | None = None) -> dict[str, object]:
    if not isinstance(counts, Mapping) or set(counts) != set(_COUNT_KEYS):
        _fail("Manifest counts have an invalid shape.")
    result: dict[str, object] = {}
    for key in ("source_bytes_read", "source_events_seen", "records_emitted", "trajectory_bytes", "tool_calls", "tool_results", "task_references", "diagnostics_emitted", "diagnostics_suppressed"):
        value = counts[key]
        if not _is_int(value) or value < 0:
            _fail("Manifest count values must be non-negative integers.")
        result[key] = value
    records_by_type = counts["records_by_type"]
    messages_by_role = counts["messages_by_role"]
    if not isinstance(records_by_type, Mapping) or set(records_by_type) != set(RECORD_TYPES):
        _fail("records_by_type has an invalid shape.")
    if not isinstance(messages_by_role, Mapping) or set(messages_by_role) != {"user", "assistant"}:
        _fail("messages_by_role has an invalid shape.")
    for mapping in (records_by_type, messages_by_role):
        for value in mapping.values():
            if not _is_int(value) or value < 0:
                _fail("Nested manifest counts must be non-negative integers.")
    result["records_by_type"] = dict(records_by_type)
    result["messages_by_role"] = dict(messages_by_role)
    if sum(records_by_type.values()) != result["records_emitted"]:
        _fail("Manifest records_by_type total disagrees with records_emitted.")
    if sum(messages_by_role.values()) != records_by_type["message"]:
        _fail("Manifest messages_by_role total disagrees with message count.")
    if result["tool_calls"] != records_by_type["tool_call"] or result["tool_results"] != records_by_type["tool_result"]:
        _fail("Manifest tool totals disagree with records_by_type.")
    if encoded is not None:
        expected = {
            "records_emitted": encoded.records,
            "trajectory_bytes": encoded.trajectory_size,
            "records_by_type": dict(encoded.records_by_type),
            "messages_by_role": dict(encoded.messages_by_role),
            "tool_calls": encoded.tool_calls,
            "tool_results": encoded.tool_results,
            "task_references": encoded.task_references,
        }
        for key, value in expected.items():
            if result[key] != value:
                _fail("Manifest counts disagree with trajectory records.", count=key)
    return result


def _validate_diagnostics(
    diagnostics: object,
    *,
    diagnostic_limit: int,
) -> list[dict[str, object]]:
    if not _is_int(diagnostic_limit) or diagnostic_limit <= 0:
        _fail("Manifest diagnostics bound is invalid.")
    if not isinstance(diagnostics, list) or len(diagnostics) > diagnostic_limit:
        _fail("Manifest diagnostics exceed their bound.")
    result: list[dict[str, object]] = []
    required_source_ref = {
        "invalid-json-line",
        "timestamp-invalid",
        "absolute-task-reference-dropped",
        "invalid-task-reference-dropped",
    }
    required_record_ref = {"orphan-tool-result"}
    for item in diagnostics:
        if not isinstance(item, Mapping):
            _fail("Manifest diagnostic must be an object.")
        _exact_keys(item, {"code", "severity", "action", "count", "record_ref", "source_ref", "details"})
        if not isinstance(item["code"], str) or item["code"] not in _DIAGNOSTIC_SPECS or not _is_int(item["count"]) or item["count"] <= 0:
            _fail("Manifest diagnostic scalar is invalid.")
        expected_action, expected_severity, expected_details = _DIAGNOSTIC_SPECS[item["code"]]
        if item["severity"] != expected_severity or item["action"] != expected_action:
            _fail("Manifest diagnostic severity/action does not match its code.")
        if item["record_ref"] is not None and (not isinstance(item["record_ref"], str) or not _RECORD_ID.fullmatch(item["record_ref"])):
            _fail("Manifest diagnostic record_ref is invalid.")
        if item["source_ref"] is not None:
            _check_source_ref(item["source_ref"], meta=False)
        if (
            item["code"] in required_source_ref
            and item["source_ref"] is None
        ):
            _fail(
                "Manifest diagnostic requires a source_ref.",
                diagnostic_code=item["code"],
            )
        if (
            item["code"] in required_record_ref
            and item["record_ref"] is None
        ):
            _fail(
                "Manifest diagnostic requires a record_ref.",
                diagnostic_code=item["code"],
            )
        if not isinstance(item["details"], Mapping) or set(item["details"]) != expected_details or not set(item["details"]) <= _DIAGNOSTIC_DETAIL_KEYS:
            _fail("Manifest diagnostic details are invalid.")
        if len(item["details"]) > 16:
            _fail("Manifest diagnostic details exceed their bound.")
        for key, value in item["details"].items():
            if key in {"observed_bytes", "limit_bytes", "observed_code_points", "retained_code_points", "observed_digits", "retained_digits", "observed_depth", "limit_depth", "observed_count", "limit_count", "occurrence"} and (not _is_int(value) or value < 0):
                _fail("Manifest diagnostic numeric detail is invalid.")
            if key == "record_type" and value not in _DIAGNOSTIC_RECORD_TYPES:
                _fail("Manifest diagnostic record_type is invalid.")
            if key == "content_kind" and value not in _DIAGNOSTIC_CONTENT_KINDS:
                _fail("Manifest diagnostic content_kind is invalid.")
            if key in {"capability", "arguments_kind", "source_status"} and not isinstance(value, str):
                _fail("Manifest diagnostic enum detail is invalid.")
        result.append(dict(item))
    has_limit = bool(
        result
        and result[-1]["code"] == "diagnostic-limit-reached"
    )
    regular = result[:-1] if has_limit else result
    if any(
        item["code"] == "diagnostic-limit-reached"
        for item in regular
    ):
        _fail(
            "Diagnostic limit marker must be the final diagnostic."
        )
    if has_limit:
        marker = result[-1]
        details = marker["details"]
        if (
            marker["count"] != 1
            or marker["record_ref"] is not None
            or marker["source_ref"] is not None
            or details["limit_count"] != diagnostic_limit
            or details["observed_count"] <= diagnostic_limit
            or len(result) != diagnostic_limit
        ):
            _fail("Diagnostic limit marker is inconsistent.")
    identities: set[tuple[str, bytes]] = set()
    missing_coordinate = 2**63 - 1

    def order_key(
        item: Mapping[str, object],
    ) -> tuple[tuple[int, int, int, int], bytes, bytes]:
        source = item["source_ref"]
        coordinates = tuple(
            (
                source.get(key, missing_coordinate)
                if isinstance(source, Mapping)
                else missing_coordinate
            )
            for key in (
                "event_index",
                "line",
                "byte_offset",
                "component_index",
            )
        )
        return (
            coordinates,  # type: ignore[return-value]
            str(item["code"]).encode("ascii"),
            canonical_json_bytes(item["details"]),
        )

    for item in regular:
        identity = (
            str(item["code"]),
            canonical_json_bytes(item["details"]),
        )
        if identity in identities:
            _fail(
                "Repeated diagnostic groups must be coalesced."
            )
        identities.add(identity)
    if regular != sorted(regular, key=order_key):
        _fail("Manifest diagnostics are not in canonical order.")
    return result


def _validate_capabilities(capabilities: Mapping[str, object], trajectory: ValidatedTrajectory, lossiness: Mapping[str, Mapping[str, int]]) -> None:
    records = trajectory.records
    reasoning = [record for record in records if record["type"] == "reasoning"]
    if capabilities["reasoning"] in {"opaque", "absent"} and reasoning:
        _fail("Reasoning capability forbids emitted reasoning records.")
    if capabilities["reasoning"] == "summary" and any(record["reasoning_kind"] == "full" for record in reasoning):
        _fail("Summary reasoning capability forbids full reasoning records.")
    tools = [record for record in records if record["type"] in {"tool_call", "tool_result"}]
    if capabilities["tool_linkage"] == "absent" and tools:
        _fail("Absent tool linkage capability forbids tool records.")
    if capabilities["tool_linkage"] == "explicit" and lossiness["synthesized"]["tool_call_id"]:
        _fail("Explicit tool linkage cannot declare synthesized IDs.")
    if capabilities["context"] == "absent" and any(record["type"] == "context" for record in records):
        _fail("Absent context capability forbids context records.")
    messages = [record for record in records if record["type"] == "message"]
    if capabilities["task_references"] == "unavailable" and any(record["task_refs"] for record in messages):
        _fail("Unavailable task-reference capability forbids retained task refs.")
    if capabilities["explicit_concurrency"] == "unavailable" and any(
        key in record for record in records for key in ("lane_ref", "parent_actor_ref", "concurrency_group")
    ):
        _fail("Unavailable concurrency capability forbids lane/parent/concurrency refs.")
    timed = [record for record in records if record["type"] != "meta"]
    timed_count = sum(record["timestamp"] is not None for record in timed)
    expected_timestamps = "full" if timed and timed_count == len(timed) else "partial" if timed_count else "absent"
    if timed:
        valid_timestamp_caps = {expected_timestamps}
    else:
        valid_timestamp_caps = {"full", "absent"}
    if capabilities["timestamps"] not in valid_timestamp_caps:
        _fail("Timestamp capability disagrees with record timestamps.")
    terminal_kinds = {"turn_start", "turn_complete", "turn_abort", "agent_start", "agent_complete", "error"}
    if capabilities["terminal_events"] == "unavailable" and any(record["type"] == "event" and record["event_kind"] in terminal_kinds for record in records):
        _fail("Unavailable terminal capability forbids terminal events.")


def validate_manifest(manifest: Mapping[str, object], *, trajectory: ValidatedTrajectory | None = None) -> Mapping[str, object]:
    if not isinstance(manifest, Mapping):
        _fail("Manifest must be an object.")
    _exact_keys(manifest, _MANIFEST_ROOT)
    if manifest["format"] != BUNDLE_FORMAT or manifest["schema_version"] != BUNDLE_SCHEMA_VERSION or manifest["result_status"] not in {"ready", "partial"}:
        _fail("Manifest format or schema version is invalid.")
    if not isinstance(manifest["bundle_id"], str) or not re.fullmatch(r"[0-9a-f]{64}", manifest["bundle_id"]):
        _fail("Manifest bundle_id is invalid.")
    if not isinstance(manifest["generated_at"], str):
        _fail("Manifest generated_at must be a UTC timestamp.")
    _check_timestamp(manifest["generated_at"])
    trajectory_shape = manifest["trajectory"]
    if not isinstance(trajectory_shape, Mapping):
        _fail("Manifest trajectory is invalid.")
    _exact_keys(trajectory_shape, {"schema", "member", "sha256", "bytes", "records"})
    if trajectory_shape["schema"] != TRAJECTORY_SCHEMA or trajectory_shape["member"] != "trajectory.jsonl" or not re.fullmatch(r"[0-9a-f]{64}", trajectory_shape["sha256"] or "") or not _is_int(trajectory_shape["bytes"]) or trajectory_shape["bytes"] < 0 or trajectory_shape["bytes"] > MAX_TRAJECTORY_BYTES or not _is_int(trajectory_shape["records"]) or not 1 <= trajectory_shape["records"] <= MAX_RECORDS:
        _fail("Manifest trajectory shape is invalid.")
    exporter = manifest["exporter"]
    if not isinstance(exporter, Mapping):
        _fail("Manifest exporter is invalid.")
    _exact_keys(exporter, {"name", "version", "normalizer_name", "normalizer_version"})
    if exporter["name"] != "svc" or not isinstance(exporter["version"], str) or exporter["normalizer_name"] != "svc-agent-thread-normalizer" or exporter["normalizer_version"] != 1:
        _fail("Manifest exporter identity is invalid.")
    source = manifest["source"]
    if not isinstance(source, Mapping):
        _fail("Manifest source is invalid.")
    _exact_keys(source, {"provider_id", "adapter_id", "source_format", "thread_ref", "source_status"})
    for key in ("provider_id", "adapter_id", "source_format"):
        if not isinstance(source[key], str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", source[key]):
            _fail("Manifest source identity is invalid.")
    _check_ref(source["thread_ref"], prefix="thread")
    if source["source_status"] not in {"stable", "grew", "changed", "displaced"}:
        _fail("Manifest source_status is invalid.")
    if manifest["policy"] != policy_dict():
        _fail("Manifest policy is not the exact bounded-normalized-v1 policy.")
    # The exact-policy check freezes schema v1; use its declared bound as the
    # marker contract so validation does not duplicate a numeric constant.
    manifest_policy = manifest["policy"]
    if (
        not isinstance(manifest_policy, Mapping)
        or not isinstance(manifest_policy.get("bounds"), Mapping)
        or not _is_int(manifest_policy["bounds"].get("diagnostics"))
    ):
        _fail("Manifest policy diagnostics bound is invalid.")
    diagnostic_limit = manifest_policy["bounds"]["diagnostics"]
    capabilities = manifest["capabilities"]
    if not isinstance(capabilities, Mapping) or set(capabilities) != set(_CAPABILITY_VALUES):
        _fail("Manifest capabilities have an invalid shape.")
    for key, values in _CAPABILITY_VALUES.items():
        if capabilities[key] not in values:
            _fail("Manifest capability value is invalid.", capability=key)
    counts = _validate_counts(manifest["counts"], None)
    lossiness = _validate_lossiness(manifest["lossiness"])
    diagnostics = _validate_diagnostics(
        manifest["diagnostics"],
        diagnostic_limit=diagnostic_limit,
    )
    partial_drops = (
        "unsupported_record",
        "invalid_json",
        "oversize_record",
        "excessive_json_depth",
        "duplicate_tool_result",
    )
    semantic_partial = any(lossiness["partial_reasons"].values()) or any(
        lossiness["dropped"][key] for key in partial_drops
    )
    if semantic_partial and manifest["result_status"] != "partial":
        _fail("Semantic evidence loss requires result_status=partial.")
    expected_source_reason = {
        "stable": None,
        "grew": "source_grew",
        "changed": "source_changed",
        "displaced": "source_displaced",
    }[source["source_status"]]
    for reason in ("source_grew", "source_changed", "source_displaced"):
        if bool(lossiness["partial_reasons"][reason]) != (
            reason == expected_source_reason
        ):
            _fail(
                "Manifest source status and partial reason disagree.",
                source_status=source["source_status"],
            )
    if (
        counts["diagnostics_emitted"]
        != sum(int(item["count"]) for item in diagnostics)
        or counts["diagnostics_suppressed"]
        != lossiness["truncated"]["diagnostics"]
    ):
        _fail("Manifest diagnostic counts disagree with diagnostics/lossiness.")
    if trajectory is not None:
        if trajectory.trajectory_sha256 != trajectory_shape["sha256"] or len(trajectory.trajectory_bytes) != trajectory_shape["bytes"] or len(trajectory.records) != trajectory_shape["records"]:
            _fail("Manifest trajectory metadata disagrees with trajectory bytes.")
        _validate_counts(counts, EncodedTrajectory(trajectory.trajectory_bytes, trajectory.trajectory_sha256, len(trajectory.trajectory_bytes), len(trajectory.records), MappingProxyType({key: sum(record["type"] == key for record in trajectory.records) for key in RECORD_TYPES}), MappingProxyType({"user": sum(record.get("role") == "user" for record in trajectory.records if record["type"] == "message"), "assistant": sum(record.get("role") == "assistant" for record in trajectory.records if record["type"] == "message")}), sum(record["type"] == "tool_call" for record in trajectory.records), sum(record["type"] == "tool_result" for record in trajectory.records), sum(len(record["task_refs"]) for record in trajectory.records if record["type"] == "message")))
        _validate_capabilities(capabilities, trajectory, lossiness)
        record_ids = {
            str(record["record_id"])
            for record in trajectory.records
        }
        if any(
            item["record_ref"] is not None
            and item["record_ref"] not in record_ids
            for item in diagnostics
        ):
            _fail(
                "Manifest diagnostic record_ref does not resolve."
            )
        if build_bundle_id(manifest, trajectory.trajectory_bytes) != manifest["bundle_id"]:
            _fail("Manifest bundle_id does not match trajectory and identity metadata.")
    return manifest


def build_manifest(*, trajectory_source: bytes | BinaryIO | EncodedTrajectory, source: Mapping[str, object], result_status: str, capabilities: Mapping[str, object], lossiness: Mapping[str, object], diagnostics: Iterable[Mapping[str, object]], counts: Mapping[str, object], exporter_version: str | None = None, generated_at: str | None = None, policy: NormalizationPolicy = DEFAULT_NORMALIZATION_POLICY) -> Mapping[str, object]:
    if exporter_version is None:
        from ..release import runtime_version

        exporter_version = runtime_version()
    trajectory_bytes = _read_trajectory_source(trajectory_source)
    validated = validate_trajectory_bytes(trajectory_bytes, policy=policy)
    encoded = EncodedTrajectory(trajectory_bytes, validated.trajectory_sha256, len(trajectory_bytes), len(validated.records), MappingProxyType({key: sum(record["type"] == key for record in validated.records) for key in RECORD_TYPES}), MappingProxyType({"user": sum(record.get("role") == "user" for record in validated.records if record["type"] == "message"), "assistant": sum(record.get("role") == "assistant" for record in validated.records if record["type"] == "message")}), sum(record["type"] == "tool_call" for record in validated.records), sum(record["type"] == "tool_result" for record in validated.records), sum(len(record["task_refs"]) for record in validated.records if record["type"] == "message"))
    normalized_counts = _validate_counts(counts, encoded)
    manifest: dict[str, object] = {
        "format": BUNDLE_FORMAT,
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "trajectory": {"schema": TRAJECTORY_SCHEMA, "member": "trajectory.jsonl", "sha256": encoded.trajectory_sha256, "bytes": encoded.trajectory_size, "records": encoded.records},
        "bundle_id": "0" * 64,
        "exporter": {"name": "svc", "version": exporter_version, "normalizer_name": "svc-agent-thread-normalizer", "normalizer_version": 1},
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source": _plain(source),
        "policy": dict(policy_dict(policy)),
        "result_status": result_status,
        "capabilities": _plain(capabilities),
        "counts": normalized_counts,
        "lossiness": _plain(lossiness),
        "diagnostics": [_plain(item) for item in diagnostics],
    }
    manifest["bundle_id"] = build_bundle_id(manifest, trajectory_bytes)
    validate_manifest(manifest, trajectory=validated)
    return manifest


def _zip_info(name: str) -> Any:
    import zipfile
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (0o600 & 0xFFFF) << 16
    return info


def _safe_member_name(name: str) -> bool:
    if not name or "\\" in name or name.startswith("/"):
        return False
    parts = name.split("/")
    return all(part not in {"", ".", ".."} for part in parts)


def _trajectory_from_source(source: bytes | BinaryIO | EncodedTrajectory) -> ValidatedTrajectory:
    data = _read_trajectory_source(source)
    return validate_trajectory_bytes(data)


def write_bundle_stream(binary_file: BinaryIO, manifest: Mapping[str, object], trajectory: bytes | BinaryIO | EncodedTrajectory) -> ValidatedBundle:
    """Write exactly the schema-v2 members into a caller-owned file object."""

    import zipfile
    if not hasattr(binary_file, "write"):
        _fail("Bundle output must be a binary writable stream.")
    trajectory_value = _trajectory_from_source(trajectory)
    validate_manifest(manifest, trajectory=trajectory_value)
    manifest_bytes = canonical_json_bytes(manifest, newline=True)
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        _fail("Manifest byte bound exceeded.", code="manifest-limit-reached")
    try:
        binary_file.seek(0)
        binary_file.truncate(0)
        with zipfile.ZipFile(binary_file, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            archive.writestr(_zip_info("manifest.json"), manifest_bytes)
            with archive.open(_zip_info("trajectory.jsonl"), mode="w") as destination:
                destination.write(trajectory_value.trajectory_bytes)
        binary_file.flush()
        end = binary_file.tell()
    except (OSError, zipfile.BadZipFile, ValueError) as error:
        raise TrajectoryError("bundle-write-failed", "Bundle ZIP could not be written.") from error
    if end > MAX_SCHEMA_V2_ZIP_BYTES:
        _fail("Bundle ZIP byte bound exceeded.", code="zip-limit-reached")
    return ValidatedBundle(manifest, trajectory_value, str(manifest["bundle_id"]), None)


def write_bundle(path: Any, manifest: Mapping[str, object], trajectory: bytes | BinaryIO | EncodedTrajectory) -> ValidatedBundle:
    """Convenience writer with absent-target/private temporary publication."""

    import os
    import stat
    import tempfile
    from pathlib import Path
    output = Path(path)
    if output.exists() or os.path.lexists(output):
        raise TrajectoryError("output-exists", "Bundle output already exists and was not replaced.")
    if not output.parent.exists() or not output.parent.is_dir():
        _fail("Bundle output parent must be an existing directory.")
    fd, temporary = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent)
    temp_path = Path(temporary)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w+b") as stream:
            fd = -1
            result = write_bundle_stream(stream, manifest, trajectory)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name == "nt":
            os.rename(temp_path, output)
        else:
            os.link(temp_path, output)
            temp_path.unlink()
        result = ValidatedBundle(result.manifest, result.trajectory, result.bundle_id, output)
        try:
            mode = stat.S_IMODE(output.stat().st_mode)
            if os.name != "nt" and mode != 0o600:
                os.chmod(output, 0o600)
        except OSError:
            pass
        return result
    except FileExistsError as error:
        raise TrajectoryError("output-exists", "Bundle output already exists and was not replaced.") from error
    finally:
        if fd != -1:
            os.close(fd)
        try:
            temp_path.unlink()
        except OSError:
            pass


def _looks_schema_v1(manifest: object) -> bool:
    return (
        isinstance(manifest, Mapping)
        and manifest.get("schema_version") == 1
        and isinstance(manifest.get("exporter"), Mapping)
        and manifest["exporter"].get("name") == "svc"
        and isinstance(manifest.get("provider"), Mapping)
        and isinstance(manifest.get("thread"), Mapping)
        and isinstance(manifest.get("artifact"), Mapping)
    )


def _member_open(archive: Any, info: Any, callback: Any) -> BinaryIO:
    stream = callback(archive, info) if callback is not None else archive.open(info, mode="r")
    if not hasattr(stream, "read"):
        _fail("Bundle member opener returned a non-readable stream.")
    return stream


def _read_member(archive: Any, info: Any, callback: Any, limit: int) -> bytes:
    if info.file_size > limit:
        _fail("Bundle member byte bound exceeded.", code="member-limit-reached")
    stream = _member_open(archive, info, callback)
    try:
        data = stream.read(limit + 1)
    finally:
        stream.close()
    if not isinstance(data, bytes) or len(data) > limit:
        _fail("Bundle member byte bound exceeded.", code="member-limit-reached")
    return data


def validate_bundle(path: Any, *, member_open: Any = None) -> ValidatedBundle:
    """Validate a portable bundle without extracting it.

    The optional opener is intentionally narrow and exists for tests to prove
    that a schema-v1 manifest is the only member opened before rejection.
    """

    import os
    import stat
    import zipfile
    from pathlib import Path
    input_path = Path(path)
    try:
        before = input_path.lstat()
    except OSError as error:
        raise TrajectoryError("bundle-input-unreadable", "Bundle input cannot be inspected.") from error
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        _fail("Bundle input must be a regular non-link file.", code="bundle-input-unsafe")
    if before.st_size > MAX_SCHEMA_V2_ZIP_BYTES:
        _fail("Bundle ZIP byte bound exceeded.", code="zip-limit-reached")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = -1
    try:
        descriptor = os.open(input_path, flags)
        opened = os.fstat(descriptor)
        before_identity = (
            before.st_dev,
            before.st_ino,
            stat.S_IFMT(before.st_mode),
            before.st_size,
            before.st_mtime_ns,
        )
        opened_identity = (
            opened.st_dev,
            opened.st_ino,
            stat.S_IFMT(opened.st_mode),
            opened.st_size,
            opened.st_mtime_ns,
        )
        if (
            not stat.S_ISREG(opened.st_mode)
            or before_identity != opened_identity
        ):
            _fail(
                "Bundle input changed while being opened.",
                code="bundle-input-mutated",
            )
        with os.fdopen(descriptor, "rb", closefd=True) as raw:
            descriptor = -1
            with zipfile.ZipFile(raw, mode="r") as archive:
                infos = archive.infolist()
                names = [info.filename for info in infos]
                if len(names) != len(set(names)):
                    _fail("Bundle ZIP contains duplicate member names.", code="bundle-invalid")
                for info in infos:
                    if not _safe_member_name(info.filename) or info.flag_bits & 0x1 or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                        _fail("Bundle ZIP contains an unsafe member.", code="bundle-invalid")
                    if info.is_dir() or ((info.external_attr >> 16) & 0o170000) not in {0, stat.S_IFREG}:
                        _fail("Bundle ZIP member is not a regular file.", code="bundle-invalid")
                if "manifest.json" not in names:
                    _fail("Bundle ZIP has no manifest member.", code="bundle-invalid")
                manifest_info = next(info for info in infos if info.filename == "manifest.json")
                manifest_bytes = _read_member(archive, manifest_info, member_open, MAX_MANIFEST_BYTES)
                manifest = _strict_loads(manifest_bytes[:-1] if manifest_bytes.endswith(b"\n") else manifest_bytes)
                if _looks_schema_v1(manifest):
                    raise TrajectoryError("unsupported-agent-thread-bundle-schema", "Schema-v1 agent-thread archives are unsupported inputs; recollect from the provider source.")
                if (
                    not manifest_bytes.endswith(b"\n")
                    or canonical_json_bytes(manifest, newline=True)
                    != manifest_bytes
                ):
                    _fail(
                        "Bundle manifest is not canonical JSON with final LF.",
                        code="bundle-invalid",
                    )
                if set(names) != {"manifest.json", "trajectory.jsonl"}:
                    _fail("Bundle ZIP contains unexpected members.", code="bundle-invalid")
                trajectory_info = next(info for info in infos if info.filename == "trajectory.jsonl")
                trajectory_bytes = _read_member(archive, trajectory_info, member_open, MAX_TRAJECTORY_BYTES)
                trajectory = validate_trajectory_bytes(trajectory_bytes)
                validate_manifest(manifest, trajectory=trajectory)
                final_opened = os.fstat(raw.fileno())
                try:
                    after = input_path.lstat()
                except OSError as error:
                    raise TrajectoryError("bundle-input-mutated", "Bundle input disappeared during validation.") from error
                final_identity = (
                    final_opened.st_dev,
                    final_opened.st_ino,
                    stat.S_IFMT(final_opened.st_mode),
                    final_opened.st_size,
                    final_opened.st_mtime_ns,
                )
                after_identity = (
                    after.st_dev,
                    after.st_ino,
                    stat.S_IFMT(after.st_mode),
                    after.st_size,
                    after.st_mtime_ns,
                )
                if (
                    stat.S_ISLNK(after.st_mode)
                    or not stat.S_ISREG(after.st_mode)
                    or before_identity != final_identity
                    or before_identity != after_identity
                ):
                    _fail("Bundle input changed during validation.", code="bundle-input-mutated")
                return ValidatedBundle(manifest, trajectory, str(manifest["bundle_id"]), input_path)
    except TrajectoryError:
        raise
    except (OSError, zipfile.BadZipFile, KeyError, ValueError) as error:
        raise TrajectoryError("bundle-invalid", "Bundle ZIP is not a valid schema-v2 artifact.") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


__all__ = [
    "BUNDLE_FORMAT", "BUNDLE_SCHEMA_VERSION", "CONTENT_PROFILE", "DEFAULT_NORMALIZATION_POLICY", "EncodedTrajectory", "MAX_NATIVE_JSON_DEPTH",
    "MAX_NATIVE_LINE_BYTES", "MAX_RECORDS", "MAX_TRAJECTORY_BYTES", "NormalizationPolicy",
    "TRAJECTORY_SCHEMA", "TrajectoryCollector", "TrajectoryError", "ValidatedBundle", "ValidatedTrajectory",
    "build_bundle_id", "build_manifest", "canonical_json_bytes", "encode_trajectory", "policy_dict", "validate_bundle", "validate_manifest", "validate_record", "validate_trajectory_bytes", "write_bundle", "write_bundle_stream", "zero_lossiness",
]
