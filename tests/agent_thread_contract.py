"""Small public-boundary evidence corpus shared by Agent-thread contract tests."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from svc_cli.telemetry.evidence import (
    build_evidence_manifest,
    build_native_index,
    write_evidence_stream,
)
from svc_cli.telemetry.trajectory import (
    RECORD_TYPES,
    build_manifest,
    canonical_json_bytes,
    zero_lossiness,
)


THREAD_REF = "thread_" + "a" * 64


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    path: Path
    evidence_id: str
    native: bytes


def message_record(
    native_index: int,
    role: str,
    content: str,
) -> dict[str, object]:
    return {
        "type": "message",
        "record_id": f"r{native_index:06d}",
        "record_index": native_index,
        "timestamp": f"2026-01-01T00:00:0{native_index}Z",
        "source_ref": {"event_index": native_index},
        "role": role,
        "content": content,
        "content_meta": {
            "truncated": False,
            "observed_code_points": len(content),
            "retained_code_points": len(content),
            "strategy": "none",
        },
        "task_refs": [],
    }


def write_evidence_bundle(
    directory: Path,
    name: str,
    frames: Sequence[bytes],
    *,
    records: Sequence[Mapping[str, object]] = (),
    projection_status: str = "ready",
    incomplete_last: bool = False,
) -> EvidenceBundle:
    native = b"".join(frames)
    offsets: list[int] = []
    native_ranges: list[tuple[int, int, dict[str, int], str]] = []
    offset = 0
    for index, frame in enumerate(frames):
        offsets.append(offset)
        native_ranges.append(
            (
                offset,
                offset + len(frame),
                {"event_index": index, "line": index, "byte_offset": offset},
                (
                    "incomplete"
                    if incomplete_last and index == len(frames) - 1
                    else "complete"
                ),
            )
        )
        offset += len(frame)
    native_index = build_native_index(native, native_ranges)

    trajectory_records: list[dict[str, object]] = [_meta()]
    for source in records:
        record = copy.deepcopy(dict(source))
        source_ref = dict(record["source_ref"])
        event_index = source_ref["event_index"]
        assert isinstance(event_index, int)
        source_ref.update(
            {
                "line": event_index,
                "byte_offset": offsets[event_index],
                "native_record_id": f"n{event_index:06d}",
            }
        )
        record["source_ref"] = source_ref
        trajectory_records.append(record)
    trajectory = b"".join(
        canonical_json_bytes(record, newline=True)
        for record in trajectory_records
    )
    records_by_type = {
        record_type: sum(
            record["type"] == record_type for record in trajectory_records
        )
        for record_type in RECORD_TYPES
    }
    projection = build_manifest(
        trajectory_source=trajectory,
        source={
            "provider_id": "codex",
            "adapter_id": "codex-rollout-v1",
            "source_format": "rollout-v1",
            "thread_ref": THREAD_REF,
            "source_status": "stable",
        },
        result_status=projection_status,
        capabilities={
            "reasoning": "absent",
            "tool_linkage": "absent",
            "context": "absent",
            "task_references": "available",
            "explicit_concurrency": "unavailable",
            "timestamps": "full" if records else "absent",
            "terminal_events": "unavailable",
        },
        lossiness=zero_lossiness(),
        diagnostics=[],
        counts={
            "source_bytes_read": len(native),
            "source_events_seen": len(frames),
            "records_emitted": len(trajectory_records),
            "trajectory_bytes": len(trajectory),
            "records_by_type": records_by_type,
            "messages_by_role": {
                role: sum(
                    record.get("type") == "message"
                    and record.get("role") == role
                    for record in trajectory_records
                )
                for role in ("user", "assistant")
            },
            "tool_calls": records_by_type["tool_call"],
            "tool_results": records_by_type["tool_result"],
            "task_references": sum(
                len(record.get("task_refs", []))
                for record in trajectory_records
            ),
            "diagnostics_emitted": 0,
            "diagnostics_suppressed": 0,
        },
    )
    manifest = build_evidence_manifest(
        native=native,
        native_index=native_index,
        projection=projection,
        trajectory=trajectory,
    )
    target = directory / f"{name}.zip"
    with target.open("x+b") as stream:
        validated = write_evidence_stream(
            stream,
            manifest,
            native,
            native_index,
            trajectory,
        )
    return EvidenceBundle(target, validated.evidence_id, native)


def _meta() -> dict[str, object]:
    return {
        "type": "meta",
        "record_id": "r000000",
        "record_index": 0,
        "timestamp": None,
        "source_ref": {"event_index": None, "component": "meta"},
        "trajectory_schema": "svc.trajectory/v1",
        "provider_id": "codex",
        "adapter_id": "codex-rollout-v1",
        "source_format": "rollout-v1",
        "thread_ref": THREAD_REF,
        "workspace": {
            "status": "missing",
            "flavor": None,
            "label": None,
            "ref": None,
            "label_truncated": False,
            "observed_code_points": 0,
            "retained_code_points": 0,
        },
        "content_profile": "bounded-normalized-v1",
    }
