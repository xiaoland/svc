from __future__ import annotations

import json
from pathlib import Path
import tempfile
import pytest

from svc_cli.telemetry.agent_threads import ProviderContext, ThreadSelection
from svc_cli.telemetry.providers.codex_rollout import CodexRolloutProvider


class TestCodexTrajectory:
    def write_source(self, root: Path, *records: dict[str, object]) -> Path:
        source = root / "rollout.jsonl"
        source.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")
        return source

    def normalize(
        self,
        root: Path,
        *records: dict[str, object],
    ) -> tuple[object, list[dict[str, object]]]:
        source = self.write_source(root, *records)
        provider = CodexRolloutProvider()
        resolved = provider.resolve(ProviderContext(home=root), ThreadSelection(source=source))
        projected: list[dict[str, object]] = []
        result = provider.stream_normalize(
            resolved,
            lambda record: projected.append(dict(record)) or True,
            {},
        )
        return result, projected

    @staticmethod
    def envelope(kind: str, payload: object, timestamp: str = "2026-01-01T00:00:00Z") -> dict[str, object]:
        return {"timestamp": timestamp, "type": kind, "payload": payload}

    def test_stream_emits_stable_source_refs_and_canonical_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.write_source(
                root,
                self.envelope("session_meta", {"id": "thread-1", "cwd": "/work/project"}),
                self.envelope("response_item", {"type": "message", "role": "user", "content": "user input"}),
                self.envelope("response_item", {"type": "function_call", "name": "svc", "call_id": "native-call", "arguments": {"cmd": "status"}}),
                self.envelope("response_item", {"type": "function_call_output", "call_id": "native-call", "status": "success", "output": "private output"}),
            )
            provider = CodexRolloutProvider()
            resolved = provider.resolve(ProviderContext(home=root), ThreadSelection(source=source))
            records: list[dict[str, object]] = []
            result = provider.stream_normalize(resolved, lambda record: records.append(dict(record)) or True, {})

            assert (result.source_status.value) == ("stable")
            assert (result.result_status.value) == ("ready")
            assert ([record["type"] for record in records]) == (["meta", "message", "tool_call", "tool_result"])
            assert ([record["record_index"] for record in records]) == ([0, 1, 2, 3])
            assert ([record["record_id"] for record in records]) == (["r000000", "r000001", "r000002", "r000003"])
            assert (records[1]["source_ref"]["event_index"]) == (1)
            assert (records[1]["source_ref"]["line"]) == (1)
            assert (records[3]["source_ref"]["event_index"]) == (3)
            assert (records[3]["content"]) == ("private output")

    def test_stream_preserves_orphan_result_order_and_deterministic_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.write_source(
                root,
                self.envelope("session_meta", {"id": "thread-2"}),
                self.envelope("response_item", {"type": "function_call_output", "call_id": "late", "status": "error", "output": "x"}),
                self.envelope("response_item", {"type": "function_call", "name": "tool", "call_id": "late", "arguments": ""}),
            )
            provider = CodexRolloutProvider()
            resolved = provider.resolve(ProviderContext(home=root), ThreadSelection(source=source))
            first: list[dict[str, object]] = []
            second: list[dict[str, object]] = []
            provider.stream_normalize(resolved, lambda record: first.append(dict(record)) or True, {})
            provider.stream_normalize(resolved, lambda record: second.append(dict(record)) or True, {})

            assert (first) == (second)
            assert (first[1]["type"]) == ("tool_result")
            assert (first[1]["link_status"]) == ("unresolved")
            assert (first[2]["type"]) == ("tool_call")
            assert (first[1]["tool_call_id"]) == (first[2]["tool_call_id"])

    def test_codex_relations_context_roles_and_ui_loss_are_classified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            passthrough = {"turn_id": "turn-native", "author": "author-native", "recipient": "recipient-native"}
            context_payloads = [
                {"type": "message", "role": "developer", "content": "developer context"},
                {"type": "message", "role": "system", "content": "system context"},
                {"type": "turn_context", "effort": "high", "approval_policy": "on-request", "sandbox_policy": "workspace"},
            ]
            context_events = [
                self.envelope("response_item", {**payload, "internal_chat_message_metadata_passthrough": passthrough})
                for payload in context_payloads
            ]
            ui_events = [
                self.envelope("event_msg", {"type": kind, "text": "ui"})
                for kind in ("user_message", "agent_message", "agent_reasoning")
            ]
            result, records = self.normalize(
                root,
                self.envelope("session_meta", {"id": "thread-shapes"}),
                *context_events,
                self.envelope("response_item", {"type": "message", "role": "user", "content": "user input", "internal_chat_message_metadata_passthrough": passthrough}),
                *ui_events,
                self.envelope("event_msg", {"type": "token_count", "count": 4}),
                self.envelope("event_msg", {"type": "task_started"}),
                self.envelope("event_msg", {"type": "task_complete", "status": "completed"}),
                self.envelope("event_msg", {"type": "context_compacted"}),
            )

            assert result.lossiness["dropped"]["unsupported_record"] == 0
            assert result.lossiness["dropped"]["ui_event"] == 3
            assert result.lossiness["dropped"]["rate_limit_noise"] == 1
            assert result.capabilities["context"] == "partial"
            assert result.capabilities["terminal_events"] == "available"
            assert result.counts["messages_by_role"] == {"user": 1, "assistant": 0}
            contexts = [record for record in records if record["type"] == "context"]
            assert [record["context_kind"] for record in contexts] == ["developer", "system", "turn"]
            assert contexts[-1]["attributes"] == {"reasoning_effort": "high", "approval_mode": "on-request", "sandbox_mode": "workspace"}
            user = next(record for record in records if record["type"] == "message")
            assert user["turn_ref"].startswith("turn_")
            assert user["actor_ref"].startswith("actor_")
            assert user["lane_ref"].startswith("lane_")
            events = [record for record in records if record["type"] == "event"]
            assert [record["event_kind"] for record in events] == ["turn_start", "turn_complete", "compaction"]

    def test_tool_call_shapes_pair_with_results_and_completion_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            relation = {"turn_id": "turn-tool", "author": "agent-tool", "recipient": "recipient-tool"}
            call_shapes = [
                self.envelope(
                    "response_item",
                    {
                        "type": "custom_tool_call",
                        "call_id": "custom-1",
                        "name": "exec",
                        "arguments": {"cmd": "true"},
                        "internal_chat_message_metadata_passthrough": relation,
                    },
                ),
                self.envelope(
                    "response_item",
                    {"type": "tool_search_call", "call_id": "search-1", "arguments": {"query": "svc"}},
                ),
                self.envelope(
                    "response_item",
                    {"type": "web_search_call", "id": "web-1", "status": "in_progress"},
                ),
            ]
            result_shapes = [
                self.envelope("response_item", {"type": "custom_tool_call_output", "call_id": "custom-1", "output": "done"}),
                self.envelope("response_item", {"type": "tool_search_call_output", "call_id": "search-1", "output": "found", "status": "success"}),
                self.envelope("response_item", {"type": "web_search_call", "id": "web-1", "status": "completed", "output": "web"}),
            ]
            result, records = self.normalize(
                root,
                self.envelope("session_meta", {"id": "thread-tool-shapes"}),
                call_shapes[0],
                self.envelope("event_msg", {"type": "exec_command_end", "call_id": "custom-1", "status": "completed", "internal_chat_message_metadata_passthrough": relation}),
                result_shapes[0],
                call_shapes[1],
                result_shapes[1],
                call_shapes[2],
                result_shapes[2],
                self.envelope("event_msg", {"type": "patch_apply_end", "call_id": "patch-1", "status": "completed"}),
                self.envelope("event_msg", {"type": "mcp_tool_call_end", "call_id": "mcp-1", "status": "success"}),
                self.envelope("event_msg", {"type": "collab_completion", "call_id": "collab-1", "status": "completed"}),
            )

            calls = [record for record in records if record["type"] == "tool_call"]
            results = [record for record in records if record["type"] == "tool_result"]
            assert len(calls) == 3
            assert len(results) == 3
            assert [record["status"] for record in results] == ["success", "success", "success"]
            assert all(record["link_status"] == "linked" for record in results)
            assert all("turn_ref" in record and "actor_ref" in record and "lane_ref" in record for record in results[:1])
            assert result.lossiness["dropped"]["unsupported_record"] == 0

    def test_current_settings_completion_and_tool_search_shapes_are_projected_safely(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_sentinel = "PRIVATE-CONTEXT-SENTINEL"
            initial_context = {
                "type": "turn_context",
                "turn_id": "turn-current",
                "model": "model-current",
                "effort": "high",
                "approval_policy": "on-request",
                "sandbox_policy": {"type": "workspace-write", "writable_roots": [private_sentinel]},
                "collaboration_mode": {"mode": "multi-agent", "settings": {"private": private_sentinel}},
            }
            applied_settings = {
                "type": "thread_settings_applied",
                "thread_settings": {
                    "model": "model-next",
                    "reasoning_effort": "medium",
                    "approval_policy": "never",
                    "permission_profile": {"type": "read-only", "private": private_sentinel},
                    "collaboration_mode": {"mode": "single-agent", "settings": {"private": private_sentinel}},
                },
            }
            result, records = self.normalize(
                root,
                self.envelope("session_meta", {"id": "thread-current-shapes"}),
                self.envelope("turn_context", initial_context),
                self.envelope("event_msg", applied_settings),
                self.envelope("response_item", {"type": "tool_search_call", "call_id": "search-current", "arguments": {"query": "safe"}}),
                self.envelope("event_msg", {"type": "web_search_end", "call_id": "search-current", "action": {"type": "search"}}),
                self.envelope("response_item", {"type": "tool_search_output", "call_id": "search-current", "status": "completed", "execution": {"b": 2, "a": 1}, "tools": [{"private": private_sentinel}]}),
                self.envelope("event_msg", {"type": "thread_rolled_back", "num_turns": 1}),
                self.envelope("event_msg", {"type": "collab_agent_spawn_end", "call_id": "spawn-current", "status": "completed"}),
                self.envelope("event_msg", {"type": "collab_waiting_end", "call_id": "wait-current", "statuses": {}}),
                self.envelope("event_msg", {"type": "collab_agent_interaction_end", "call_id": "interaction-current", "status": {"completed": "agent"}}),
            )

            contexts = [
                record for record in records if record["type"] == "context"
            ]
            assert [record["attributes"] for record in contexts] == [
                {"model": "model-current", "reasoning_effort": "high", "approval_mode": "on-request", "sandbox_mode": "workspace-write", "collaboration_mode": "multi-agent"},
                {"model": "model-next", "reasoning_effort": "medium", "approval_mode": "never", "sandbox_mode": "read-only", "collaboration_mode": "single-agent"},
            ]
            tool_result = next(
                record
                for record in records
                if record["type"] == "tool_result"
            )
            assert tool_result["content"] == '{"a":1,"b":2}'
            assert tool_result["status"] == "success"
            assert tool_result["link_status"] == "linked"
            assert result.lossiness["dropped"]["unsupported_record"] == 0
            assert result.result_status.value == "ready"
            assert private_sentinel not in json.dumps(records, ensure_ascii=False)

    def test_plaintext_reasoning_summary_remains_authority_when_full_reasoning_is_opaque(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.write_source(
                root,
                self.envelope(
                    "session_meta",
                    {"id": "thread-reasoning-summary"},
                ),
                self.envelope(
                    "response_item",
                    {
                        "type": "reasoning",
                        "summary": "bounded summary",
                        "encrypted_content": "opaque",
                    },
                ),
                self.envelope(
                    "response_item",
                    {
                        "type": "reasoning",
                        "encrypted_content": "opaque",
                    },
                ),
            )
            provider = CodexRolloutProvider()
            resolved = provider.resolve(
                ProviderContext(home=root),
                ThreadSelection(source=source),
            )
            records: list[dict[str, object]] = []

            result = provider.stream_normalize(
                resolved,
                lambda record: records.append(dict(record)) or True,
                {},
            )

            reasoning = [
                record
                for record in records
                if record["type"] == "reasoning"
            ]
            assert (len(reasoning)) == (1)
            assert (reasoning[0]["content"]) == ("bounded summary")
            assert (result.capabilities["reasoning"]) == ("summary")
            assert (result.lossiness["unavailable"]["reasoning"]) == (2)
            assert (sum(
                    diagnostic["count"]
                    for diagnostic in result.diagnostics
                    if diagnostic["code"] == "reasoning-unavailable"
                )) == (2)

    def test_opaque_reasoning_emits_no_fabricated_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.write_source(
                root,
                self.envelope(
                    "session_meta",
                    {"id": "thread-reasoning-opaque"},
                ),
                self.envelope(
                    "response_item",
                    {
                        "type": "reasoning",
                        "encrypted_content": "opaque",
                    },
                ),
            )
            provider = CodexRolloutProvider()
            resolved = provider.resolve(
                ProviderContext(home=root),
                ThreadSelection(source=source),
            )
            records: list[dict[str, object]] = []

            result = provider.stream_normalize(
                resolved,
                lambda record: records.append(dict(record)) or True,
                {},
            )

            assert ("reasoning") not in ([record["type"] for record in records])
            assert (result.capabilities["reasoning"]) == ("opaque")
            assert (result.lossiness["unavailable"]["reasoning"]) == (1)

    def test_stream_sink_rejection_emits_record_limit_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.write_source(
                root,
                self.envelope("session_meta", {"id": "thread-3"}),
                self.envelope("response_item", {"type": "message", "role": "user", "content": "one"}),
                self.envelope("response_item", {"type": "message", "role": "assistant", "content": "two"}),
            )
            provider = CodexRolloutProvider()
            resolved = provider.resolve(ProviderContext(home=root), ThreadSelection(source=source))
            records: list[dict[str, object]] = []
            def sink(record: dict[str, object]) -> bool:
                records.append(dict(record))
                return len(records) < 2

            result = provider.stream_normalize(resolved, sink, {"records": 2})

            assert (len(records)) == (2)
            assert (result.result_status.value) == ("partial")
            assert (result.lossiness["partial_reasons"]["record_limit"]) > (0)
            assert ([
                    {
                        "code": diagnostic["code"],
                        "details": diagnostic["details"],
                    }
                    for diagnostic in result.diagnostics
                    if diagnostic["code"] == "record-limit-reached"
                ]) == ([
                    {
                        "code": "record-limit-reached",
                        "details": {
                            "observed_count": 2,
                            "limit_count": 2,
                        },
                    }
                ])

    def test_append_after_open_is_not_collected_and_is_reported_as_grew(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.write_source(
                root,
                self.envelope("session_meta", {"id": "thread-append"}),
            )
            provider = CodexRolloutProvider()
            resolved = provider.resolve(ProviderContext(home=root), ThreadSelection(source=source))
            records: list[dict[str, object]] = []

            def sink(record: dict[str, object]) -> bool:
                records.append(dict(record))
                if record["type"] == "meta":
                    with source.open("a", encoding="utf-8") as stream:
                        stream.write(
                            json.dumps(
                                self.envelope(
                                    "response_item",
                                    {
                                        "type": "message",
                                        "role": "assistant",
                                        "content": "appended",
                                    },
                                )
                            )
                            + "\n"
                        )
                return True

            result = provider.stream_normalize(resolved, sink, {})

            assert ([record["type"] for record in records]) == (["meta"])
            assert (result.source_status.value) == ("grew")
            assert (result.result_status.value) == ("partial")
            assert (result.lossiness["partial_reasons"]["source_grew"]) == (1)

    def test_tool_linkage_modes_suppress_duplicates_and_preserve_parent_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result, records = self.normalize(
                root,
                self.envelope("session_meta", {"id": "thread-tools"}),
                self.envelope("response_item", {"type": "function_call", "name": "synthetic"}),
                self.envelope("response_item", {"type": "function_call", "name": "explicit", "call_id": "call-1", "parent_actor_id": "parent-1"}),
                self.envelope("response_item", {"type": "function_call_output", "call_id": "call-1", "status": "success", "output": "first"}),
                self.envelope("response_item", {"type": "function_call_output", "call_id": "call-1", "status": "error", "output": "duplicate"}),
            )

            assert result.capabilities["tool_linkage"] == "mixed"
            assert [record["type"] for record in records].count("tool_result") == 1
            assert result.lossiness["dropped"]["duplicate_tool_result"] == 1
            assert result.result_status.value == "partial"
            explicit_call = next(
                record
                for record in records
                if record["type"] == "tool_call" and record["name"] == "explicit"
            )
            assert str(explicit_call["parent_actor_ref"]).startswith("actor_")

    def test_task_references_scan_full_message_and_enforce_global_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hidden_ref = "tasks/hidden/packet.md"
            source = self.write_source(
                root,
                self.envelope("session_meta", {"id": "thread-task-refs"}),
                self.envelope(
                    "response_item",
                    {
                        "type": "message",
                        "role": "user",
                        "content": (
                            ("x" * 17_000)
                            + " "
                            + hidden_ref
                            + " tasks/omitted/packet.md"
                        ),
                    },
                ),
            )
            provider = CodexRolloutProvider()
            resolved = provider.resolve(ProviderContext(home=root), ThreadSelection(source=source))
            records: list[dict[str, object]] = []
            result = provider.stream_normalize(
                resolved,
                lambda record: records.append(dict(record)) or True,
                {"task_reference_occurrences": 1},
            )

            message = next(record for record in records if record["type"] == "message")
            assert (message["task_refs"]) == ([hidden_ref])
            assert (message["content_meta"]["truncated"])
            assert (result.lossiness["truncated"]["task_references"]) == (1)

    @pytest.mark.parametrize(
        ("candidate", "expected_refs", "loss_key"),
        [
            pytest.param("tasks/good/packet.md", ["tasks/good/packet.md"], None, id="relative"),
            pytest.param("/private/tasks/absolute/packet.md", [], "absolute_task_reference", id="absolute-posix"),
            pytest.param(r"C:\private\tasks\drive\packet.md", [], "absolute_task_reference", id="absolute-windows"),
            pytest.param(r"\\server\share\tasks\unc\packet.md", [], "absolute_task_reference", id="absolute-unc"),
            pytest.param("https://example.invalid/tasks/uri/packet.md", [], "invalid_task_reference", id="uri"),
            pytest.param(r"tasks\backslash\packet.md", [], "invalid_task_reference", id="backslash"),
            pytest.param("tasks/../invalid/packet.md", [], "invalid_task_reference", id="dot-segment"),
            pytest.param("tasks/" + ("x" * 1_010) + "/packet.md", [], "oversize_task_reference", id="oversize"),
        ],
    )
    def test_task_reference_roots_uri_invalid_and_oversize_are_classified(
        self,
        candidate: str,
        expected_refs: list[str],
        loss_key: str | None,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result, records = self.normalize(
                root,
                self.envelope(
                    "session_meta",
                    {"id": "thread-task-ref-class"},
                ),
                self.envelope(
                    "response_item",
                    {
                        "type": "message",
                        "role": "user",
                        "content": candidate,
                    },
                ),
            )

            message = next(record for record in records if record["type"] == "message")
            assert message["task_refs"] == expected_refs
            task_loss_keys = (
                "absolute_task_reference",
                "invalid_task_reference",
                "oversize_task_reference",
            )
            for key in task_loss_keys:
                assert result.lossiness["dropped"][key] == (1 if key == loss_key else 0)
