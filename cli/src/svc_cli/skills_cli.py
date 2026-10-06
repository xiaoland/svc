"""Skills command grammar and terminal delivery."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable, Literal, TextIO, TypedDict, cast

from . import skills
from .cli_output.skills import (
    AdoptionOutput,
    SkillsOutput,
    SkillsTargetOutput,
    adoption,
    applied,
    installation,
    planned,
    target_output,
)
from .errors import SvcError
from .plans import canonical_json, sha256_bytes
from .skill_adoption import apply_adoption, plan_adoption


_SKILLS_HELP = (
    "Install and manage separately released SVC Skills. File changes are plan-first: "
    "inspect the plan, then repeat with --apply PLAN_DIGEST. Existing foreign or modified "
    "files are preserved. Adoption is a separate project instruction operation; installing "
    "files does not prove host discovery or automatic execution."
)


def register(subparsers: Any, add_output: Callable[..., None]) -> None:
    group = subparsers.add_parser(
        "skills",
        help="Install, inspect, update, and adopt SVC Skills",
        description=_SKILLS_HELP,
    )
    commands = group.add_subparsers(dest="skills_command", required=True)
    descriptions = {
        "install": "Plan copying an explicit SVC release into selected host discovery directories",
        "status": "Inspect installed files and ownership without network access or writes",
        "check": "Compare actual installed files with an explicit or latest stable Skills release",
        "update": "Plan an explicit release update while preserving local changes",
        "remove": "Plan removing clean CLI-owned Skills only",
        "adopt": "Plan project-visible working rules pointing to installed Skills",
        "unadopt": "Plan removing only a clean SVC adoption instruction block",
    }
    for name, description in descriptions.items():
        parser = commands.add_parser(
            name, help=description, description=description, epilog=_SKILLS_HELP
        )
        parser.add_argument("--repo", default=".", help="Project directory")
        parser.add_argument(
            "--agent",
            choices=("codex", "claude"),
            action=None if name in {"adopt", "unadopt"} else "append",
            required=name not in {"status", "check"},
            help="Target host (repeat for multiple hosts; status/check default to both)",
        )
        parser.add_argument(
            "--global",
            dest="global_scope",
            action="store_true",
            help="Use explicitly selected host's user-level Skill directory",
        )
        if name in {"install", "update", "remove", "adopt", "unadopt"}:
            parser.add_argument(
                "--apply",
                metavar="PLAN_DIGEST",
                help="Apply only the freshly recomputed exact plan",
            )
        if name in {"install", "status", "check", "update", "remove"}:
            parser.add_argument(
                "--skill",
                action="append",
                help="Select one SVC Skill (repeat; default all six)",
            )
        if name in {"install", "check", "update"}:
            source = parser.add_mutually_exclusive_group(required=name != "check")
            source.add_argument(
                "--version", help="Explicit stable corpus-v release version"
            )
            source.add_argument(
                "--archive",
                type=Path,
                help="Offline release ZIP with adjacent .zip.sha256",
            )
            parser.add_argument(
                "--checksum", type=Path, help="Explicit offline SHA-256 checksum file"
            )
        if name in {"adopt", "unadopt"}:
            parser.add_argument(
                "--skills-dir",
                type=Path,
                help="Actual Skills root, including an installation owned by another manager",
            )
        add_output(parser, "skills", "Emit the compact typed Skills result")


class ReleaseFields(TypedDict):
    target_version: str | None
    release_notes: str | None
    migration_guidance: str | None


def _release(args: argparse.Namespace) -> skills.SkillArchive:
    if args.archive is not None:
        checksum = args.checksum or args.archive.with_suffix(
            args.archive.suffix + ".sha256"
        )
        return skills.read_release(args.archive, checksum=checksum)
    if args.checksum is not None:
        raise SvcError("invalid-skills-source", "--checksum requires --archive.")
    return skills.resolve_release(args.version)


def run(args: argparse.Namespace) -> tuple[SkillsOutput | AdoptionOutput, int]:
    command = args.skills_command
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        raise SvcError(
            "repo-not-directory",
            "Project root must be an existing directory.",
            {"repo": str(repo)},
        )
    if command in {"adopt", "unadopt"}:
        if args.skills_dir is not None and args.global_scope:
            raise SvcError(
                "invalid-skills-source", "Choose --skills-dir or --global for adoption."
            )
        root = (
            args.skills_dir.resolve()
            if args.skills_dir
            else skills.skills_root(repo, args.agent, args.global_scope)
        )
        adopt_plan = plan_adoption(
            repo, agent=args.agent, skills_root=root, remove=command == "unadopt"
        )
        if args.apply:
            adopt_result = apply_adoption(adopt_plan, args.apply)
            return adoption(adopt_plan, applied_status=adopt_result.status), 0
        return adoption(adopt_plan), 3 if adopt_plan.local.blockers else 0
    targets = tuple(
        skills.SkillTarget(
            Path.home() if args.global_scope else repo,
            cast(skills.Host, agent),
            "global" if args.global_scope else "project",
        )
        for agent in dict.fromkeys(args.agent or ("codex", "claude"))
    )
    if command == "status":
        observed_list = []
        for target in targets:
            units = skills.status(target, args.skill)
            state = (
                "attention"
                if any(unit.status not in {"absent", "current"} for unit in units)
                else "current"
                if any(unit.status == "current" for unit in units)
                else "absent"
            )
            observed_list.append(
                target_output(
                    target, state, tuple(installation(unit) for unit in units)
                )
            )
        observed = tuple(observed_list)
        status: Literal["current", "attention", "absent"] = (
            "attention"
            if any(target.status == "attention" for target in observed)
            else "current"
            if any(target.status == "current" for target in observed)
            else "absent"
        )
        return SkillsOutput(
            command="skills status", mode="status", status=status, targets=observed
        ), 3 if status == "attention" else 0
    archive = None if command == "remove" else _release(args)
    release_fields: ReleaseFields = (
        {"target_version": None, "release_notes": None, "migration_guidance": None}
        if archive is None
        else {
            "target_version": archive.manifest.version,
            "release_notes": f"https://github.com/xiaoland/svc/releases/tag/corpus-v{archive.manifest.version}",
            "migration_guidance": f"https://github.com/xiaoland/svc/tree/{archive.manifest.revision}/corpus/migrations",
        }
    )
    if command == "check":
        assert archive is not None
        observed = tuple(
            target_output(
                target,
                "current"
                if all(unit.status == "current" for unit in units)
                else "available"
                if all(
                    unit.status in {"current", "outdated", "absent"} for unit in units
                )
                else "attention",
                tuple(installation(unit) for unit in units),
            )
            for target in targets
            for units in [skills.check(target, archive, args.skill).units]
        )
        check_status: Literal["attention", "available", "current"] = (
            "attention"
            if any(target.status == "attention" for target in observed)
            else "available"
            if any(target.status == "available" for target in observed)
            else "current"
        )
        return SkillsOutput(
            command="skills check",
            mode="check",
            status=check_status,
            targets=observed,
            **release_fields,
        ), 3 if check_status == "attention" else 0
    plans_list = []
    for target in targets:
        if command == "remove":
            plans_list.append(skills.remove(target, args.skill))
        else:
            assert archive is not None
            prepare = skills.install if command == "install" else skills.update
            plans_list.append(prepare(archive, target, args.skill))
    plans = tuple(plans_list)
    digest = sha256_bytes(canonical_json([plan.digest for plan in plans]))
    plan_status: Literal["ready", "blocked", "noop"] = (
        "blocked"
        if any(plan.status == "blocked" for plan in plans)
        else "ready"
        if any(plan.status == "ready" for plan in plans)
        else "noop"
    )
    machine_command = cast(
        Literal["skills install", "skills update", "skills remove"], f"skills {command}"
    )
    if not args.apply or plan_status == "blocked":
        if args.apply and args.apply != digest:
            raise SvcError(
                "plan-digest-mismatch",
                "The supplied plan digest does not match the current Skills plan.",
                {"expected": digest, "received": args.apply},
            )
        return SkillsOutput(
            command=machine_command,
            mode="plan",
            status=plan_status,
            targets=tuple(planned(plan) for plan in plans),
            plan_digest=digest,
            **release_fields,
        ), 3 if plan_status == "blocked" else 0
    if args.apply != digest:
        raise SvcError(
            "plan-digest-mismatch",
            "The supplied plan digest does not match the current Skills plan.",
            {"expected": digest, "received": args.apply},
        )
    completed: list[SkillsTargetOutput] = []
    stopped = False
    for plan in plans:
        if stopped:
            completed.append(
                target_output(
                    plan.target,
                    "skipped",
                    tuple(
                        installation(
                            unit,
                            status="skipped",
                            message="Earlier target failed; not executed",
                        )
                        for unit in skills.status(plan.target, args.skill)
                    ),
                )
            )
            continue
        result = skills.apply_plan(plan, plan.digest)
        completed.append(applied(plan.target, result))
        stopped = result.status in {"failed", "partial", "blocked"}
    success = any(target.status in {"applied", "partial"} for target in completed)
    final_status: Literal["applied", "noop", "partial", "failed"] = (
        "partial"
        if stopped and success
        else "failed"
        if stopped
        else "applied"
        if success
        else "noop"
    )
    return SkillsOutput(
        command=machine_command,
        mode="apply",
        status=final_status,
        targets=tuple(completed),
        plan_digest=digest,
        **release_fields,
    ), 4 if stopped else 0


def render(payload: SkillsOutput | AdoptionOutput, stream: TextIO) -> None:
    print(f"svc {payload.command}: {payload.status}", file=stream)
    if isinstance(payload, AdoptionOutput):
        print(f"Project: {payload.repo}; host: {payload.agent}", file=stream)
        print(f"Skill entries: {payload.skills_root}", file=stream)
        for mutation in payload.operations:
            print(
                f"  {mutation.action} {mutation.path}: {mutation.reason}", file=stream
            )
        for blocker in payload.blockers:
            print(f"  {blocker.code}: {blocker.message}", file=stream)
    else:
        if payload.target_version:
            print(f"Target release: {payload.target_version}", file=stream)
        for target in payload.targets:
            print(f"{target.agent} ({target.scope}): {target.skills_root}", file=stream)
            for unit in target.units:
                version = (
                    f"; verified version {unit.actual_version}"
                    if unit.actual_version
                    else ""
                )
                observation = (
                    f"; installation {unit.installation_status}"
                    if unit.status != unit.installation_status
                    else ""
                )
                print(
                    f"  {unit.name}: {unit.status}{observation}{version}", file=stream
                )
                if unit.message:
                    print(f"    {unit.message}", file=stream)
                if unit.error:
                    effect = unit.error.details.get("repository_effect")
                    if effect is not None:
                        print(f"    File effect: {effect}", file=stream)
                    rollback = unit.error.details.get("rollback")
                    if isinstance(rollback, dict):
                        print(f"    Rollback: {rollback.get('status')}", file=stream)
                for mutation in unit.operations:
                    print(f"    {mutation.action} {mutation.path}", file=stream)
        if payload.release_notes:
            print(f"Release notes: {payload.release_notes}", file=stream)
            print(f"Migration guidance: {payload.migration_guidance}", file=stream)
    if payload.mode == "plan" and payload.status == "ready":
        print(
            f"Repeat the same command with --apply {payload.plan_digest}", file=stream
        )
