from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .engine import (
    ProtocolError,
    apply_plan,
    inspect_status,
    plan_init,
    plan_migrate,
    recover_pending_transaction,
)
from .manifest import load_manifest


EXIT_OK = 0
EXIT_CONFLICT = 3
EXIT_FAILURE = 4


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="svc",
        description="Versioned SVC consumption and migration protocol.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Inspect installation, drift, and conflicts")
    status.add_argument("repo", nargs="?", default=".")
    status.add_argument("--json", action="store_true", dest="json_output")

    init = subparsers.add_parser("init", help="Plan or apply SVC initialization")
    init.add_argument("repo", nargs="?", default=".")
    init.add_argument("--apply", metavar="PLAN_DIGEST")
    init.add_argument("--json", action="store_true", dest="json_output")

    migrate = subparsers.add_parser("migrate", help="Plan or apply sequential migration")
    migrate.add_argument("repo", nargs="?", default=".")
    migrate.add_argument("--to", required=True, dest="target_version")
    migrate.add_argument("--from-version")
    migrate.add_argument("--apply", metavar="PLAN_DIGEST")
    migrate.add_argument("--json", action="store_true", dest="json_output")
    return parser


def _emit_json(payload: dict[str, Any], stream: Any | None = None) -> None:
    if stream is None:
        stream = sys.stdout
    json.dump(payload, stream, indent=2, sort_keys=True)
    stream.write("\n")


def _emit_plan(plan: Any) -> None:
    print(f"SVC {plan.command} plan: {plan.source_version or 'unmanaged'} -> {plan.target_version}")
    for operation in plan.operations:
        print(f"  {operation.action:8} {operation.path}  {operation.reason}")
    if plan.blockers:
        print("Blockers:")
        for blocker in plan.blockers:
            print(f"  {blocker['code']}: {blocker['path']}: {blocker['message']}")
    print(f"Plan digest: {plan.digest}")
    if not plan.blockers:
        print(f"Apply with: --apply {plan.digest}")


def _emit_status(payload: dict[str, Any]) -> None:
    installed = payload["installed_version"] or payload["detected_source"] or "unmanaged"
    print(f"SVC status: {installed} -> {payload['target_version']}")
    for artifact in payload["artifacts"]:
        print(f"  {artifact['status']:8} {artifact['path']}  ({artifact['class']})")
    print("Healthy" if payload["healthy"] else "Action required")


def _emit_recovery(recovery: dict[str, Any] | None) -> None:
    if recovery:
        print(f"Recovered prior transaction: {recovery['status']} ({recovery['plan_digest']})")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    json_output = bool(getattr(args, "json_output", False))
    try:
        manifest = load_manifest()
        repo = Path(args.repo)
        recovery = recover_pending_transaction(repo)
        if args.command == "status":
            payload = inspect_status(repo, manifest)
            payload["recovery"] = recovery
            if json_output:
                _emit_json(payload)
            else:
                _emit_recovery(recovery)
                _emit_status(payload)
            return EXIT_OK if payload["healthy"] else EXIT_CONFLICT

        if args.command == "init":
            plan = plan_init(repo, manifest)
        else:
            plan = plan_migrate(
                repo,
                manifest,
                target_version=args.target_version,
                from_version=args.from_version,
            )

        if args.apply:
            result = apply_plan(repo, plan, args.apply, manifest)
            result["recovery"] = recovery or result.get("recovery")
            payload = {"schema_version": 1, "command": args.command, **result}
            if json_output:
                _emit_json(payload)
            else:
                _emit_recovery(recovery)
                print(
                    f"SVC {args.command} {result['status']}: "
                    f"{result['changed']} changed; verification {result['verification']}"
                )
            return EXIT_OK

        if json_output:
            payload = plan.as_dict()
            payload["recovery"] = recovery
            _emit_json(payload)
        else:
            _emit_recovery(recovery)
            _emit_plan(plan)
        return EXIT_CONFLICT if plan.blockers else EXIT_OK
    except ProtocolError as exc:
        if json_output:
            _emit_json(exc.as_dict(), stream=sys.stderr)
        else:
            print(f"svc: {exc.code}: {exc.message}", file=sys.stderr)
            if exc.details:
                print(json.dumps(exc.details, indent=2, sort_keys=True), file=sys.stderr)
        return EXIT_CONFLICT if exc.code in {
            "installed-state-exists",
            "managed-drift",
            "plan-blocked",
            "plan-digest-mismatch",
            "stale-plan",
            "unknown-source-version",
        } else EXIT_FAILURE
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        payload = {
            "schema_version": 1,
            "error": {"code": "invalid-release", "message": str(exc), "details": {}},
        }
        if json_output:
            _emit_json(payload, stream=sys.stderr)
        else:
            print(f"svc: invalid-release: {exc}", file=sys.stderr)
        return EXIT_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
