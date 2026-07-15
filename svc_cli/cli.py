"""Console interface for the packaged SVC corpus and project integration runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .errors import SvcError
from .lookup import CorpusLookup, LookupQuery
from .project import inspect_status, plan_adopt, plan_init
from .release import catalog, runtime_version
from .update import apply_self_update, plan_self_update
from .plans import apply_local_plan


EXIT_OK = 0
EXIT_USAGE = 2
EXIT_CONFLICT = 3
EXIT_FAILURE = 4


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
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
    adopt.add_argument("version", nargs="?", help="Packaged SVC version to adopt (defaults to this corpus)")
    adopt.add_argument("repo", nargs="?", default=".")
    adopt.add_argument("--apply", metavar="PLAN_DIGEST")
    adopt.add_argument("--json", action="store_true", dest="json_output")

    update = subparsers.add_parser("self-update", help="Plan or run a supported local CLI installer update")
    update.add_argument("--apply", metavar="PLAN_DIGEST")
    update.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
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

        if args.command == "self-update":
            plan = plan_self_update()
            if args.apply:
                payload = {"schema_version": 1, "command": "self-update", **apply_self_update(plan, args.apply)}
                _emit(payload, json_output)
                return EXIT_OK
            _emit_update_plan(plan, json_output)
            return EXIT_CONFLICT if plan.blockers else EXIT_OK

        if args.command == "init":
            plan = plan_init(Path(args.repo), args.agent)
        else:
            plan = plan_adopt(Path(args.repo), args.version)
        if args.apply:
            payload = {"schema_version": 1, "command": plan.command, **apply_local_plan(plan, args.apply)}
            _emit(payload, json_output)
            return EXIT_OK
        _emit_local_plan(plan, json_output)
        return EXIT_CONFLICT if plan.blockers else EXIT_OK
    except SvcError as error:
        _emit_error(error, json_output)
        return _exit_code(error)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        _emit_error(SvcError("invalid-release", str(error)), json_output)
        return EXIT_FAILURE


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


def _emit_status(payload: dict[str, object], json_output: bool) -> None:
    if json_output:
        _emit_json(payload)
        return
    installed = payload["installed_cli_version"] or "source-tree"
    runtime = payload["runtime"]
    print(
        f"SVC status: CLI {installed}; packaged SVC {payload['packaged_svc_version']}; "
        f"runtime {runtime['status']}"
    )
    project = payload["project"]
    print(f"  {project['status']:16} {project['path']}")
    for item in payload["guidance"]:
        print(f"  {item['status']:16} {item['path']}  ({item['kind']})")
    print("Healthy" if payload["healthy"] else "Action required")


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
        print(json.dumps(error.details, ensure_ascii=False, indent=2, sort_keys=True), file=sys.stderr)


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
    }:
        return EXIT_FAILURE
    return EXIT_CONFLICT


if __name__ == "__main__":
    raise SystemExit(main())
