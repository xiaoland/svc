"""Console interface for the packaged SVC corpus and project integration runtime."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Never, Sequence, cast

from ._execution import ExecutionStore
from .analysis.protocol import AnalysisProtocolError
from .analysis.query import query_schema
from .analysis.read import read_schema
from .analysis.service import execute_query, execute_read
from .errors import SvcError
from .dev.runtime import ensure_target, inspect_dev_identity, inspect_dev_status, stop_target
from .lookup import (
    LOOKUP_DISCOVERY_HINT,
    READ_GUIDANCE_COMMAND,
    CorpusLookup,
    LookupQuery,
)
from .project import InitPlan, apply_init, inspect_status, plan_init
from .run.runtime import (
    execute_entry,
    follow_run,
    inspect_run,
    outcome_exit_code,
    receipt,
)
from .release import catalog, runtime_version
from .upgrade import UpgradePlan, UpgradeTarget, apply_upgrade, plan_upgrade
from .telemetry.agent_threads import ArchiveFilter
from .telemetry.service import (
    export_agent_thread,
    list_agent_threads,
)


EXIT_OK = 0
EXIT_USAGE = 2
EXIT_CONFLICT = 3
EXIT_FAILURE = 4


class CliUsageError(ValueError):
    """Argument grammar error raised without argparse writing side effects."""


class SvcArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise CliUsageError(message)


def _parser() -> argparse.ArgumentParser:
    parser = SvcArgumentParser(
        prog="svc",
        description="Local Sustainable Vibe Coding corpus and project integration CLI.",
        epilog=f"For local SVC guidance: {LOOKUP_DISCOVERY_HINT}",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {runtime_version()}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    lookup = subparsers.add_parser(
        "lookup",
        help="Browse, search, or read the packaged SVC Corpus",
        description=(
            "Browse, search, or read packaged SVC Corpus guidance. Lookup does not "
            "document SVC CLI usage; use svc <command> --help for command contracts."
        ),
        epilog=(
            "--list browses one logical directory level. --keyword ranks concept "
            "candidates; --regex returns exact path/content matches. --path prints one "
            "exact document as raw Markdown. Search can validly return no matches. "
            "Default text is for Agent/Human reading; --json is compact scripts/CI output."
        ),
    )
    lookup_group = lookup.add_mutually_exclusive_group(required=True)
    lookup_group.add_argument(
        "--list",
        nargs="?",
        const="",
        dest="list_prefix",
        metavar="PREFIX",
        help="List immediate children of one logical Corpus directory",
    )
    lookup_group.add_argument(
        "--path",
        help="Read one exact normalized source-relative Markdown path from --list",
    )
    lookup_group.add_argument(
        "--keyword",
        help="Rank bounded lexical candidates in the selected scope",
    )
    lookup_group.add_argument(
        "--regex",
        help="Return bounded exact regular-expression matches",
    )
    lookup.add_argument("--scope", choices=("path", "both"))
    lookup.add_argument(
        "--limit", type=_lookup_limit, help="Maximum keyword results (1-50)"
    )
    lookup.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit compact mode-specific JSON for scripts and CI",
    )

    init = subparsers.add_parser(
        "init",
        help="Establish or repair bounded project integration (plan-first)",
        description=(
            "Plan first-time establishment or repair of bounded SVC project integration. "
            "Without --apply, inspect a non-mutating plan. With --apply, SVC recomputes "
            "the plan and applies it only when PLAN_DIGEST still selects the exact state."
        ),
        epilog=(
            "Owned effects: create a missing minimal svc.json; maintain SVC-marked blocks "
            "in .gitignore, AGENTS.md, and docs/index.md; retire a clean legacy SVC CLI "
            "Skill. Existing configuration, Corpus baseline, svc.local.json, and unmarked "
            "Consumer content are not rewritten. Use svc upgrade for config or Corpus migration."
        ),
    )
    init.add_argument("repo", nargs="?", default=".", help="Project directory")
    init.add_argument("--apply", metavar="PLAN_DIGEST")
    init.add_argument(
        "--json", action="store_true", dest="json_output", help="Emit compact scripts/CI JSON"
    )

    status = subparsers.add_parser(
        "status",
        help="Inspect CLI, config, Corpus baseline, and managed integration state",
        description=(
            "Inspect project SVC state without probing dev targets or changing files. "
            "Non-healthy results include one primary continuation and exit 3; --json "
            "emits the complete compact scripts/CI projection."
        ),
    )
    status.add_argument("repo", nargs="?", default=".", help="Project directory")
    status.add_argument(
        "--json", action="store_true", dest="json_output", help="Emit the complete compact scripts/CI projection"
    )

    upgrade = subparsers.add_parser(
        "upgrade",
        help="Plan or apply one config-schema or Corpus-baseline upgrade stage",
        description=(
            "Plan or apply one project SVC upgrade stage. Config migration and "
            "Corpus baseline adoption are independent targets; without --target, "
            "config is selected first when both are pending."
        ),
        epilog=(
            "Config apply performs only the exact supported file transform. Corpus "
            "plans reference guidance for Agent/Human document work; Corpus apply "
            "records only the reviewed baseline. This command does not update the CLI."
        ),
    )
    upgrade.add_argument("repo", nargs="?", default=".", help="Project directory")
    upgrade.add_argument("--target", choices=("config", "corpus"))
    upgrade.add_argument("--apply", metavar="PLAN_DIGEST")
    upgrade.add_argument(
        "--json", action="store_true", dest="json_output", help="Emit compact scripts/CI JSON"
    )

    dev = subparsers.add_parser(
        "dev", help="Observe, ensure, or stop declared consumer dev capabilities"
    )
    dev_commands = dev.add_subparsers(dest="dev_command", required=True)
    dev_status = dev_commands.add_parser(
        "status",
        help="Observe one or all declared dev targets without starting them",
        description=(
            "Execute the selected target readiness probes and report qualified runtime "
            "state. Consumer-owned exec probes may run code, but status never invokes a "
            "provisioner, stop action, or process takeover. Omit TARGET to inspect all."
        ),
        epilog=(
            "Resolved snapshots use stdout: exit 0 only when every selected target is "
            "ready, otherwise 3. Invalid requests and infrastructure errors use stderr. "
            "Default text is Agent/Human-oriented; --json is the compact scripts/CI projection."
        ),
    )
    dev_status.add_argument("target", nargs="?")
    dev_status.add_argument("--repo", default=".")
    dev_status.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit the complete compact scripts/CI projection",
    )
    dev_identity = dev_commands.add_parser(
        "identity",
        help="Show the resolved workspace identity used for dev coordination",
    )
    dev_identity.add_argument(
        "--repo", default=".", help="Workspace directory (default: current directory)"
    )
    dev_identity.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit compact exact identity JSON for scripts and CI",
    )
    dev_ensure = dev_commands.add_parser(
        "ensure",
        help="Reuse, join, or start exactly one declared dev target",
        description=(
            "Make one declared target ready. Ensure may execute its Consumer-owned "
            "provisioner, waits for declared readiness, refuses an unhealthy responder, "
            "and leaves a ready long-running capability running after this CLI exits."
        ),
        epilog=(
            "Live start/join facts use stderr and the terminal capability result uses "
            "stdout. Exit 0 means ready, 3 means a resolved non-ready boundary, 4 means "
            "execution infrastructure failure, and caller Ctrl+C returns 130."
        ),
    )
    dev_ensure.add_argument("target")
    dev_ensure.add_argument(
        "--repo", default=".", help="Workspace directory (default: current directory)"
    )
    dev_ensure.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit one compact terminal scripts/CI result and suppress live progress",
    )
    dev_stop = dev_commands.add_parser(
        "stop",
        help="Run the declared bounded stop action for exactly one dev target",
        description=(
            "Stop exactly one declared dev target through its target-local stop action. "
            "SVC never infers cleanup from a recorded PID. The final readiness probe "
            "qualifies the result; native action output remains in the reported log."
        ),
        epilog=(
            "Live owner/join facts use stderr and the terminal stop result uses stdout. "
            "Exit 0 means the action succeeded and readiness is false; expected manual, "
            "failed, still-ready, or unverified results exit 3; infrastructure failure "
            "is 4; caller Ctrl+C is 130."
        ),
    )
    dev_stop.add_argument("target")
    dev_stop.add_argument(
        "--repo", default=".", help="Workspace directory (default: current directory)"
    )
    dev_stop.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit one compact terminal scripts/CI result and suppress live progress",
    )
    run = subparsers.add_parser(
        "run",
        help="Execute, follow, or inspect one declared bounded run",
        description=(
            "Execute one named bounded project command, replay and wait for one exact "
            "execution with --follow, or observe it without replay/wait using --inspect. "
            "Same active entry intent converges; a later explicit entry invocation reruns."
        ),
        epilog=(
            "Default execute/follow preserves native stdout/stderr and writes SVC lifecycle "
            "text to stderr. Inspect text uses stdout. --json suppresses native/live output "
            "and emits one compact receipt. Execution IDs and logs are workspace-local. "
            "Owner Ctrl+C interrupts its run; follower Ctrl+C only detaches that caller. "
            "Child exits pass through, while successful inspect exits 0."
        ),
    )
    run.add_argument("entry", nargs="?")
    run_selection = run.add_mutually_exclusive_group()
    run_selection.add_argument(
        "--follow", metavar="EXECUTION_ID", help="Replay native output and wait"
    )
    run_selection.add_argument(
        "--inspect", metavar="EXECUTION_ID", help="Observe facts without replay or wait"
    )
    run.add_argument(
        "--repo", default=".", help="Workspace directory (default: current directory)"
    )
    run.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit one compact receipt and suppress native/live display",
    )

    telemetry = subparsers.add_parser(
        "telemetry", help="Collect explicit local observability evidence"
    )
    telemetry_resources = telemetry.add_subparsers(
        dest="telemetry_resource", required=True
    )
    agent_thread = telemetry_resources.add_parser(
        "agent-thread", help="List or capture provider-obtainable Agent-thread evidence"
    )
    agent_thread_commands = agent_thread.add_subparsers(
        dest="agent_thread_command", required=True
    )
    thread_list = agent_thread_commands.add_parser(
        "list", help="List bounded Codex thread selection context"
    )
    thread_list.add_argument("--codex-home", type=Path)
    thread_list.add_argument(
        "--archive-state",
        choices=tuple(state.value for state in ArchiveFilter),
        default=ArchiveFilter.ALL.value,
        help="Filter by provider-reported lifecycle (default: all)",
    )
    thread_list.add_argument(
        "--limit",
        type=_telemetry_limit,
        default=20,
        help="Maximum threads to list (1-100)",
    )
    thread_list.add_argument("--json", action="store_true", dest="json_output")
    thread_export = agent_thread_commands.add_parser(
        "export",
        help="Capture one exact local thread into a schema-v3 evidence ZIP",
    )
    selector = thread_export.add_mutually_exclusive_group(required=True)
    selector.add_argument("--thread-id")
    selector.add_argument(
        "--source", type=Path, help="Exact Codex rollout JSONL source"
    )
    thread_export.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Absent .zip destination distinct from the source",
    )
    thread_export.add_argument("--codex-home", type=Path)
    thread_export.add_argument("--json", action="store_true", dest="json_output")

    analysis = subparsers.add_parser(
        "analysis",
        help="Query or read immutable Agent-thread evidence; read the packaged Agent Task Analysis method first",
    )
    analysis_tools = analysis.add_subparsers(dest="analysis_tool", required=True)
    for name, help_text in (
        ("query", "Inspect boundaries or match deterministic navigation predicates"),
        ("read", "Read ordered native evidence from start, exact ref, or cursor"),
    ):
        tool = analysis_tools.add_parser(name, help=help_text)
        tool.add_argument(
            "--schema",
            action="store_true",
            help="Return the tool contract and Agent method reference",
        )
        tool.add_argument("--input", type=Path, help="Exact schema-v3 evidence ZIP")
        tool.add_argument("--request", help="JSON request file or - for stdin")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    try:
        args = parser.parse_args(raw_argv)
        if args.command == "run":
            selected = sum(
                value is not None for value in (args.entry, args.follow, args.inspect)
            )
            if selected != 1:
                raise CliUsageError(
                    "svc run requires exactly one entry, --follow ID, or --inspect ID"
                )
    except CliUsageError as error:
        if raw_argv[:1] == ["analysis"] or "--json" in raw_argv:
            _emit_json(
                {
                    "code": "invalid-cli-usage",
                    "message": str(error),
                },
                stream=sys.stderr,
            )
        else:
            print(f"svc: invalid-cli-usage: {error}", file=sys.stderr)
            if not raw_argv or raw_argv[:1] == ["lookup"]:
                print(f"Hint: {LOOKUP_DISCOVERY_HINT}", file=sys.stderr)
        return EXIT_USAGE
    json_output = bool(getattr(args, "json_output", False))
    try:
        if args.command == "lookup":
            if args.limit is not None and (
                args.list_prefix is not None or args.path is not None
            ):
                raise SvcError(
                    "invalid-lookup-options",
                    "--limit does not apply to --list or --path.",
                )
            if args.scope is not None and args.keyword is None and args.regex is None:
                raise SvcError(
                    "invalid-lookup-options",
                    "--scope applies only to --keyword or --regex.",
                )
            lookup_limit = args.limit if args.limit is not None else 10
            scope = args.scope or "both"
            if args.list_prefix is not None:
                query = LookupQuery("list", args.list_prefix, limit=lookup_limit)
            elif args.path is not None:
                query = LookupQuery("path", args.path, limit=lookup_limit)
            elif args.keyword is not None:
                query = LookupQuery("keyword", args.keyword, scope, lookup_limit)
            else:
                query = LookupQuery("regex", args.regex, scope, lookup_limit)
            response = CorpusLookup(catalog()).lookup(query)
            _emit_lookup(response, json_output)
            return EXIT_OK

        if args.command == "status":
            payload = inspect_status(Path(args.repo))
            _emit_status(payload, json_output)
            return EXIT_OK if payload["healthy"] else EXIT_CONFLICT

        if args.command == "upgrade":
            target = cast(UpgradeTarget | None, args.target)
            upgrade_plan = plan_upgrade(Path(args.repo), target)
            if args.apply:
                payload = apply_upgrade(upgrade_plan, args.apply)
                _emit_upgrade_apply(payload, json_output)
                return EXIT_OK
            _emit_upgrade_plan(upgrade_plan, json_output)
            return (
                EXIT_CONFLICT
                if upgrade_plan.status in {"migration-required", "blocked"}
                else EXIT_OK
            )

        if args.command == "dev":
            if args.dev_command == "identity":
                payload = inspect_dev_identity(Path(args.repo))
                _emit_dev_identity(payload, json_output)
                return EXIT_OK
            if args.dev_command == "status":
                payload = inspect_dev_status(Path(args.repo), args.target)
                _emit_dev_status(payload, json_output)
                return EXIT_OK if payload["healthy"] else EXIT_CONFLICT
            if args.dev_command == "stop":
                payload = stop_target(
                    Path(args.repo),
                    args.target,
                    on_selected=None if json_output else _emit_dev_stop_selected,
                )
                _emit_dev_stop(payload, json_output)
                return _dev_stop_exit_code(payload)
            try:
                payload = ensure_target(
                    Path(args.repo),
                    args.target,
                    on_selected=None if json_output else _emit_dev_ensure_selected,
                )
            except SvcError as error:
                if not _is_expected_ensure_outcome(error):
                    raise
                payload = dict(error.details)
            _emit_dev_ensure(payload, json_output)
            return _dev_ensure_exit_code(payload)

        if args.command == "run":
            return _run_declared(args, json_output)

        if args.command == "analysis":
            return _run_analysis_tool(args)

        if args.command == "telemetry":
            if (
                args.telemetry_resource == "agent-thread"
                and args.agent_thread_command == "list"
            ):
                payload = list_agent_threads(
                    args.codex_home, args.limit, args.archive_state
                )
                _emit_telemetry_list(payload, json_output)
                return EXIT_OK
            payload = export_agent_thread(
                codex_home=args.codex_home,
                thread_id=args.thread_id,
                source=args.source,
                output=args.output,
            )
            _emit_telemetry_export(payload, json_output)
            return EXIT_OK

        local_plan = plan_init(Path(args.repo))
        if args.apply:
            payload = apply_init(local_plan, args.apply)
            _emit_init_apply(payload, json_output)
            return EXIT_OK
        _emit_init_plan(local_plan, json_output)
        return EXIT_CONFLICT if local_plan.blockers else EXIT_OK
    except SvcError as error:
        _emit_error(error, json_output)
        return _exit_code(error)
    except AnalysisProtocolError as error:
        _emit_json(error.as_dict(), stream=sys.stderr)
        return _analysis_exit_code(error)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        _emit_error(SvcError("invalid-release", str(error)), json_output)
        return EXIT_FAILURE


def _analysis_request(source: str) -> object:
    if source == "-":
        text = sys.stdin.read(1_048_577)
    else:
        try:
            with Path(source).open("r", encoding="utf-8") as stream:
                text = stream.read(1_048_577)
        except (OSError, UnicodeDecodeError) as error:
            raise AnalysisProtocolError(
                "analysis-request-unreadable",
                "Analysis request could not be read as UTF-8 JSON.",
                {"path": source, "reason": str(error)},
            ) from error
    if len(text.encode("utf-8")) > 1_048_576:
        raise AnalysisProtocolError(
            "analysis-request-too-large",
            "Analysis request exceeds its byte bound.",
        )

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in items:
            if key in value:
                raise ValueError(f"duplicate JSON key: {key}")
            value[key] = item
        return value

    try:
        return json.loads(
            text,
            object_pairs_hook=pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite number: {token}")
            ),
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise AnalysisProtocolError(
            "invalid-analysis-request-json",
            "Analysis request is not strict JSON.",
            {"reason": str(error)},
        ) from error


def _run_declared(args: argparse.Namespace, json_output: bool) -> int:
    callback = None if json_output else _emit_run_selected
    stdout_sink = None if json_output else _binary_output(sys.stdout)
    stderr_sink = None if json_output else _binary_output(sys.stderr)
    if args.follow is not None:
        command = "run follow"
        outcome = follow_run(
            Path(args.repo),
            args.follow,
            stdout_sink=stdout_sink,
            stderr_sink=stderr_sink,
            on_selected=callback,
        )
    elif args.inspect is not None:
        command = "run inspect"
        outcome = inspect_run(Path(args.repo), args.inspect)
    else:
        command = "run"
        outcome = execute_entry(
            Path(args.repo),
            args.entry,
            stdout_sink=stdout_sink,
            stderr_sink=stderr_sink,
            on_selected=callback,
        )
    payload = receipt(outcome, command)
    if json_output:
        _emit_json(payload)
    else:
        _emit_run_terminal(outcome, inspect=args.inspect is not None)
    return outcome_exit_code(outcome, inspect=args.inspect is not None)


def _emit_run_selected(record: Any, role: str) -> None:
    store = ExecutionStore()
    print(f"svc run {record.subject}: {role} {record.execution_id}", file=sys.stderr)
    print(f"cwd: {record.cwd}", file=sys.stderr)
    print(f"$ {_display_argv(record.argv)}", file=sys.stderr)
    print(
        "logs: "
        f"stdout {store.log_path(record, 'stdout')}; "
        f"stderr {store.log_path(record, 'stderr')}",
        file=sys.stderr,
    )


def _emit_dev_stop(payload: dict[str, object], json_output: bool) -> None:
    if json_output:
        _emit_json(payload)
        return
    workspace = cast(dict[str, object], payload["workspace"])
    capability = cast(dict[str, object], payload["capability"])
    print(
        f"svc dev {payload['target']}: {payload['status']}; "
        f"instance {workspace['instance']}; scope {capability['scope']}"
    )
    attempt = payload.get("attempt")
    if isinstance(attempt, dict):
        print(f"$ {_display_argv(cast(Sequence[str], attempt['argv']))}")
        role = attempt["caller_role"]
        state = attempt["state"]
        detail = (
            f", exit {attempt['exit_code']}" if "exit_code" in attempt else ""
        )
        print(f"Execution: {attempt['execution_id']} ({role}), {state}{detail}")
        logs = cast(dict[str, dict[str, object]], attempt["logs"])
        if "merged" in logs:
            print(f"Stop log: {logs['merged']['path']}")
            if payload["status"] == "stop-failed" and logs["merged"]["bytes"]:
                tail = _file_tail(Path(str(logs["merged"]["path"])))
                if tail:
                    print("Stop output (tail):")
                    for line in tail.splitlines():
                        print(f"  {line}")
    probe = payload.get("probe")
    if isinstance(probe, dict):
        disposition = "ready" if probe["healthy"] else "not ready"
        print(f"Final probe: {probe['kind']} {probe['reason']} — {disposition}")
    elif "probe_error" in payload:
        error = cast(dict[str, object], payload["probe_error"])
        print(f"Final probe: unverified — {error['code']}: {error['message']}")


def _emit_dev_identity(payload: dict[str, object], json_output: bool) -> None:
    if json_output:
        _emit_json(payload)
        return
    workspace = cast(dict[str, object], payload["workspace"])
    print("svc dev identity")
    print(f"instance: {workspace['instance']}")
    print(f"root: {workspace['root']}")
    print(
        f"repository: {workspace['repository_kind']} {workspace['repository_id']}"
    )
    print(f"worktree: {workspace['worktree_id']}")
    print(f"namespace: {workspace['namespace_id']}")


def _emit_dev_ensure(payload: dict[str, object], json_output: bool) -> None:
    if json_output:
        _emit_json(payload)
        return
    workspace = cast(dict[str, object], payload["workspace"])
    capability = cast(dict[str, object], payload["capability"])
    if payload.get("caller_status") == "detached":
        attempt = cast(dict[str, object], payload["attempt"])
        logs = cast(dict[str, dict[str, object]], attempt["logs"])
        print(
            f"svc dev {payload['target']}: detached from start "
            f"{attempt['execution_id']}; scope {capability['scope']}"
        )
        print(f"Execution state: {attempt['state']}")
        print(f"Startup log: {logs['merged']['path']}")
        return
    ready = payload.get("ready") is True
    lead = "ready" if ready else str(payload["status"])
    outcome = f" ({payload['status']})" if ready else ""
    print(
        f"svc dev {payload['target']}: {lead}{outcome}; "
        f"instance {workspace['instance']}; scope {capability['scope']}"
    )
    probe = cast(dict[str, object], payload["probe"])
    print(f"Probe: {probe['kind']} {_probe_text_detail(probe)}")
    if not ready and "probe_argv" in payload:
        print(f"$ {_display_argv(cast(Sequence[str], payload['probe_argv']))}")
    access = cast(list[str], payload.get("access", []))
    if access:
        for value in access:
            print(f"Access: {value}")
    else:
        output = probe.get("output")
        if isinstance(output, str) and output:
            preview, omitted = _text_preview(output)
            print("Probe output:")
            for line in preview.splitlines() or [preview]:
                print(f"  {line}")
            if omitted or probe.get("output_truncated"):
                print("  … output truncated; use --json for the bounded capture")
        elif not ready and probe["kind"] == "exec":
            print("Probe output: empty")
    attempt_value = payload.get("attempt")
    if isinstance(attempt_value, dict):
        logs = cast(dict[str, dict[str, object]], attempt_value["logs"])
        print(
            f"Execution: {attempt_value['execution_id']} "
            f"({attempt_value['caller_role']}), {attempt_value['state']}"
        )
        print(f"Startup log: {logs['merged']['path']}")
    if payload["status"] == "manual-action-required":
        print(
            "No SVC command can provision this target; follow the Consumer "
            "project's guidance."
        )


def _emit_dev_ensure_selected(
    record: Any, caller_role: str, log_path: str
) -> None:
    if caller_role == "owner":
        print(
            f"svc dev {record.subject}: starting `{_display_argv(record.argv)}`",
            file=sys.stderr,
        )
    else:
        print(
            f"svc dev {record.subject}: joining existing start {record.execution_id}",
            file=sys.stderr,
        )
    print(f"Waiting for readiness; startup log: {log_path}", file=sys.stderr)


def _emit_dev_stop_selected(record: Any, caller_role: str, log_path: str) -> None:
    if caller_role == "owner":
        print(
            f"svc dev {record.subject}: stopping `{_display_argv(record.argv)}`",
            file=sys.stderr,
        )
    else:
        print(
            f"svc dev {record.subject}: joining stop {record.execution_id}",
            file=sys.stderr,
        )
    print(f"Waiting for stop; log: {log_path}", file=sys.stderr)


def _is_expected_ensure_outcome(error: SvcError) -> bool:
    return error.code in {
        "manual-action-required",
        "occupied-unhealthy",
        "readiness-timeout",
        "provision-exited",
        "activation-timeout",
        "activation-failed",
        "dev-owner-lost",
        "ensure-interrupted",
    } and error.details.get("command") == "dev ensure"


def _dev_ensure_exit_code(payload: dict[str, object]) -> int:
    if payload.get("status") == "interrupted" or payload.get("caller_status") == "detached":
        return 130
    return EXIT_OK if payload.get("ready") is True else EXIT_CONFLICT


def _emit_dev_status(payload: dict[str, object], json_output: bool) -> None:
    if json_output:
        _emit_json(payload)
        return
    workspace = cast(dict[str, object], payload["workspace"])
    status = str(payload["status"])
    if status in {"invalid-configuration", "not-configured"}:
        print(f"svc dev status: {status}; instance {workspace['instance']}")
        if "reason" in payload:
            print(f"Reason: {payload['reason']}")
        if status == "not-configured":
            print("No dev targets are declared in svc.json.")
        return
    targets = cast(list[dict[str, object]], payload["targets"])
    ready_count = sum(
        1
        for entry in targets
        if isinstance(entry.get("probe"), dict)
        and cast(dict[str, object], entry["probe"])["healthy"]
    )
    print(
        f"svc dev status: {status} — {ready_count}/{len(targets)} ready; "
        f"instance {workspace['instance']}"
    )
    ensure_targets: list[str] = []
    for entry in targets:
        if "error" in entry:
            error = cast(dict[str, object], entry["error"])
            print(f"error      {entry['target']}  {error['code']}: {error['message']}")
            continue
        probe = cast(dict[str, object], entry["probe"])
        capability = cast(dict[str, object], entry["capability"])
        disposition = "ready" if probe["healthy"] else "not-ready"
        detail = _probe_text_detail(probe)
        continuation = entry.get("continuation")
        suffix = f"; {continuation}" if continuation is not None else ""
        print(
            f"{disposition:<10} {entry['target']}  {capability['scope']}  "
            f"{probe['kind']} {detail}{suffix}"
        )
        if not probe["healthy"] and "probe_argv" in entry:
            print(
                f"  $ {_display_argv(cast(Sequence[str], entry['probe_argv']))}"
            )
        access = cast(list[str], entry["access"])
        for value in access:
            print(f"  Access: {value}")
        output = probe.get("output")
        if isinstance(output, str) and output:
            preview, omitted = _text_preview(output)
            print("  Probe output:")
            for line in preview.splitlines() or [preview]:
                print(f"    {line}")
            if omitted or probe.get("output_truncated"):
                print("    … output truncated; use --json for the bounded capture")
        elif probe["kind"] == "exec" and not probe["healthy"]:
            print("  Probe output: empty")
        if continuation == "ensure":
            ensure_targets.append(str(entry["target"]))
    if ensure_targets:
        selected = ensure_targets[0] if len(ensure_targets) == 1 else "<target>"
        print(
            "Ensure one: "
            f"svc dev ensure {shlex.quote(selected)} --repo "
            f"{shlex.quote(str(workspace['root']))}"
        )


def _probe_text_detail(probe: dict[str, object]) -> str:
    if probe["kind"] == "exec" and "exit_code" in probe:
        return f"exit {probe['exit_code']}"
    if probe["kind"] == "http" and "status_code" in probe:
        return f"status {probe['status_code']}"
    return str(probe["reason"])


def _text_preview(value: str, limit: int = 1_200) -> tuple[str, bool]:
    if len(value) <= limit:
        return value.rstrip("\n"), False
    return value[:limit].rstrip("\n"), True


def _file_tail(path: Path, limit: int = 1_200) -> str | None:
    try:
        with path.open("rb") as stream:
            size = stream.seek(0, os.SEEK_END)
            stream.seek(max(0, size - limit))
            value = stream.read(limit)
    except OSError:
        return None
    return value.decode("utf-8", errors="replace").rstrip("\n") or None


def _dev_stop_exit_code(payload: dict[str, object]) -> int:
    if payload.get("caller_status") in {"interrupted", "detached"}:
        return 130
    return EXIT_OK if payload.get("status") == "stopped" else EXIT_CONFLICT


def _emit_run_terminal(outcome: Any, *, inspect: bool) -> None:
    stream = sys.stdout if inspect else sys.stderr
    if outcome.detached:
        suffix = f" {outcome.record.execution_id}" if outcome.record is not None else ""
        print(f"svc run {outcome.entry}: detached{suffix}", file=stream)
        if outcome.record is not None and outcome.store is not None:
            _emit_run_logs(outcome.store, outcome.record, stream=stream)
        return
    record = outcome.record
    if record is None:
        return
    duration = (
        f" in {record.duration_ms / 1000:.1f}s"
        if record.duration_ms is not None
        else ""
    )
    prefix = (
        f"svc run inspect: {record.subject} —"
        if inspect
        else f"svc run {record.subject}:"
    )
    detail = f" {record.exit_code}" if record.state == "exited" else ""
    print(
        f"{prefix} {record.state}{detail}{duration} ({outcome.caller_role})",
        file=stream,
    )
    print(f"execution: {record.execution_id}", file=stream)
    if inspect:
        print(f"$ {_display_argv(record.argv)}", file=stream)
        print(f"cwd: {record.cwd}", file=stream)
    if outcome.store is not None:
        _emit_run_logs(outcome.store, record, stream=stream)
    if record.failure_reason:
        print(f"reason: {record.failure_reason}", file=stream)


def _emit_run_logs(store: Any, record: Any, *, stream: Any) -> None:
    stdout = store.log_reference(record, "stdout")
    stderr = store.log_reference(record, "stderr")
    print(
        "logs: "
        f"stdout {stdout.path} ({stdout.bytes:,} bytes); "
        f"stderr {stderr.path} ({stderr.bytes:,} bytes)",
        file=stream,
    )


def _display_argv(argv: Sequence[str]) -> str:
    return (
        subprocess.list2cmdline(list(argv))
        if os.name == "nt"
        else shlex.join(list(argv))
    )


class _TextBinaryAdapter:
    def __init__(self, stream: Any) -> None:
        self.stream = stream

    def write(self, data: bytes) -> int:
        text = data.decode("utf-8", errors="replace")
        self.stream.write(text)
        return len(data)

    def flush(self) -> None:
        self.stream.flush()


def _binary_output(stream: Any) -> Any:
    return getattr(stream, "buffer", None) or _TextBinaryAdapter(stream)


def _run_analysis_tool(args: argparse.Namespace) -> int:
    if args.schema:
        if args.input is not None or args.request is not None:
            raise AnalysisProtocolError(
                "invalid-cli-usage",
                "--schema cannot be combined with --input or --request.",
            )
        payload = query_schema() if args.analysis_tool == "query" else read_schema()
        _emit_json(payload)
        return EXIT_OK
    if args.input is None or args.request is None:
        raise AnalysisProtocolError(
            "invalid-cli-usage",
            "Analysis execution requires --input and --request.",
        )
    request = _analysis_request(args.request)
    if args.analysis_tool == "query":
        payload = execute_query(args.input, request)
    else:
        payload = execute_read(args.input, request)
    _emit_json(payload)
    return EXIT_OK


def _lookup_limit(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("--limit must be an integer") from error
    if not 1 <= limit <= 50:
        raise argparse.ArgumentTypeError("--limit must be between 1 and 50")
    return limit


def _telemetry_limit(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("--limit must be an integer") from error
    if not 1 <= limit <= 100:
        raise argparse.ArgumentTypeError("--limit must be between 1 and 100")
    return limit


def _emit_upgrade_plan(plan: UpgradePlan, json_output: bool) -> None:
    if json_output:
        _emit_json(plan.as_dict())
        return
    print(f"svc upgrade: {plan.status}")
    print(f"Repository: {plan.repo}")
    if plan.target is None:
        configuration = cast(dict[str, object], plan.details["configuration"])
        corpus_state = cast(dict[str, object], plan.details["corpus"])
        print(f"Configuration: schema {configuration['schema']} (current)")
        print(f"Corpus: baseline {corpus_state['project_version']} (current)")
        print("Project SVC upgrade state is current.")
        return

    _emit_upgrade_target_heading(plan)
    if plan.status == "blocked":
        print("No changes can be applied.")
        _emit_blockers(plan.blockers)
        _emit_upgrade_remaining(plan.remaining_targets, label="Other target")
        print("Next: resolve the blocker, then recompute this target:")
        print(f"  svc upgrade {shlex.quote(str(plan.repo))} --target {plan.target}")
        return

    if plan.target == "config":
        print("\nAutomatic config changes:")
        for change in plan.automatic_changes:
            print(f"  {change}")
        for guide in plan.config_guides:
            print(
                f"\nProject migration guidance ({guide.identifier}, sha256:{guide.sha256}):"
            )
            for line in guide.text.splitlines():
                print(f"  {line}" if line else "")
    else:
        corpus_details = cast(dict[str, object], plan.details["corpus"])
        releases = cast(list[dict[str, object]], corpus_details["releases"])
        print(f"\nCorpus releases ({len(releases)}):")
        paths: list[str] = []
        for release in releases:
            migration = str(release["migration"])
            label = (
                "guidance required"
                if migration == "guide"
                else "migration not required"
            )
            print(f"  {release['version']}  {label}")
            for guide_ref in cast(list[dict[str, str]], release.get("guides", [])):
                paths.append(guide_ref["path"])
                print(f"    {guide_ref['path']}")
        if paths:
            print("\nRead required guidance:")
            for path in paths:
                print(f"  svc lookup --path {shlex.quote(path)}")
            print(
                "\nSVC will only record the reviewed Corpus baseline; it will not "
                "modify project-owned SVC documents."
            )

    print(f"\nWould change ({len(plan.mutations)}):")
    for operation in plan.mutations:
        print(f"  {operation.action} {operation.path} - {operation.reason}")
    _emit_upgrade_remaining(plan.remaining_targets, label="Reminder")
    assert plan.digest is not None
    if plan.status == "migration-required":
        print("\nAfter completing the migration guidance, apply this exact plan:")
    else:
        print("\nApply this exact plan:")
    print(
        f"  svc upgrade {shlex.quote(str(plan.repo))} --target {plan.target} "
        f"--apply {plan.digest}"
    )


def _emit_upgrade_apply(payload: dict[str, object], json_output: bool) -> None:
    if json_output:
        _emit_json(payload)
        return
    print("svc upgrade: applied")
    print(f"Repository: {payload['repo']}")
    target = str(payload["target"])
    if target == "config":
        details = cast(dict[str, object], payload["configuration"])
        print(
            f"Target: config (schema {details['from_schema']} -> {details['to_schema']})"
        )
    else:
        details = cast(dict[str, object], payload["corpus"])
        print(
            f"Target: corpus (baseline {details['from_version']} -> {details['to_version']})"
        )
    print(f"Applied plan: {payload['plan_digest']}")
    migration = cast(dict[str, object], payload["migration"])
    if migration["disposition"] == "caller-asserted":
        print(
            "Migration guidance: asserted complete by caller; project-owned work not verified by SVC"
        )
    else:
        print("Migration guidance: not required")
    operations = cast(list[dict[str, object]], payload["operations"])
    print(f"\nChanged ({len(operations)}):")
    for operation in operations:
        print(f"  {operation['action']} {operation['path']}")
    verification = cast(dict[str, object], payload["verification"])
    print(f"\nVerification: {verification['scope']} {verification['status']}")
    remaining = cast(list[dict[str, object]], payload["remaining_targets"])
    if remaining:
        _emit_upgrade_remaining(tuple(remaining), label="Reminder")
        print("Next upgrade:")
        print(f"  svc upgrade {shlex.quote(str(payload['repo']))}")
    else:
        print("\nRemaining upgrade targets: none")
        print("Next observation:")
        print(f"  svc status {shlex.quote(str(payload['repo']))}")


def _emit_upgrade_target_heading(plan: UpgradePlan) -> None:
    if plan.target == "config" and "configuration" in plan.details:
        details = cast(dict[str, object], plan.details["configuration"])
        if "from_schema" in details:
            print(
                f"Target: config (schema {details['from_schema']} -> {details['to_schema']})"
            )
            return
    if plan.target == "corpus" and "corpus" in plan.details:
        details = cast(dict[str, object], plan.details["corpus"])
        if "from_version" in details:
            print(
                f"Target: corpus (baseline {details['from_version']} -> {details['to_version']})"
            )
            return
    print(f"Target: {plan.target}")


def _emit_upgrade_remaining(
    remaining: Sequence[dict[str, object]], *, label: str
) -> None:
    for fact in remaining:
        target = str(fact["target"])
        if target == "corpus":
            transition = f"{fact['from_version']} -> {fact['to_version']}"
        else:
            transition = f"schema {fact['from_schema']} -> {fact['to_schema']}"
        print(f"\n{label}: {target} upgrade {fact['status']} ({transition})")


def _emit_init_plan(plan: InitPlan, json_output: bool) -> None:
    if json_output:
        _emit_json(plan.as_dict())
        return
    suffix = "; no changes can be applied" if plan.status == "blocked" else ""
    print(f"svc init: {plan.status}{suffix}")
    print(f"Repository: {plan.repo}")
    print(
        "Intent: "
        + (
            "establish project integration"
            if plan.intent == "establish"
            else "repair managed integration"
        )
    )
    print(f"Corpus: {plan.corpus_version}")
    baseline = plan.corpus_baseline
    if baseline["disposition"] == "create":
        print(f"Corpus baseline: create {baseline['version']}")
    else:
        print(f"Corpus baseline: {baseline['version'] or 'unavailable'} (unchanged)")
    if plan.status == "blocked":
        print()
        _emit_blockers(plan.blockers)
        print("Next: resolve the blocker, then recompute the plan:")
        print(f"  svc init {shlex.quote(str(plan.repo))}")
        return
    if plan.status == "noop":
        print("Managed integration is current; no changes.")
        return
    print(f"\nWould change ({len(plan.mutations)}):")
    for mutation in plan.mutations:
        surface, extent, reason = _init_operation_text(mutation.path)
        print(f"  {mutation.action:7} {mutation.path} ({extent}) - {reason}")
    assert plan.digest is not None
    print("\nApply exact plan:")
    print(f"  svc init {shlex.quote(str(plan.repo))} --apply {plan.digest}")


def _emit_init_apply(payload: dict[str, object], json_output: bool) -> None:
    if json_output:
        _emit_json(payload)
        return
    print(f"svc init: {payload['status']}")
    print(f"Repository: {payload['repo']}")
    print(f"Corpus: {payload['corpus_version']}")
    baseline = cast(dict[str, object], payload["corpus_baseline"])
    if baseline["disposition"] == "create":
        print(f"Corpus baseline: created {baseline['version']}")
    else:
        print(f"Corpus baseline: {baseline['version'] or 'unavailable'} (unchanged)")
    print(f"Applied plan: {payload['plan_digest']}")
    operations = cast(list[dict[str, object]], payload["operations"])
    if operations:
        print(f"\nChanged ({len(operations)}):")
        past = {
            "create": "created",
            "append": "appended",
            "refresh": "refreshed",
            "delete": "deleted",
        }
        for operation in operations:
            _, extent, _ = _init_operation_text(str(operation["path"]))
            print(
                f"  {past[str(operation['action'])]:9} {operation['path']} ({extent})"
            )
    else:
        print("Changed: none; no managed operation required a write")
    print("\nVerification: all planned path postconditions passed")
    print("Next observation:")
    print(f"  svc status {shlex.quote(str(payload['repo']))}")


def _init_operation_text(path: str) -> tuple[str, str, str]:
    values = {
        "svc.json": ("project-state", "whole file", "establish minimal project state"),
        ".gitignore": (
            "local-config-ignore",
            "SVC local-config ignore block",
            "maintain local overlay privacy",
        ),
        "AGENTS.md": ("agent-router", "SVC navigation block", "update Agent router"),
        "docs/index.md": (
            "docs-navigation",
            "SVC navigation block",
            "update documentation navigation",
        ),
        ".agents/skills/svc/SKILL.md": (
            "legacy-cli-skill",
            "clean generated file",
            "retire CLI Skill",
        ),
    }
    return values[path]


def _emit_status(payload: dict[str, Any], json_output: bool) -> None:
    if json_output:
        _emit_json(payload)
        return
    installed = payload["installed_cli_version"] or "source-tree"
    corpus_state = payload["corpus"]
    configuration = payload["configuration"]
    project_version = corpus_state["project_version"] or "absent"
    lead = "healthy" if payload["healthy"] else str(payload["status"])
    print(
        f"SVC {lead} — CLI {installed} ({payload['resource_mode']}); "
        f"Corpus {corpus_state['available_version']}; project baseline {project_version} "
        f"({corpus_state['status']}); configuration {configuration['status']}"
    )
    next_action = payload["next"]
    if not payload["healthy"]:
        print(f"Next: {next_action['action']} — {next_action['reason']}")
        command = next_action.get("command")
        if isinstance(command, list):
            print("  " + shlex.join([str(part) for part in command]))
    message = payload["project"].get("message") or configuration.get("message")
    if message:
        print(f"Configuration: {message}")
    integration = payload["integration"]
    anomalies = integration["anomalies"]
    if anomalies:
        print(
            f"Integration: {integration['status']} ({len(anomalies)} anomalous surface(s))"
        )
        for item in anomalies:
            print(f"  {item['status']:16} {item['path']} ({item['kind']})")
    workspace = payload["workspace"]
    print(
        f"Workspace: {workspace['root']} ({workspace['repository_kind']}; "
        f"worktree {workspace['worktree_id']}; instance {workspace['instance']})"
    )
    dev_targets = payload["dev"]["targets"]
    if dev_targets:
        print("Dev: " + ", ".join(dev_targets))
    run_entries = payload["run"]["entries"]
    if run_entries:
        print("Run: " + ", ".join(run_entries))


def _emit_telemetry_list(payload: dict[str, Any], json_output: bool) -> None:
    if json_output:
        _emit_json(payload)
        return
    threads = payload["threads"]
    print(f"SVC telemetry agent-thread list: {len(threads)} thread(s)")
    for descriptor in threads:
        if not isinstance(descriptor, dict):
            continue
        updated = descriptor.get("updated_at") or "unknown-time"
        print(
            f"  {descriptor.get('thread_id')}  {descriptor.get('archive_state')}  {updated}"
        )


def _emit_telemetry_export(payload: dict[str, Any], json_output: bool) -> None:
    if json_output:
        _emit_json(payload)
        return
    evidence = payload["evidence"]
    if isinstance(evidence, dict):
        print(f"SVC telemetry agent-thread export: exported {evidence.get('path')}")
    else:
        print("SVC telemetry agent-thread export: exported")


def _emit_lookup(response: Any, json_output: bool) -> None:
    if json_output:
        _emit_json(response.as_dict())
        return
    if response.query.mode == "path":
        content = response.document.content
        print(content, end="" if content.endswith("\n") else "\n")
        return
    if response.query.mode == "list":
        for entry in response.entries:
            if entry.kind == "directory":
                print(f"{entry.path:<40} {entry.document_count} documents")
            else:
                print(f"{entry.path:<40} {entry.title}")
        print("\nExpand: svc lookup --list <directory>")
        print("Read:   svc lookup --path <document>")
        return
    if response.query.mode == "keyword":
        if not response.candidates:
            print(f"No SVC Corpus matches for: {response.query.value}")
            return
        for candidate in response.candidates:
            print(f"{candidate.entry.path:<40} {candidate.entry.title}")
            if candidate.excerpt is not None:
                print(f"  {candidate.excerpt}")
            else:
                print("  [path match]")
    else:
        if not response.matches:
            print(f"No SVC Corpus matches for: {response.query.value}")
            return
        for match in response.matches:
            if match.surface == "path":
                print(f"[path] {match.entry.path}")
            else:
                print(
                    f"{match.entry.path}:{match.line}:{match.column}: {match.excerpt}"
                )
    if response.truncated:
        print(f"Results truncated at --limit {response.query.limit}.")
    print("\nRead one: svc lookup --path <path>")


def _emit_blockers(blockers: Sequence[Any]) -> None:
    if not blockers:
        return
    print("Blockers:")
    for blocker in blockers:
        path = getattr(blocker, "path", None)
        location = f" {path}:" if path else ""
        print(f"  {blocker.code}:{location} {blocker.message}")


def _emit_error(error: SvcError, json_output: bool) -> None:
    if json_output:
        _emit_json(error.as_dict(), stream=sys.stderr)
        return
    print(f"svc: {error.code}: {error.message}", file=sys.stderr)
    details = dict(error.details)
    hint = details.pop("hint", None)
    labels = {
        "reason": "Reason",
        "path": "Path",
        "repo": "Repository",
        "target": "Target",
        "entry": "Entry",
        "expected": "Expected",
        "actual": "Actual",
        "execution_id": "Execution",
    }
    rendered: set[str] = set()
    for key, label in labels.items():
        value = details.get(key)
        if isinstance(value, (str, int, float, bool)):
            print(f"{label}: {value}", file=sys.stderr)
            rendered.add(key)
    for key, label in (
        ("available_entries", "Available entries"),
        ("available_targets", "Available targets"),
    ):
        value = details.get(key)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            print(f"{label}: {', '.join(value) if value else 'none'}", file=sys.stderr)
            rendered.add(key)
    rollback = details.get("rollback")
    if isinstance(rollback, dict) and isinstance(rollback.get("status"), str):
        print(f"Rollback: {rollback['status']}", file=sys.stderr)
        rendered.add("rollback")
    if set(details) - rendered:
        print("Structured details: rerun with --json.", file=sys.stderr)
    if isinstance(hint, str):
        print(f"Hint: {hint}", file=sys.stderr)


def _emit_json(payload: dict[str, object], stream: Any | None = None) -> None:
    output = stream or sys.stdout
    json.dump(
        payload, output, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    output.write("\n")


def _exit_code(error: SvcError) -> int:
    if error.code in {
        "invalid-document-path",
        "invalid-directory-prefix",
        "invalid-lookup-options",
        "invalid-lookup-regex",
    }:
        return EXIT_USAGE
    if error.code == "apply-interrupted":
        rollback = error.details.get("rollback")
        if isinstance(rollback, dict) and rollback.get("status") == "failed":
            return EXIT_FAILURE
        return 130
    if error.code in {
        "apply-failed",
        "execution-capture-failed",
        "execution-coordination-invalid",
        "execution-coordination-mismatch",
        "execution-launch-failed",
        "execution-log-unreadable",
        "execution-record-invalid",
        "execution-state-invalid",
        "execution-state-unreadable",
        "invalid-corpus",
        "invalid-execution-coordination",
        "invalid-release",
        "postcondition-failed",
        "staging-failed",
        "output-write-failed",
        "execution-storage-failed",
    }:
        return EXIT_FAILURE
    return EXIT_CONFLICT


def _analysis_exit_code(error: AnalysisProtocolError) -> int:
    if error.code in {
        "invalid-cli-usage",
        "invalid-analysis-request-json",
        "invalid-query-request",
        "invalid-read-request",
        "analysis-request-too-large",
    }:
        return EXIT_USAGE
    if error.code in {
        "cursor-scope-mismatch",
        "invalid-cursor",
        "invalid-reference",
        "reference-kind-mismatch",
        "reference-not-found",
        "reference-scope-mismatch",
        "query-page-budget-too-small",
    }:
        return EXIT_CONFLICT
    return EXIT_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
