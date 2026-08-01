"""Schema-v3 immutable native evidence bundles.

The evidence core is deliberately independent from providers and archive
collection.  A v3 bundle keeps the captured native authority beside a
validated framing index and the existing v2 trajectory projection.  Query and
read layers can therefore resolve native records without treating the
projection as a substitute for collected content.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, BinaryIO, Iterable, Mapping, Never
import zipfile

from .trajectory import (
    MAX_MANIFEST_BYTES,
    MAX_TRAJECTORY_BYTES,
    TrajectoryError,
    ValidatedTrajectory,
    canonical_json_bytes,
    validate_manifest,
    validate_trajectory_bytes,
)


EVIDENCE_FORMAT = "svc-agent-thread-evidence"
EVIDENCE_SCHEMA_VERSION = 3
EVIDENCE_MEMBERS = (
    "manifest.json",
    "native.bin",
    "native-index.jsonl",
    "trajectory.jsonl",
)
MAX_NATIVE_BYTES = 256 * 1024 * 1024
MAX_NATIVE_INDEX_BYTES = 32 * 1024 * 1024
MAX_EVIDENCE_ZIP_BYTES = 384 * 1024 * 1024
_RECORD_ID = re.compile(r"^n[0-9]{6}$")
_HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ROOT_KEYS = {"format", "schema_version", "evidence_id", "native", "native_index", "projection", "capture"}
_MEMBER_META_KEYS = {"member", "sha256", "bytes"}
_INDEX_META_KEYS = _MEMBER_META_KEYS | {"records"}
_CAPTURE_KEYS = {"status", "unknown_remainder", "representation"}


class EvidenceError(ValueError):
    """Stable schema-v3 evidence failure."""

    def __init__(self, code: str, message: str, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = MappingProxyType(dict(details or {}))

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            result["details"] = dict(self.details)
        return result


@dataclass(frozen=True, slots=True)
class NativeIndexEntry:
    """One contiguous native frame in ``native.bin``."""

    native_record_id: str
    native_index: int
    byte_start: int
    byte_end: int
    sha256: str
    representation: str
    frame_status: str
    source_coordinate: Mapping[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "native_record_id": self.native_record_id,
            "native_index": self.native_index,
            "byte_start": self.byte_start,
            "byte_end": self.byte_end,
            "sha256": self.sha256,
            "representation": self.representation,
            "frame_status": self.frame_status,
            "source_coordinate": dict(self.source_coordinate),
        }


@dataclass(frozen=True, slots=True)
class ValidatedEvidence:
    """Validated schema-v3 members and their nested v2 projection."""

    manifest: Mapping[str, Any]
    native: bytes
    native_index: tuple[NativeIndexEntry, ...]
    trajectory: ValidatedTrajectory
    evidence_id: str
    path: Any = None

    @property
    def native_bytes(self) -> bytes:
        return self.native

    @property
    def native_index_bytes(self) -> bytes:
        return encode_native_index(self.native_index)


def _fail(code: str, message: str, **details: Any) -> Never:
    raise EvidenceError(code, message, details)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _strict_loads(value: bytes) -> Any:
    def pairs(items: list[tuple[str, object]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in items:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = item
        return result

    try:
        return json.loads(
            value.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise EvidenceError("invalid-evidence-json", "Evidence member is not strict UTF-8 JSON.") from error


def _coerce_bytes(value: bytes | bytearray | memoryview, *, name: str) -> bytes:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        _fail("invalid-evidence-member", f"{name} must be bytes.")
    return bytes(value)


def _coordinate(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping) or set(value) != {"event_index", "line", "byte_offset"}:
        _fail("invalid-native-index", "source_coordinate must contain event_index, line, and byte_offset.")
    result: dict[str, int] = {}
    for key in ("event_index", "line", "byte_offset"):
        item = value[key]
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            _fail("invalid-native-index", "source_coordinate values must be non-negative integers.")
        result[key] = item
    return result


def _entry_from_mapping(value: Any) -> NativeIndexEntry:
    if not isinstance(value, Mapping) or set(value) != {
        "native_record_id",
        "native_index",
        "byte_start",
        "byte_end",
        "sha256",
        "representation",
        "frame_status",
        "source_coordinate",
    }:
        _fail("invalid-native-index", "Native index entry has an invalid shape.")
    record_id = value["native_record_id"]
    if not isinstance(record_id, str) or not _RECORD_ID.fullmatch(record_id):
        _fail("invalid-native-index", "Native record ID has an invalid form.")
    integer_values: dict[str, int] = {}
    for key in ("native_index", "byte_start", "byte_end"):
        item = value[key]
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            _fail("invalid-native-index", f"{key} must be a non-negative integer.")
        integer_values[key] = item
    digest = value["sha256"]
    if not isinstance(digest, str) or not _HEX_DIGEST.fullmatch(digest):
        _fail("invalid-native-index", "Native frame digest is invalid.")
    if value["representation"] != "provider-bytes":
        _fail("invalid-native-index", "Native frame representation is invalid.")
    frame_status = value["frame_status"]
    if not isinstance(frame_status, str) or frame_status not in {"complete", "incomplete"}:
        _fail("invalid-native-index", "Native frame status is invalid.")
    return NativeIndexEntry(
        native_record_id=record_id,
        native_index=integer_values["native_index"],
        byte_start=integer_values["byte_start"],
        byte_end=integer_values["byte_end"],
        sha256=digest,
        representation="provider-bytes",
        frame_status=frame_status,
        source_coordinate=_coordinate(value["source_coordinate"]),
    )


def encode_native_index(entries: Iterable[NativeIndexEntry | Mapping[str, Any]]) -> bytes:
    """Encode entries as canonical JSONL in native ordinal order."""

    materialized = tuple(
        entry if isinstance(entry, NativeIndexEntry) else _entry_from_mapping(entry)
        for entry in entries
    )
    data = b"".join(canonical_json_bytes(entry.as_dict(), newline=True) for entry in materialized)
    if len(data) > MAX_NATIVE_INDEX_BYTES:
        _fail("native-index-limit-reached", "Native index byte bound exceeded.")
    return data


def build_native_index(
    native: bytes,
    frames: Iterable[Mapping[str, Any] | tuple[int, int, Mapping[str, int], str]],
) -> bytes:
    """Build a canonical native index and derive IDs/digests from byte ranges."""

    native_bytes = _coerce_bytes(native, name="native")
    if len(native_bytes) > MAX_NATIVE_BYTES:
        _fail("native-limit-reached", "Native byte bound exceeded.")
    entries: list[NativeIndexEntry] = []
    for index, frame in enumerate(frames):
        if isinstance(frame, Mapping):
            start = frame.get("byte_start")
            end = frame.get("byte_end")
            coordinate = frame.get("source_coordinate")
            status = frame.get("frame_status", "complete")
        else:
            if len(frame) != 4:
                _fail("invalid-native-index", "Frame tuple must contain start, end, coordinate, and status.")
            start, end, coordinate, status = frame
        if isinstance(start, bool) or not isinstance(start, int) or isinstance(end, bool) or not isinstance(end, int):
            _fail("invalid-native-index", "Frame byte bounds must be integers.")
        if start < 0 or end <= start or end > len(native_bytes):
            _fail("invalid-native-index", "Frame byte bounds are outside native content.")
        if not isinstance(status, str) or status not in {"complete", "incomplete"}:
            _fail("invalid-native-index", "Frame status is invalid.")
        frame_bytes = native_bytes[start:end]
        entries.append(
            NativeIndexEntry(
                native_record_id=f"n{index:06d}",
                native_index=index,
                byte_start=start,
                byte_end=end,
                sha256=_sha256(frame_bytes),
                representation="provider-bytes",
                frame_status=str(status),
                source_coordinate=_coordinate(coordinate),
            )
        )
    _validate_native_index(native_bytes, tuple(entries))
    return encode_native_index(entries)


def _parse_native_index(data: bytes) -> tuple[NativeIndexEntry, ...]:
    if len(data) > MAX_NATIVE_INDEX_BYTES:
        _fail("native-index-limit-reached", "Native index byte bound exceeded.")
    if not data:
        return ()
    if not data.endswith(b"\n"):
        _fail("invalid-native-index", "Native index must end with a newline.")
    entries: list[NativeIndexEntry] = []
    for line in data.splitlines(keepends=True):
        if not line.endswith(b"\n"):
            _fail("invalid-native-index", "Native index lines must end with a newline.")
        raw = line[:-1]
        if not raw:
            _fail("invalid-native-index", "Native index cannot contain blank lines.")
        value = _strict_loads(raw)
        if canonical_json_bytes(value, newline=True) != line:
            _fail("invalid-native-index", "Native index must use canonical JSONL.")
        entries.append(_entry_from_mapping(value))
    return tuple(entries)


def _validate_native_index(native: bytes, entries: tuple[NativeIndexEntry, ...]) -> None:
    expected_start = 0
    incomplete_seen = False
    for index, entry in enumerate(entries):
        if entry.native_index != index or entry.native_record_id != f"n{index:06d}":
            _fail("invalid-native-index", "Native index ordinals and IDs must be contiguous.")
        if entry.byte_start != expected_start or entry.byte_end <= entry.byte_start or entry.byte_end > len(native):
            _fail("invalid-native-index", "Native index byte ranges must exactly cover native content.")
        if _sha256(native[entry.byte_start : entry.byte_end]) != entry.sha256:
            _fail("native-digest-mismatch", "Native frame digest does not match native content.")
        if entry.frame_status == "incomplete":
            if incomplete_seen or index != len(entries) - 1:
                _fail("invalid-native-index", "Only the final native frame may be incomplete.")
            incomplete_seen = True
        expected_start = entry.byte_end
    if expected_start != len(native):
        _fail("invalid-native-index", "Native index does not cover every retained native byte.")


def _validate_trajectory_native_refs(
    trajectory: ValidatedTrajectory,
    entries: tuple[NativeIndexEntry, ...],
) -> None:
    """Bind every derived record to one complete captured native frame.

    The leading meta record is synthetic and must remain unmapped.  All other
    records are derived claims over native evidence, so accepting a missing,
    unknown, or incomplete mapping would make the projection look more
    authoritative than the captured source.
    """

    by_id = {entry.native_record_id: entry for entry in entries}
    for record in trajectory.records:
        source_ref = record.get("source_ref")
        if record.get("type") == "meta":
            if isinstance(source_ref, Mapping) and "native_record_id" in source_ref:
                _fail(
                    "native-reference-invalid",
                    "The synthetic meta record cannot carry a native_record_id.",
                    record_id=record.get("record_id"),
                )
            continue
        if not isinstance(source_ref, Mapping) or "native_record_id" not in source_ref:
            _fail(
                "native-reference-missing",
                "Every non-meta trajectory record requires a native_record_id.",
                record_id=record.get("record_id"),
            )
        native_record_id = source_ref["native_record_id"]
        entry = by_id.get(native_record_id)
        if entry is None:
            _fail(
                "native-reference-unresolved",
                "Trajectory native_record_id does not resolve to a native frame.",
                record_id=record.get("record_id"),
                native_record_id=native_record_id,
            )
        if entry.frame_status != "complete":
            _fail(
                "native-reference-incomplete",
                "Trajectory records may only resolve to complete native frames.",
                record_id=record.get("record_id"),
                native_record_id=native_record_id,
            )


def _validate_member_meta(value: Any, *, keys: set[str], member: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        _fail("invalid-evidence-manifest", f"Manifest {member} metadata has an invalid shape.")
    if value.get("member") != member:
        _fail("invalid-evidence-manifest", f"Manifest member name for {member} is invalid.")
    digest = value.get("sha256")
    size = value.get("bytes")
    if not isinstance(digest, str) or not _HEX_DIGEST.fullmatch(digest):
        _fail("invalid-evidence-manifest", f"Manifest digest for {member} is invalid.")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        _fail("invalid-evidence-manifest", f"Manifest byte count for {member} is invalid.")
    result = dict(value)
    if "records" in keys:
        records = value.get("records")
        if isinstance(records, bool) or not isinstance(records, int) or records < 0:
            _fail("invalid-evidence-manifest", "Native index record count is invalid.")
    return result


def _validate_capture(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _CAPTURE_KEYS:
        _fail("invalid-evidence-manifest", "Manifest capture metadata has an invalid shape.")
    status = value.get("status")
    if not isinstance(status, str) or status not in {"complete", "partial"}:
        _fail("invalid-evidence-manifest", "Manifest capture status is invalid.")
    unknown = value.get("unknown_remainder")
    if not isinstance(unknown, bool):
        _fail("invalid-evidence-manifest", "Manifest capture unknown_remainder must be boolean.")
    if value.get("representation") != "provider-bytes":
        _fail("invalid-evidence-manifest", "Manifest capture representation is invalid.")
    return {"status": status, "unknown_remainder": unknown, "representation": "provider-bytes"}


def build_evidence_id(
    manifest: Mapping[str, Any],
    native: bytes,
    native_index: bytes,
    trajectory: bytes,
) -> str:
    """Build the digest identity for one schema-v3 evidence set."""

    projection = manifest.get("projection")
    if not isinstance(projection, Mapping):
        _fail("invalid-evidence-manifest", "Evidence projection must be an object.")
    identity = {
        "native": {"sha256": _sha256(native), "bytes": len(native)},
        "native_index": {"sha256": _sha256(native_index), "bytes": len(native_index)},
        "projection": _plain(projection),
        "capture": _plain(manifest.get("capture")),
        "trajectory_sha256": _sha256(trajectory),
    }
    return _sha256(
        b"svc-agent-thread-evidence-v3\0"
        + native
        + b"\0"
        + native_index
        + b"\0"
        + trajectory
        + b"\0"
        + canonical_json_bytes(identity)
    )


def build_evidence_manifest(
    *,
    native: bytes,
    native_index: bytes | Iterable[NativeIndexEntry | Mapping[str, Any]],
    projection: Mapping[str, Any],
    trajectory: bytes,
    capture: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Build and validate a schema-v3 manifest around a v2 projection."""

    native_bytes = _coerce_bytes(native, name="native")
    if len(native_bytes) > MAX_NATIVE_BYTES:
        _fail("native-limit-reached", "Native byte bound exceeded.")
    index_bytes = (
        _coerce_bytes(native_index, name="native-index")
        if isinstance(native_index, (bytes, bytearray, memoryview))
        else encode_native_index(native_index)
    )
    index_entries = _parse_native_index(index_bytes)
    _validate_native_index(native_bytes, index_entries)
    incomplete = any(entry.frame_status == "incomplete" for entry in index_entries)
    capture_value = _validate_capture(
        capture
        if capture is not None
        else {
            "status": "partial" if incomplete else "complete",
            "unknown_remainder": incomplete,
            "representation": "provider-bytes",
        }
    )
    if incomplete and (capture_value["status"] != "partial" or capture_value["unknown_remainder"] is not True):
        _fail("invalid-evidence-manifest", "Incomplete native frames require partial capture with unknown remainder.")
    trajectory_bytes = _coerce_bytes(trajectory, name="trajectory")
    try:
        validated_trajectory = validate_trajectory_bytes(trajectory_bytes)
        validate_manifest(projection, trajectory=validated_trajectory)
    except TrajectoryError as error:
        raise EvidenceError(error.code, error.message, error.details) from error
    manifest: dict[str, Any] = {
        "format": EVIDENCE_FORMAT,
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "evidence_id": "0" * 64,
        "native": {
            "member": "native.bin",
            "sha256": _sha256(native_bytes),
            "bytes": len(native_bytes),
        },
        "native_index": {
            "member": "native-index.jsonl",
            "sha256": _sha256(index_bytes),
            "bytes": len(index_bytes),
            "records": len(index_entries),
        },
        "projection": _plain(projection),
        "capture": capture_value,
    }
    manifest["evidence_id"] = build_evidence_id(manifest, native_bytes, index_bytes, trajectory_bytes)
    validate_evidence_members(manifest, native_bytes, index_bytes, trajectory_bytes)
    return manifest


def validate_evidence_manifest(
    manifest: Mapping[str, Any],
    *,
    native: bytes | None = None,
    native_index: bytes | None = None,
    trajectory: bytes | None = None,
) -> Mapping[str, Any]:
    """Validate root schema-v3 metadata, optionally against all member bytes."""

    if isinstance(manifest, Mapping):
        legacy_schema = manifest.get("schema_version")
        if type(legacy_schema) is int and legacy_schema in {1, 2}:
            _fail("unsupported-agent-thread-bundle-schema", "Schema-v1/v2 bundles require recollection into schema v3.")
    if not isinstance(manifest, Mapping) or set(manifest) != _ROOT_KEYS:
        _fail("invalid-evidence-manifest", "Evidence manifest has an invalid root shape.")
    schema_version = manifest.get("schema_version")
    if manifest["format"] != EVIDENCE_FORMAT or schema_version != EVIDENCE_SCHEMA_VERSION:
        if type(schema_version) is int and schema_version in {1, 2}:
            _fail("unsupported-agent-thread-bundle-schema", "Schema-v1/v2 bundles require recollection into schema v3.")
        _fail("invalid-evidence-manifest", "Evidence format or schema version is invalid.")
    evidence_id = manifest["evidence_id"]
    if not isinstance(evidence_id, str) or not _HEX_DIGEST.fullmatch(evidence_id):
        _fail("invalid-evidence-manifest", "Evidence ID is invalid.")
    native_meta = _validate_member_meta(manifest["native"], keys=_MEMBER_META_KEYS, member="native.bin")
    index_meta = _validate_member_meta(manifest["native_index"], keys=_INDEX_META_KEYS, member="native-index.jsonl")
    capture = _validate_capture(manifest["capture"])
    projection = manifest["projection"]
    if not isinstance(projection, Mapping):
        _fail("invalid-evidence-manifest", "Evidence projection must be an object.")
    projection_schema_version = projection.get("schema_version")
    if type(projection_schema_version) is int and projection_schema_version in {1, 2} and projection_schema_version != 2:
        _fail("unsupported-agent-thread-bundle-schema", "Only a schema-v2 projection may be nested in schema-v3 evidence.")
    if projection_schema_version != 2:
        _fail("invalid-evidence-manifest", "Evidence projection must be schema v2.")
    try:
        validate_manifest(projection)
    except TrajectoryError as error:
        raise EvidenceError(error.code, error.message, error.details) from error
    if native is None or native_index is None or trajectory is None:
        return manifest
    native_bytes = _coerce_bytes(native, name="native")
    index_bytes = _coerce_bytes(native_index, name="native-index")
    trajectory_bytes = _coerce_bytes(trajectory, name="trajectory")
    if len(native_bytes) != native_meta["bytes"] or _sha256(native_bytes) != native_meta["sha256"]:
        _fail("native-digest-mismatch", "Native member does not match its manifest digest.")
    if len(index_bytes) != index_meta["bytes"] or _sha256(index_bytes) != index_meta["sha256"]:
        _fail("native-index-digest-mismatch", "Native index does not match its manifest digest.")
    entries = _parse_native_index(index_bytes)
    if len(entries) != index_meta["records"]:
        _fail("invalid-native-index", "Native index record count disagrees with its manifest.")
    _validate_native_index(native_bytes, entries)
    incomplete = any(entry.frame_status == "incomplete" for entry in entries)
    if incomplete and (capture["status"] != "partial" or capture["unknown_remainder"] is not True):
        _fail("invalid-evidence-manifest", "Incomplete native frames require partial capture with unknown remainder.")
    try:
        validated_trajectory = validate_trajectory_bytes(trajectory_bytes)
        validate_manifest(projection, trajectory=validated_trajectory)
    except TrajectoryError as error:
        raise EvidenceError(error.code, error.message, error.details) from error
    expected = build_evidence_id(manifest, native_bytes, index_bytes, trajectory_bytes)
    if expected != evidence_id:
        _fail("evidence-id-mismatch", "Evidence ID does not match its members and projection.")
    return manifest


def validate_evidence_members(
    manifest: Mapping[str, Any],
    native: bytes,
    native_index: bytes,
    trajectory: bytes,
) -> ValidatedEvidence:
    """Validate in-memory v3 members and return a reusable evidence value."""

    native_bytes = _coerce_bytes(native, name="native")
    index_bytes = _coerce_bytes(native_index, name="native-index")
    trajectory_bytes = _coerce_bytes(trajectory, name="trajectory")
    validate_evidence_manifest(
        manifest,
        native=native_bytes,
        native_index=index_bytes,
        trajectory=trajectory_bytes,
    )
    entries = _parse_native_index(index_bytes)
    _validate_native_index(native_bytes, entries)
    validated_trajectory = validate_trajectory_bytes(trajectory_bytes)
    _validate_trajectory_native_refs(validated_trajectory, entries)
    return ValidatedEvidence(
        manifest=manifest,
        native=native_bytes,
        native_index=entries,
        trajectory=validated_trajectory,
        evidence_id=str(manifest["evidence_id"]),
    )


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (0o644 & 0xFFFF) << 16
    return info


def _write_member(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    archive.writestr(_zip_info(name), data)


def write_evidence_stream(
    binary_file: BinaryIO,
    manifest: Mapping[str, Any],
    native: bytes,
    native_index: bytes,
    trajectory: bytes,
) -> ValidatedEvidence:
    """Write exactly four schema-v3 members to a caller-owned binary stream."""

    validated = validate_evidence_members(manifest, native, native_index, trajectory)
    native_bytes = validated.native
    native_index_bytes = validated.native_index_bytes
    trajectory_bytes = validated.trajectory.trajectory_bytes
    manifest_bytes = canonical_json_bytes(manifest, newline=True)
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        _fail("manifest-limit-reached", "Evidence manifest byte bound exceeded.")
    if len(native_bytes) > MAX_NATIVE_BYTES or len(native_index_bytes) > MAX_NATIVE_INDEX_BYTES:
        _fail("member-limit-reached", "Evidence member byte bound exceeded.")
    try:
        binary_file.seek(0)
        binary_file.truncate(0)
        with zipfile.ZipFile(binary_file, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            _write_member(archive, "manifest.json", manifest_bytes)
            _write_member(archive, "native.bin", native_bytes)
            _write_member(archive, "native-index.jsonl", native_index_bytes)
            _write_member(archive, "trajectory.jsonl", trajectory_bytes)
        binary_file.flush()
        end = binary_file.tell()
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        raise EvidenceError("evidence-write-failed", "Evidence ZIP could not be written.") from error
    if end > MAX_EVIDENCE_ZIP_BYTES:
        _fail("zip-limit-reached", "Evidence ZIP byte bound exceeded.")
    return validated


def _read_member(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    limit: int,
) -> bytes:
    if info.file_size > limit:
        _fail("member-limit-reached", "Evidence member byte bound exceeded.")
    with archive.open(info, mode="r") as stream:
        data = stream.read(limit + 1)
    if not isinstance(data, bytes) or len(data) > limit:
        _fail("member-limit-reached", "Evidence member byte bound exceeded.")
    return data


def validate_evidence(path: Any) -> ValidatedEvidence:
    """Validate one bounded, canonical schema-v3 ZIP."""

    input_path = Path(path)
    try:
        if input_path.stat().st_size > MAX_EVIDENCE_ZIP_BYTES:
            _fail("zip-limit-reached", "Evidence ZIP byte bound exceeded.")
        with zipfile.ZipFile(input_path, mode="r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                _fail("bundle-invalid", "Evidence ZIP contains duplicate members.")
            try:
                manifest_info = next(
                    info for info in infos if info.filename == "manifest.json"
                )
            except StopIteration:
                _fail("bundle-invalid", "Evidence ZIP is missing manifest.json.")
            manifest_bytes = _read_member(
                archive,
                manifest_info,
                MAX_MANIFEST_BYTES,
            )
            if not manifest_bytes.endswith(b"\n"):
                _fail("bundle-invalid", "Evidence manifest must end with a newline.")
            manifest = _strict_loads(manifest_bytes[:-1])
            if not isinstance(manifest, Mapping):
                _fail(
                    "invalid-evidence-manifest",
                    "Evidence manifest must be an object.",
                )
            schema_version = manifest.get("schema_version")
            if type(schema_version) is int and schema_version in {1, 2}:
                _fail(
                    "unsupported-agent-thread-bundle-schema",
                    "Schema-v1/v2 bundles require recollection into schema v3.",
                )
            if canonical_json_bytes(manifest, newline=True) != manifest_bytes:
                _fail(
                    "bundle-invalid",
                    "Evidence manifest must use canonical JSON.",
                )
            if len(infos) != len(EVIDENCE_MEMBERS) or set(names) != set(
                EVIDENCE_MEMBERS
            ):
                _fail(
                    "bundle-invalid",
                    "Evidence ZIP must contain exactly the four schema-v3 members.",
                )
            by_name = {info.filename: info for info in infos}
            native = _read_member(
                archive,
                by_name["native.bin"],
                MAX_NATIVE_BYTES,
            )
            native_index = _read_member(
                archive,
                by_name["native-index.jsonl"],
                MAX_NATIVE_INDEX_BYTES,
            )
            trajectory = _read_member(
                archive,
                by_name["trajectory.jsonl"],
                MAX_TRAJECTORY_BYTES,
            )
            validated = validate_evidence_members(
                manifest,
                native,
                native_index,
                trajectory,
            )
            return ValidatedEvidence(
                validated.manifest,
                validated.native,
                validated.native_index,
                validated.trajectory,
                validated.evidence_id,
                input_path,
            )
    except EvidenceError:
        raise
    except (
        EOFError,
        KeyError,
        NotImplementedError,
        OSError,
        RuntimeError,
        ValueError,
        zipfile.BadZipFile,
    ) as error:
        raise EvidenceError(
            "bundle-invalid",
            "Evidence ZIP is not a valid schema-v3 artifact.",
        ) from error


__all__ = [
    "EVIDENCE_FORMAT",
    "EVIDENCE_MEMBERS",
    "EVIDENCE_SCHEMA_VERSION",
    "EvidenceError",
    "MAX_EVIDENCE_ZIP_BYTES",
    "MAX_NATIVE_BYTES",
    "MAX_NATIVE_INDEX_BYTES",
    "NativeIndexEntry",
    "ValidatedEvidence",
    "build_evidence_id",
    "build_evidence_manifest",
    "build_native_index",
    "encode_native_index",
    "validate_evidence",
    "validate_evidence_manifest",
    "validate_evidence_members",
    "write_evidence_stream",
]
