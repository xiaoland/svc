from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import stat
import zipfile

import pytest

from svc_cli.errors import SvcError
from svc_cli.telemetry.agent_threads import (
    NormalizationResult,
    ProviderContext,
    SourceStatus,
    ThreadSelection,
)
from svc_cli.telemetry.archive import (
    _canonical_evidence_output,
    _finalize_normalization,
    _verify_output_parent,
    normalize_agent_thread_evidence,
    write_agent_thread_evidence,
)
from svc_cli.telemetry.evidence import validate_evidence
from svc_cli.telemetry.providers.codex_rollout import CodexRolloutProvider
from svc_cli.telemetry.trajectory import (
    DEFAULT_NORMALIZATION_POLICY,
    TrajectoryCollector,
    canonical_json_bytes,
    zero_lossiness,
)


THREAD_REF = "thread_" + ("1" * 64)


def _meta() -> dict[str, object]:
    return {
        "type": "meta",
        "record_id": "r000000",
        "record_index": 0,
        "timestamp": None,
        "source_ref": {"event_index": None, "component": "meta"},
        "trajectory_schema": "svc.trajectory/v1",
        "provider_id": "synthetic",
        "adapter_id": "synthetic-v1",
        "source_format": "fixture-v1",
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


def _message() -> dict[str, object]:
    content = "bounded content"
    return {
        "type": "message",
        "record_id": "r000001",
        "record_index": 1,
        "timestamp": "2026-07-28T00:00:00Z",
        "source_ref": {
            "event_index": 0,
            "line": 0,
            "component_index": 0,
            "component": "message",
        },
        "role": "user",
        "content": content,
        "content_meta": {
            "truncated": False,
            "observed_code_points": len(content),
            "retained_code_points": len(content),
            "strategy": "none",
        },
        "task_refs": [],
    }


def _normalization_result() -> NormalizationResult:
    return NormalizationResult(
        provider_id="synthetic",
        adapter_id="synthetic-v1",
        source_format="fixture-v1",
        thread_ref=THREAD_REF,
        workspace=_meta()["workspace"],
        source_status=SourceStatus.STABLE,
        result_status="ready",
        capabilities={
            "reasoning": "absent",
            "tool_linkage": "explicit",
            "context": "absent",
            "task_references": "available",
            "explicit_concurrency": "unavailable",
            "timestamps": "full",
            "terminal_events": "unavailable",
        },
        counts={"diagnostics_suppressed": 0},
        lossiness=zero_lossiness(),
    )


def _rollout_source(root: Path, *, name: str = "rollout.jsonl") -> Path:
    source = root / name
    records = (
        {
            "timestamp": "2026-01-01T00:00:00Z",
            "type": "session_meta",
            "payload": {"id": "thread-v3"},
        },
        {
            "timestamp": "2026-01-01T00:00:01Z",
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": "done",
            },
        },
    )
    source.write_text(
        "\n".join(json.dumps(item, separators=(",", ":")) for item in records)
        + "\n",
        encoding="utf-8",
    )
    return source


def _write_evidence(source: Path, output: Path) -> dict[str, object]:
    return write_agent_thread_evidence(
        CodexRolloutProvider(),
        ProviderContext(home=source.parent),
        ThreadSelection(source=source),
        output,
    )


@pytest.mark.parametrize("limit_kind", ("records", "trajectory_bytes"))
def test_collector_limits_use_actual_policy_and_attempt(limit_kind: str) -> None:
    records = (_meta(), _message())
    meta_bytes = len(canonical_json_bytes(records[0], newline=True))
    message_bytes = len(canonical_json_bytes(records[1], newline=True))
    policy_limit = 1 if limit_kind == "records" else meta_bytes + 1
    collector = TrajectoryCollector(
        policy=replace(DEFAULT_NORMALIZATION_POLICY, **{limit_kind: policy_limit})
    )
    assert collector.emit(records[0])
    assert not collector.emit(records[1])
    collector.finish()

    _, lossiness, diagnostics, status = _finalize_normalization(
        _normalization_result(), collector
    )
    assert status == "partial"
    reason = "record_limit" if limit_kind == "records" else "trajectory_limit"
    assert lossiness["partial_reasons"][reason] == 1
    expected = (
        {"observed_count": 2, "limit_count": 1}
        if limit_kind == "records"
        else {"observed_bytes": meta_bytes + message_bytes, "limit_bytes": meta_bytes + 1}
    )
    assert diagnostics[-1]["details"] == expected


def test_core_limit_preserves_provider_diagnostic_cap_accounting() -> None:
    collector = TrajectoryCollector(
        policy=replace(DEFAULT_NORMALIZATION_POLICY, records=1)
    )
    assert collector.emit(_meta())
    assert not collector.emit(_message())
    collector.finish()
    result = _normalization_result()
    diagnostic_limit = DEFAULT_NORMALIZATION_POLICY.diagnostics
    regular = tuple(
        {
            "code": "message-truncated",
            "severity": "info",
            "action": "truncate",
            "count": 1,
            "record_ref": None,
            "source_ref": {
                "event_index": index,
                "line": index,
                "component_index": 0,
                "component": "message",
            },
            "details": {
                "observed_code_points": index + 2,
                "retained_code_points": 1,
            },
        }
        for index in range(diagnostic_limit - 1)
    )
    marker = {
        "code": "diagnostic-limit-reached",
        "severity": "warning",
        "action": "truncate",
        "count": 1,
        "record_ref": None,
        "source_ref": None,
        "details": {"observed_count": 300, "limit_count": diagnostic_limit},
    }
    lossiness = {group: dict(values) for group, values in result.lossiness.items()}
    lossiness["truncated"]["diagnostics"] = 45
    capped = replace(
        result,
        counts={"diagnostics_emitted": diagnostic_limit, "diagnostics_suppressed": 45},
        lossiness=lossiness,
        diagnostics=regular + (marker,),
    )

    final_counts, final_loss, diagnostics, _ = _finalize_normalization(
        capped, collector
    )

    assert len(diagnostics) == diagnostic_limit
    assert diagnostics[-1]["code"] == "diagnostic-limit-reached"
    assert diagnostics[-1]["details"] == {
        "observed_count": 301,
        "limit_count": diagnostic_limit,
    }
    assert final_counts["diagnostics_suppressed"] == 46
    assert final_loss["truncated"]["diagnostics"] == 46


def test_capture_projection_and_publication_share_one_v3_authority(
    tmp_path: Path,
) -> None:
    source = _rollout_source(tmp_path)
    provider = CodexRolloutProvider()
    selection = ThreadSelection(source=source)
    ephemeral = normalize_agent_thread_evidence(
        provider,
        ProviderContext(home=tmp_path),
        selection,
    )
    output = tmp_path / "evidence.zip"
    manifest = write_agent_thread_evidence(
        provider,
        ProviderContext(home=tmp_path),
        selection,
        output,
    )
    validated = validate_evidence(output)

    assert validated.native == source.read_bytes()
    assert validated.evidence_id == manifest["evidence_id"]
    assert ephemeral.native == validated.native
    assert [
        record["source_ref"].get("native_record_id")
        for record in validated.trajectory.records
    ] == [None, "n000001"]
    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == [
            "manifest.json",
            "native.bin",
            "native-index.jsonl",
            "trajectory.jsonl",
        ]
        assert all(
            stat.S_IMODE(info.external_attr >> 16) == 0o644
            for info in archive.infolist()
        )


def test_output_may_be_inside_repository_but_is_never_overwritten(
    tmp_path: Path,
) -> None:
    source = _rollout_source(tmp_path)
    output = tmp_path / "evidence.zip"
    _write_evidence(source, output)

    with pytest.raises(FileExistsError):
        _write_evidence(source, output)
    assert validate_evidence(output).native == source.read_bytes()


def test_output_must_differ_from_selected_source(tmp_path: Path) -> None:
    source = _rollout_source(tmp_path, name="rollout.zip")

    with pytest.raises(ValueError, match="differ from the selected source"):
        _write_evidence(source, source)

    assert source.read_bytes().startswith(b'{"timestamp"')


def test_replaced_output_parent_is_rejected_before_publication(
    tmp_path: Path,
) -> None:
    output_parent = tmp_path / "exports"
    output_parent.mkdir()
    target = _canonical_evidence_output(output_parent / "evidence.zip")

    output_parent.rename(tmp_path / "exports-original")
    output_parent.mkdir()

    with pytest.raises(ValueError, match="changed after validation"):
        _verify_output_parent(output_parent, target.parent_identity)
    assert not (output_parent / "evidence.zip").exists()


def test_link_output_parent_is_rejected(tmp_path: Path) -> None:
    physical = tmp_path / "physical"
    physical.mkdir()
    linked = tmp_path / "linked"
    try:
        linked.symlink_to(physical, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")

    with pytest.raises(ValueError, match="non-link directory"):
        _canonical_evidence_output(linked / "evidence.zip")


def test_provider_errors_publish_no_artifact(tmp_path: Path) -> None:
    source = tmp_path / "invalid.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    output = tmp_path / "evidence.zip"

    with pytest.raises(SvcError):
        _write_evidence(source, output)
    assert not output.exists()
