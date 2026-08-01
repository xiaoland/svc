"""Console interface for the packaged SVC corpus and project integration runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Never, Sequence, cast

from .analysis.protocol import AnalysisProtocolError
from .analysis.query import query_schema
from .analysis.read import read_schema
from .analysis.service import execute_query, execute_read
from .errors import SvcError
from .dev.runtime import ensure_target, inspect_dev_identity, inspect_dev_status
from .dev.setup import plan_setup
from .lookup import CorpusLookup, LookupQuery
from .project import inspect_status, plan_adopt, plan_init
from .release import catalog, runtime_version
from .telemetry.agent_threads import ArchiveFilter
from .telemetry.service import (
    export_agent_thread,
    list_agent_threads,
)
from .update import apply_self_update, plan_self_update
from .plans import LocalPlan, apply_local_plan


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
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {runtime_version()}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    lookup = subparsers.add_parser("lookup", help="Read packaged SVC guidance by path regex or keyword")
    lookup_group = lookup.add_mutually_exclusive_group(required=True)
    lookup_group.add_argument("--name", help="Full-path regular expression over packaged SVC document paths")
    lookup_group.add_argument("--keyword", help="Deterministic local keyword query")
    lookup.add_argument("--all", action="store_true", dest="allow_many", help="Allow all --name matches")
    lookup.add_argument("--limit", type=_lookup_limit, default=10, help="Maximum keyword results (1-50)")
    lookup.add_argument("--json", action="store_true", dest="json_output")

    init = subparsers.add_parser("init", help="Plan or apply bounded SVC project integration")
    init.add_argument("repo", nargs="?", default=".")
    init.add_argument("--agent", default="codex", choices=("codex",))
    init.add_argument("--apply", metavar="PLAN_DIGEST")
    init.add_argument("--json", action="store_true", dest="json_output")

    status = subparsers.add_parser("status", help="Inspect installed, adopted, and generated SVC state")
    status.add_argument("repo", nargs="?", default=".")
    status.add_argument("--json", action="store_true", dest="json_output")

    adopt = subparsers.add_parser("adopt", help="Plan or record explicit project adoption of this corpus")
    adopt.add_argument(
        "version",
        nargs="?",
        help="Packaged SVC version to adopt (defaults to this corpus)",
    )
    adopt.add_argument("repo", nargs="?", default=".")
    adopt.add_argument("--apply", metavar="PLAN_DIGEST")
    adopt.add_argument("--json", action="store_true", dest="json_output")

    update = subparsers.add_parser("self-update", help="Plan or run a supported local CLI installer update")
    update.add_argument("--apply", metavar="PLAN_DIGEST")
    update.add_argument("--json", action="store_true", dest="json_output")

    dev = subparsers.add_parser("dev", help="Observe or safely ensure declared consumer dev capabilities")
    dev_commands = dev.add_subparsers(dest="dev_command", required=True)
    dev_status = dev_commands.add_parser("status", help="Observe one or all declared dev targets without starting them")
    dev_status.add_argument("target", nargs="?")
    dev_status.add_argument("--repo", default=".")
    dev_status.add_argument("--json", action="store_true", dest="json_output")
    dev_identity = dev_commands.add_parser(
        "identity",
        help="Show the resolved workspace identity used for dev coordination",
    )
    dev_identity.add_argument("--repo", default=".")
    dev_identity.add_argument("--json", action="store_true", dest="json_output")
    dev_ensure = dev_commands.add_parser("ensure", help="Reuse or start exactly one declared dev target")
    dev_ensure.add_argument("target")
    dev_ensure.add_argument("--repo", default=".")
    dev_ensure.add_argument("--json", action="store_true", dest="json_output")
    dev_setup = dev_commands.add_parser("setup", help="Plan or apply bounded VS Code Tasks or package script bridges")
    dev_setup.add_argument("integration", choices=("vscode", "npm"))
    dev_setup.add_argument("target", nargs="?")
    dev_setup.add_argument("--repo", default=".")
    setup_mode = dev_setup.add_mutually_exclusive_group()
    setup_mode.add_argument("--plan", action="store_true")
    setup_mode.add_argument("--apply", metavar="PLAN_DIGEST")
    dev_setup.add_argument("--json", action="store_true", dest="json_output")

    telemetry = subparsers.add_parser("telemetry", help="Collect explicit local observability evidence")
    telemetry_resources = telemetry.add_subparsers(dest="telemetry_resource", required=True)
    agent_thread = telemetry_resources.add_parser(
        "agent-thread", help="List or capture provider-obtainable Agent-thread evidence"
    )
    agent_thread_commands = agent_thread.add_subparsers(dest="agent_thread_command", required=True)
    thread_list = agent_thread_commands.add_parser("list", help="List bounded Codex thread selection context")
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
    selector.add_argument("--source", type=Path, help="Exact Codex rollout JSONL source")
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
    except CliUsageError as error:
        if raw_argv[:1] == ["analysis"]:
            _emit_json(
                {
                    "code": "invalid-cli-usage",
                    "message": str(error),
                },
                stream=sys.stderr,
            )
        else:
            print(f"svc: invalid-cli-usage: {error}", file=sys.stderr)
        return EXIT_USAGE
    json_output = bool(getattr(args, "json_output", False))
    try:
        if args.command == "lookup":
            if args.keyword is not None and args.allow_many:
                raise SvcError("invalid-lookup-options", "--all is valid only with --name.")
            query = LookupQuery(
                "name" if args.name is not None else "keyword",
                args.name if args.name is not None else args.keyword,
                args.allow_many,
                args.limit,
            )
            response = CorpusLookup(catalog()).lookup(query)
            _emit_lookup(response, json_output)
            return EXIT_OK

        if args.command == "status":
            payload = inspect_status(Path(args.repo))
            _emit_status(payload, json_output)
            return EXIT_OK if payload["healthy"] else EXIT_CONFLICT

        if args.command == "dev":
            if args.dev_command == "identity":
                payload = inspect_dev_identity(Path(args.repo))
                _emit(payload, json_output)
                return EXIT_OK
            if args.dev_command == "status":
                payload = inspect_dev_status(Path(args.repo), args.target)
                _emit(payload, json_output)
                return EXIT_OK if payload["healthy"] else EXIT_CONFLICT
            if args.dev_command == "setup":
                setup_plan = plan_setup(Path(args.repo), args.integration, args.target)
                if args.apply:
                    payload = {
                        "schema_version": 1,
                        "command": setup_plan.command,
                        **apply_local_plan(cast(LocalPlan, setup_plan), args.apply),
                    }
                    _emit(payload, json_output)
                    return EXIT_OK
                _emit_local_plan(setup_plan, json_output)
                return EXIT_CONFLICT if setup_plan.blockers else EXIT_OK
            payload = ensure_target(Path(args.repo), args.target)
            _emit(payload, json_output)
            return EXIT_OK

        if args.command == "analysis":
            return _run_analysis_tool(args)

        if args.command == "telemetry":
            if args.telemetry_resource == "agent-thread" and args.agent_thread_command == "list":
                payload = list_agent_threads(args.codex_home, args.limit, args.archive_state)
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

        if args.command == "self-update":
            update_plan = plan_self_update()
            if args.apply:
                payload = {
                    "schema_version": 1,
                    "command": "self-update",
                    **apply_self_update(update_plan, args.apply),
                }
                _emit(payload, json_output)
                return EXIT_OK
            _emit_update_plan(update_plan, json_output)
            return EXIT_CONFLICT if update_plan.blockers else EXIT_OK

        if args.command == "init":
            local_plan = plan_init(Path(args.repo), args.agent)
        else:
            local_plan = plan_adopt(Path(args.repo), args.version)
        if args.apply:
            payload = {
                "schema_version": 1,
                "command": local_plan.command,
                **apply_local_plan(local_plan, args.apply),
            }
            _emit(payload, json_output)
            return EXIT_OK
        _emit_local_plan(local_plan, json_output)
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
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"non-finite number: {token}")),
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise AnalysisProtocolError(
            "invalid-analysis-request-json",
            "Analysis request is not strict JSON.",
            {"reason": str(error)},
        ) from error


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


def _emit(payload: dict[str, object], json_output: bool) -> None:
    if json_output:
        _emit_json(payload)
        return
    status = str(payload.get("status", "completed"))
    command = str(payload.get("command", "svc"))
    changed = payload.get("changed")
    suffix = f"; {changed} project files changed" if changed is not None else ""
    print(f"SVC {command}: {status}{suffix}")


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


def _emit_local_plan(plan: Any, json_output: bool) -> None:
    if json_output:
        _emit_json(plan.as_dict())
        return
    print(f"SVC {plan.command} plan: {plan.status} for SVC {plan.target_version}")
    for operation in plan.writes:
        print(f"  {operation.action:7} {operation.path}  {operation.reason}")
    _emit_blockers(plan.blockers)
    print(f"Plan digest: {plan.digest}")
    if not plan.blockers:
        print(f"Apply with: --apply {plan.digest}")


def _emit_update_plan(plan: Any, json_output: bool) -> None:
    if json_output:
        _emit_json(plan.as_dict())
        return
    print(f"SVC self-update plan: {plan.status} from {plan.current_version or 'unavailable'}")
    if plan.command:
        print("  run     " + " ".join(plan.command))
    _emit_blockers(plan.blockers)
    print(f"Plan digest: {plan.digest}")
    if not plan.blockers:
        print(f"Apply with: --apply {plan.digest}")


def _emit_status(payload: dict[str, Any], json_output: bool) -> None:
    if json_output:
        _emit_json(payload)
        return
    installed = payload["installed_cli_version"] or "source-tree"
    runtime = payload["runtime"]
    print(f"SVC status: CLI {installed}; packaged SVC {payload['packaged_svc_version']}; runtime {runtime['status']}")
    project = payload["project"]
    print(f"  {project['status']:16} {project['path']}")
    configuration = payload["configuration"]
    print(f"  {configuration['status']:16} effective configuration")
    managed_ignore = payload["managed_ignore"]
    print(f"  {managed_ignore['status']:16} {managed_ignore['path']}  ({managed_ignore['kind']})")
    for item in payload["guidance"]:
        print(f"  {item['status']:16} {item['path']}  ({item['kind']})")
    print("Healthy" if payload["healthy"] else "Action required")


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
        print(f"  {descriptor.get('thread_id')}  {descriptor.get('archive_state')}  {updated}")


def _emit_telemetry_export(payload: dict[str, Any], json_output: bool) -> None:
    if json_output:
        _emit_json(payload)
        return
    evidence = payload["evidence"]
    if isinstance(evidence, dict):
        print(f"SVC telemetry agent-thread export: exported {evidence.get('path')}")
    else:
        print("SVC telemetry agent-thread export: exported")
    diagnostic_groups = payload.get("diagnostic_groups")
    if isinstance(diagnostic_groups, int) and diagnostic_groups:
        print(f"  {diagnostic_groups} normalized diagnostic group(s); inspect manifest.json in the evidence archive")


def _emit_lookup(response: Any, json_output: bool) -> None:
    if json_output:
        _emit_json(response.as_dict())
        return
    if response.query.mode == "name":
        for index, result in enumerate(response.results):
            if index:
                print("\n---\n")
            print(result.content, end="" if result.content.endswith("\n") else "\n")
        return
    for result in response.results:
        print(f"{result.path}\t{result.title}\t{result.score}")
        print(f"  {result.excerpt}")


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
    if error.details:
        print(
            json.dumps(error.details, ensure_ascii=False, indent=2, sort_keys=True),
            file=sys.stderr,
        )


def _emit_json(payload: dict[str, object], stream: Any | None = None) -> None:
    output = stream or sys.stdout
    json.dump(payload, output, ensure_ascii=False, indent=2, sort_keys=True)
    output.write("\n")


def _exit_code(error: SvcError) -> int:
    if error.code in {
        "apply-failed",
        "invalid-corpus",
        "invalid-release",
        "postcondition-failed",
        "self-update-failed",
        "self-update-verification-failed",
        "staging-failed",
        "output-write-failed",
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
