from __future__ import annotations

import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Mapping

import pytest

from svc_cli.telemetry.agent_threads import ProviderContext, ThreadSelection
from svc_cli.telemetry.archive import write_agent_thread_evidence
from svc_cli.telemetry.evidence import ValidatedEvidence, validate_evidence
from svc_cli.telemetry.providers import CodexRolloutProvider


@dataclass(frozen=True)
class TrajectoryCase:
    root: Path
    provider: CodexRolloutProvider

    @staticmethod
    def envelope(
        kind: str,
        payload: object,
        timestamp: str = "2026-01-01T00:00:00Z",
    ) -> dict[str, object]:
        return {"timestamp": timestamp, "type": kind, "payload": payload}

    def source(
        self,
        *events: dict[str, object] | str,
        name: str = "rollout.jsonl",
    ) -> Path:
        path = self.root / name
        lines = [
            event
            if isinstance(event, str)
            else json.dumps(event, ensure_ascii=False, separators=(",", ":"))
            for event in events
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def export(self, source: Path) -> ValidatedEvidence:
        output = self.root / f"{source.stem}.zip"
        write_agent_thread_evidence(
            self.provider,
            ProviderContext(home=self.root),
            ThreadSelection(source=source),
            output,
        )
        return validate_evidence(output)

    def project(
        self,
        source: Path,
        bounds: Mapping[str, int] | None = None,
    ):
        resolved = self.provider.resolve(
            ProviderContext(home=self.root),
            ThreadSelection(source=source),
        )
        native = BytesIO()
        capture = self.provider.capture_native(resolved, native, bounds or {})
        records: list[dict[str, Any]] = []
        result = self.provider.stream_normalize_captured(
            resolved,
            native,
            capture,
            lambda record: records.append(dict(record)) or True,
            bounds or {},
        )
        return result, records


@pytest.fixture
def trajectory_case(tmp_path: Path) -> TrajectoryCase:
    return TrajectoryCase(tmp_path, CodexRolloutProvider())


def session(thread_id: str, **payload: object) -> dict[str, object]:
    return TrajectoryCase.envelope("session_meta", {"id": thread_id, **payload})


def response(kind: str, **payload: object) -> dict[str, object]:
    return TrajectoryCase.envelope("response_item", {"type": kind, **payload})


def event(kind: str, **payload: object) -> dict[str, object]:
    return TrajectoryCase.envelope("event_msg", {"type": kind, **payload})


class TestCodexTrajectoryProjection:
    def test_manifest_observes_messages_tools_relations_events_and_known_loss(
        self,
        trajectory_case: TrajectoryCase,
    ) -> None:
        relation = {
            "turn_id": "turn-native",
            "author": "agent-native",
            "recipient": "lane-native",
        }
        source = trajectory_case.source(
            session("thread-flow", cwd="/work/project"),
            response(
                "message",
                role="developer",
                content="developer context",
                internal_chat_message_metadata_passthrough=relation,
            ),
            response(
                "message",
                role="user",
                content="inspect tasks/flow/packet.md",
                internal_chat_message_metadata_passthrough=relation,
            ),
            response("message", role="assistant", content="working"),
            response(
                "function_call",
                name="svc",
                call_id="call-native",
                arguments={"cmd": "status tasks/tool-is-not-eligible/packet.md"},
                parent_actor_id="parent-native",
                internal_chat_message_metadata_passthrough=relation,
            ),
            event(
                "exec_command_end",
                call_id="call-native",
                status="completed",
                internal_chat_message_metadata_passthrough=relation,
            ),
            response(
                "function_call_output",
                call_id="call-native",
                output="done",
            ),
            event("task_started"),
            event("task_complete", status="completed"),
            event("context_compacted"),
            event("user_message", text="duplicate UI"),
            event("token_count", count=4),
            name="flow.jsonl",
        )

        evidence = trajectory_case.export(source)
        records = list(evidence.trajectory.records)
        projection = evidence.manifest["projection"]

        assert [record["type"] for record in records] == [
            "meta",
            "context",
            "message",
            "message",
            "tool_call",
            "tool_result",
            "event",
            "event",
            "event",
        ]
        assert [record["record_index"] for record in records] == list(range(9))
        assert [record["record_id"] for record in records] == [
            f"r{index:06d}" for index in range(9)
        ]
        assert records[0]["workspace"]["label"] == "project"

        user = records[2]
        call = records[4]
        result = records[5]
        assert user["task_refs"] == ["tasks/flow/packet.md"]
        assert (
            user["turn_ref"],
            user["actor_ref"],
            user["lane_ref"],
        ) == (
            call["turn_ref"],
            call["actor_ref"],
            call["lane_ref"],
        )
        assert str(call["parent_actor_ref"]).startswith("actor_")
        assert result["tool_call_id"] == call["tool_call_id"]
        assert result["status"] == "success"
        assert result["link_status"] == "linked"
        assert (
            result["turn_ref"],
            result["actor_ref"],
            result["lane_ref"],
        ) == (
            call["turn_ref"],
            call["actor_ref"],
            call["lane_ref"],
        )
        assert [record["source_ref"]["native_record_id"] for record in records[1:]] == [
            "n000001",
            "n000002",
            "n000003",
            "n000004",
            "n000006",
            "n000007",
            "n000008",
            "n000009",
        ]
        assert [
            record["event_kind"] for record in records if record["type"] == "event"
        ] == ["turn_start", "turn_complete", "compaction"]
        assert projection["counts"]["messages_by_role"] == {
            "user": 1,
            "assistant": 1,
        }
        assert projection["counts"]["task_references"] == 1
        assert projection["lossiness"]["dropped"]["ui_event"] == 2
        assert projection["lossiness"]["dropped"]["rate_limit_noise"] == 1
        assert projection["capabilities"]["context"] == "partial"
        assert projection["capabilities"]["terminal_events"] == "available"

    def test_manifest_observes_tool_shapes_linkage_and_duplicate_loss(
        self,
        trajectory_case: TrajectoryCase,
    ) -> None:
        relation = {
            "turn_id": "turn-tool",
            "author": "agent-tool",
            "recipient": "lane-tool",
        }
        source = trajectory_case.source(
            session("thread-tools"),
            response(
                "custom_tool_call",
                call_id="custom-1",
                name="exec",
                arguments={"cmd": "true"},
                internal_chat_message_metadata_passthrough=relation,
            ),
            event(
                "exec_command_end",
                call_id="custom-1",
                status="completed",
                internal_chat_message_metadata_passthrough=relation,
            ),
            response("custom_tool_call_output", call_id="custom-1", output="done"),
            response(
                "tool_search_call",
                call_id="search-1",
                arguments={"query": "svc"},
            ),
            response(
                "tool_search_output",
                call_id="search-1",
                status="completed",
                execution={"b": 2, "a": 1},
            ),
            response("web_search_call", id="web-1", status="in_progress"),
            response(
                "web_search_call",
                id="web-1",
                status="completed",
                output="web",
            ),
            response("function_call", name="synthetic"),
            response(
                "function_call",
                name="explicit",
                call_id="explicit-1",
                parent_actor_id="parent-1",
            ),
            response(
                "function_call_output",
                call_id="explicit-1",
                status="success",
                output="first",
            ),
            response(
                "function_call_output",
                call_id="explicit-1",
                status="error",
                output="duplicate",
            ),
            response(
                "function_call_output",
                call_id="late",
                status="error",
                output="orphan",
            ),
            response(
                "function_call",
                name="late-tool",
                call_id="late",
                arguments="",
            ),
            name="tools.jsonl",
        )

        evidence = trajectory_case.export(source)
        records = list(evidence.trajectory.records)
        projection = evidence.manifest["projection"]
        calls = [record for record in records if record["type"] == "tool_call"]
        results = [record for record in records if record["type"] == "tool_result"]

        assert [record["name"] for record in calls] == [
            "exec",
            "tool_search",
            "web_search",
            "synthetic",
            "explicit",
            "late-tool",
        ]
        assert len(results) == 5
        assert results[0]["status"] == "success"
        assert all(key in results[0] for key in ("turn_ref", "actor_ref", "lane_ref"))
        assert results[1]["content"] == '{"a":1,"b":2}'
        assert results[1]["status"] == "success"
        assert results[-1]["link_status"] == "unresolved"
        assert results[-1]["tool_call_id"] == calls[-1]["tool_call_id"]
        explicit = next(record for record in calls if record["name"] == "explicit")
        assert str(explicit["parent_actor_ref"]).startswith("actor_")
        assert projection["capabilities"]["tool_linkage"] == "mixed"
        assert projection["result_status"] == "partial"
        assert projection["lossiness"]["dropped"]["duplicate_tool_result"] == 1

    def test_manifest_observes_reasoning_authority_and_invalid_native_loss(
        self,
        trajectory_case: TrajectoryCase,
    ) -> None:
        source = trajectory_case.source(
            session("thread-reasoning"),
            response(
                "reasoning",
                summary="bounded summary",
                encrypted_content="opaque",
            ),
            response("reasoning", encrypted_content="opaque"),
            "{not-json}",
            name="reasoning.jsonl",
        )

        evidence = trajectory_case.export(source)
        records = list(evidence.trajectory.records)
        projection = evidence.manifest["projection"]
        reasoning = [record for record in records if record["type"] == "reasoning"]

        assert len(reasoning) == 1
        assert reasoning[0]["reasoning_kind"] == "summary"
        assert reasoning[0]["content"] == "bounded summary"
        assert projection["capabilities"]["reasoning"] == "summary"
        assert projection["lossiness"]["unavailable"]["reasoning"] == 2
        assert projection["lossiness"]["dropped"]["invalid_json"] == 1
        assert projection["result_status"] == "partial"
        assert (
            sum(
                diagnostic["count"]
                for diagnostic in projection["diagnostics"]
                if diagnostic["code"] == "reasoning-unavailable"
            )
            == 2
        )

    def test_task_reference_scan_uses_full_message_and_reports_all_bounds(
        self,
        trajectory_case: TrajectoryCase,
    ) -> None:
        retained = "tasks/hidden/packet.md"
        omitted = "tasks/omitted/packet.md"
        oversize = "tasks/" + ("x" * 1_010) + "/packet.md"
        content = " ".join(
            [
                "x" * 17_000,
                retained,
                omitted,
                "/private/tasks/absolute/packet.md",
                r"C:\private\tasks\drive\packet.md",
                r"\\server\share\tasks\unc\packet.md",
                "https://example.invalid/tasks/uri/packet.md",
                r"tasks\backslash\packet.md",
                "tasks/../invalid/packet.md",
                oversize,
            ]
        )
        source = trajectory_case.source(
            session("thread-task-refs"),
            response("message", role="user", content=content),
            name="task-refs.jsonl",
        )

        result, records = trajectory_case.project(
            source,
            {"task_reference_occurrences": 1},
        )
        message = next(record for record in records if record["type"] == "message")

        assert message["task_refs"] == [retained]
        assert message["content_meta"]["truncated"]
        assert result.counts["task_references"] == 1
        assert result.lossiness["truncated"]["message"] == 1
        assert result.lossiness["truncated"]["task_references"] == 1
        assert result.lossiness["dropped"]["absolute_task_reference"] == 3
        assert result.lossiness["dropped"]["invalid_task_reference"] == 3
        assert result.lossiness["dropped"]["oversize_task_reference"] == 1
        assert {item["code"] for item in result.diagnostics} >= {
            "task-reference-limit-reached",
            "absolute-task-reference-dropped",
            "invalid-task-reference-dropped",
            "task-reference-oversize-dropped",
            "message-truncated",
        }
