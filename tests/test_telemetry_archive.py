from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import stat
import tempfile
import pytest
import zipfile

from svc_cli.errors import SvcError
from svc_cli.telemetry.agent_threads import (
    NormalizationResult,
    ProviderContext,
    ResolvedThread,
    SourceStatus,
    ThreadSelection,
)
from svc_cli.telemetry.archive import (
    _canonical_repository_and_output,
    _finalize_normalization,
    _verify_output_parent,
    normalize_agent_thread,
    write_agent_thread_bundle,
)
from svc_cli.telemetry.trajectory import (
    DEFAULT_NORMALIZATION_POLICY,
    TrajectoryCollector,
    canonical_json_bytes,
    validate_bundle,
    zero_lossiness,
)


THREAD_REF = "thread_" + ("1" * 64)


class SyntheticTrajectoryProvider:
    provider_id = "synthetic"

    def __init__(self, source_status: str = "stable") -> None:
        self.source_status = source_status

    def resolve(
        self,
        context: ProviderContext,
        selection: ThreadSelection,
    ) -> ResolvedThread:
        assert selection.source is not None
        return ResolvedThread(
            provider_id=self.provider_id,
            adapter_id="synthetic-v1",
            source_format="fixture-v1",
            thread_id="native-private-thread-id",
            source_path=selection.source,
        )

    def stream_normalize(self, resolved, sink, bounds):
        records = (
            {
                "type": "meta",
                "record_id": "r000000",
                "record_index": 0,
                "timestamp": None,
                "source_ref": {
                    "event_index": None,
                    "component": "meta",
                },
                "trajectory_schema": "svc.trajectory/v1",
                "provider_id": self.provider_id,
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
            },
            {
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
                "content": "bounded private content",
                "content_meta": {
                    "truncated": False,
                    "observed_code_points": 23,
                    "retained_code_points": 23,
                    "strategy": "none",
                },
                "task_refs": [],
            },
        )
        for record in records:
            if not sink(record):
                break
        lossiness = zero_lossiness()
        result_status = "ready"
        if self.source_status != "stable":
            lossiness["partial_reasons"][
                "source_" + self.source_status
            ] = 1
            result_status = "partial"
        return NormalizationResult(
            provider_id=self.provider_id,
            adapter_id="synthetic-v1",
            source_format="fixture-v1",
            thread_ref=THREAD_REF,
            workspace=records[0]["workspace"],
            source_status=SourceStatus(self.source_status),
            result_status=result_status,
            capabilities={
                "reasoning": "absent",
                "tool_linkage": "explicit",
                "context": "absent",
                "task_references": "available",
                "explicit_concurrency": "unavailable",
                "timestamps": "full",
                "terminal_events": "unavailable",
            },
            counts={
                "source_bytes_read": 2,
                "source_events_seen": 1,
                "records_emitted": 2,
                "trajectory_bytes": 0,
                "records_by_type": {
                    "meta": 1,
                    "message": 1,
                    "reasoning": 0,
                    "tool_call": 0,
                    "tool_result": 0,
                    "context": 0,
                    "event": 0,
                },
                "messages_by_role": {"user": 1, "assistant": 0},
                "tool_calls": 0,
                "tool_results": 0,
                "task_references": 0,
                "diagnostics_emitted": 0,
                "diagnostics_suppressed": 0,
            },
            lossiness=lossiness,
            diagnostics=(),
        )


class TestNormalizedBundle:
    def export(
        self,
        root: Path,
        provider: SyntheticTrajectoryProvider | None = None,
    ) -> tuple[Path, dict[str, object]]:
        repository = root / "repo"
        output_parent = root / "exports"
        repository.mkdir()
        output_parent.mkdir()
        source = root / "source.jsonl"
        source.write_text("{}\n", encoding="utf-8")
        output = output_parent / "thread.zip"
        manifest = write_agent_thread_bundle(
            provider or SyntheticTrajectoryProvider(),
            ProviderContext(home=root),
            ThreadSelection(source=source),
            repository,
            output,
        )
        return output, manifest

    def test_bundle_has_exact_private_deterministic_members(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, manifest = self.export(Path(temporary))
            validated = validate_bundle(output)
            with zipfile.ZipFile(output) as archive:
                assert (archive.namelist()) == (["manifest.json", "trajectory.jsonl"])
                for info in archive.infolist():
                    assert (info.date_time) == ((1980, 1, 1, 0, 0, 0))
                    assert (stat.S_IMODE(info.external_attr >> 16)) == (0o600)
                    assert (info.compress_type) == (zipfile.ZIP_DEFLATED)
                payload = archive.read("manifest.json")
                trajectory = archive.read("trajectory.jsonl")

            assert (payload) == ((
                    json.dumps(
                        manifest,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode("utf-8"))
            assert (validated.bundle_id) == (manifest["bundle_id"])
            assert (validated.trajectory.trajectory_bytes) == (trajectory)
            assert (b"native-private-thread-id") not in (output.read_bytes())
            if os.name != "nt":
                assert (stat.S_IMODE(output.stat().st_mode)) == (0o600)

    def test_collector_limit_diagnostics_use_the_actual_policy_and_attempt(
        self,
    ) -> None:
        provider = SyntheticTrajectoryProvider()
        resolved = provider.resolve(
            ProviderContext(),
            ThreadSelection(source=Path("synthetic.jsonl")),
        )
        observed_records: list[dict[str, object]] = []
        provider.stream_normalize(
            resolved,
            lambda record: observed_records.append(dict(record)) or True,
            {},
        )

        record_policy = replace(
            DEFAULT_NORMALIZATION_POLICY,
            records=1,
        )
        record_collector = TrajectoryCollector(policy=record_policy)
        record_result = provider.stream_normalize(
            resolved,
            record_collector.emit,
            {},
        )
        record_collector.finish()
        _, record_loss, record_diagnostics, record_status = (
            _finalize_normalization(record_result, record_collector)
        )
        assert (record_status) == ("partial")
        assert (record_loss["partial_reasons"]["record_limit"]) == (1)
        assert (record_diagnostics[-1]["details"]) == ({"observed_count": 2, "limit_count": 1})

        meta_bytes = len(
            canonical_json_bytes(observed_records[0], newline=True)
        )
        message_bytes = len(
            canonical_json_bytes(observed_records[1], newline=True)
        )
        trajectory_policy = replace(
            DEFAULT_NORMALIZATION_POLICY,
            trajectory_bytes=meta_bytes + 1,
        )
        trajectory_collector = TrajectoryCollector(
            policy=trajectory_policy,
        )
        trajectory_result = provider.stream_normalize(
            resolved,
            trajectory_collector.emit,
            {},
        )
        trajectory_collector.finish()
        _, trajectory_loss, trajectory_diagnostics, _ = (
            _finalize_normalization(
                trajectory_result,
                trajectory_collector,
            )
        )
        assert (trajectory_loss["partial_reasons"]["trajectory_limit"]) == (1)
        assert (trajectory_diagnostics[-1]["details"]) == ({
                "observed_bytes": meta_bytes + message_bytes,
                "limit_bytes": meta_bytes + 1,
            })

    def test_core_limit_preserves_provider_diagnostic_cap_accounting(
        self,
    ) -> None:
        provider = SyntheticTrajectoryProvider()
        resolved = provider.resolve(
            ProviderContext(),
            ThreadSelection(source=Path("synthetic.jsonl")),
        )
        collector = TrajectoryCollector(
            policy=replace(
                DEFAULT_NORMALIZATION_POLICY,
                records=1,
            )
        )
        result = provider.stream_normalize(
            resolved,
            collector.emit,
            {},
        )
        collector.finish()
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
            for index in range(255)
        )
        marker = {
            "code": "diagnostic-limit-reached",
            "severity": "warning",
            "action": "truncate",
            "count": 1,
            "record_ref": None,
            "source_ref": None,
            "details": {
                "observed_count": 300,
                "limit_count": 256,
            },
        }
        lossiness = {
            group: dict(values)
            for group, values in result.lossiness.items()
        }
        lossiness["truncated"]["diagnostics"] = 45
        counts = dict(result.counts)
        counts["diagnostics_emitted"] = 256
        counts["diagnostics_suppressed"] = 45
        capped = replace(
            result,
            counts=counts,
            lossiness=lossiness,
            diagnostics=regular + (marker,),
        )

        final_counts, final_loss, diagnostics, _ = (
            _finalize_normalization(capped, collector)
        )

        assert (len(diagnostics)) == (256)
        assert (diagnostics[-1]["code"]) == ("diagnostic-limit-reached")
        assert (diagnostics[-1]["details"]) == ({"observed_count": 301, "limit_count": 256})
        assert (final_counts["diagnostics_suppressed"]) == (46)
        assert (final_loss["truncated"]["diagnostics"]) == (46)

    def test_ephemeral_normalization_matches_export_without_publication(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repo"
            output_parent = root / "exports"
            repository.mkdir()
            output_parent.mkdir()
            source = root / "source.jsonl"
            source.write_text("{}\n", encoding="utf-8")
            provider = SyntheticTrajectoryProvider()
            selection = ThreadSelection(source=source)

            ephemeral = normalize_agent_thread(
                provider,
                ProviderContext(home=root),
                selection,
            )
            output = output_parent / "thread.zip"
            manifest = write_agent_thread_bundle(
                provider,
                ProviderContext(home=root),
                selection,
                repository,
                output,
            )
            persisted = validate_bundle(output)

        assert (ephemeral.path) is None
        assert (ephemeral.bundle_id) == (manifest["bundle_id"])
        assert (ephemeral.bundle_id) == (persisted.bundle_id)
        assert (ephemeral.trajectory.trajectory_bytes) == (persisted.trajectory.trajectory_bytes)

    def test_source_race_status_is_semantic_and_partial(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, manifest = self.export(
                Path(temporary),
                SyntheticTrajectoryProvider("grew"),
            )
        assert (manifest["source"]["source_status"]) == ("grew")
        assert (manifest["result_status"]) == ("partial")
        assert (manifest["lossiness"]["partial_reasons"]["source_grew"]) == (1)

    def test_output_is_absent_outside_repository_and_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output, _ = self.export(root)
            source = root / "source.jsonl"
            with pytest.raises(FileExistsError):
                write_agent_thread_bundle(
                    SyntheticTrajectoryProvider(),
                    ProviderContext(home=root),
                    ThreadSelection(source=source),
                    root / "repo",
                    output,
                )

            inside = root / "repo" / "inside.zip"
            with pytest.raises(ValueError):
                write_agent_thread_bundle(
                    SyntheticTrajectoryProvider(),
                    ProviderContext(home=root),
                    ThreadSelection(source=source),
                    root / "repo",
                    inside,
                )
            assert not (inside.exists())

    def test_replaced_output_parent_is_rejected_before_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repo"
            repository.mkdir()
            output_parent = root / "exports"
            output_parent.mkdir()
            target = _canonical_repository_and_output(
                repository,
                output_parent / "thread.zip",
            )

            displaced_parent = root / "exports-original"
            output_parent.rename(displaced_parent)
            output_parent.mkdir()

            with pytest.raises(ValueError, match="changed after validation"):
                _verify_output_parent(
                    output_parent,
                    target.parent_identity,
                    target.repository,
                )
            assert not ((output_parent / "thread.zip").exists())

    def test_provider_errors_publish_no_artifact(self) -> None:
        class FailingProvider(SyntheticTrajectoryProvider):
            def stream_normalize(self, resolved, sink, bounds):
                raise SvcError(
                    "thread-source-incompatible",
                    "not a compatible source",
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repo"
            output_parent = root / "exports"
            repository.mkdir()
            output_parent.mkdir()
            source = root / "source.jsonl"
            source.write_text("{}\n", encoding="utf-8")
            output = output_parent / "thread.zip"
            with pytest.raises(SvcError):
                write_agent_thread_bundle(
                    FailingProvider(),
                    ProviderContext(home=root),
                    ThreadSelection(source=source),
                    repository,
                    output,
                )
            assert not (output.exists())
