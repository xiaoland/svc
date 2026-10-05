"""Project-visible SVC adoption, independent of Skill file ownership."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from .errors import SvcError
from .plans import (
    Blocker,
    LocalPlan,
    PlanAction,
    LocalApplyResult,
    apply_local_plan,
    make_write,
    sha256_bytes,
)


_BEGIN = "<!-- svc:begin adoption"
_END = "<!-- svc:end adoption -->"
_BLOCK = re.compile(
    r"<!-- svc:begin adoption sha256=([0-9a-f]{64}) -->\n(.*?)\n"
    r"<!-- svc:end adoption -->(?:\n)?",
    re.DOTALL,
)
_SKILL_NAMES = (
    "svc-task-packet",
    "svc-methods",
    "svc-verification",
    "svc-sub-agents",
    "svc-specs",
    "svc-taste",
)


@dataclass(frozen=True)
class AdoptionPlan:
    local: LocalPlan
    agent: str
    skills_root: Path
    remove: bool
    entries: tuple[str, ...]


def _entry_snapshot(root: Path) -> tuple[tuple[str, str], ...]:
    entries = []
    for name in _SKILL_NAMES:
        entry = root / name / "SKILL.md"
        if not entry.exists():
            continue
        if not entry.is_file():
            raise SvcError(
                "invalid-skill-entry",
                "Skill entry must be a file.",
                {"path": str(entry)},
            )
        raw = entry.read_bytes()
        text = raw.decode("utf-8")
        front = text.split("---", 2)
        if (
            len(front) != 3
            or front[0]
            or not re.search(rf"(?m)^name: (?:{name}|\"{name}\")$", front[1])
        ):
            raise SvcError(
                "invalid-skill-entry",
                "Installed Skill name does not match its entry.",
                {"path": str(entry)},
            )
        entries.append((name, sha256_bytes(raw)))
    if not any(name == "svc-task-packet" for name, _ in entries):
        raise SvcError(
            "task-packet-unavailable",
            "Full SVC project adoption requires an available svc-task-packet entry.",
            {"path": str(root)},
        )
    return tuple(entries)


def _body(repo: Path, root: Path, snapshot: tuple[tuple[str, str], ...]) -> str:
    lines = [
        "## SVC working guidance",
        "",
        "Human product intent, preferences, permissions, material trade-offs, and acceptance remain Human authority. Resolve factual and technical claims from evidence; before durable changes, establish the authorized effect and affected owners. Installed Skills grant no additional permissions.",
        "",
        "For every non-trivial task, first recover its existing Task Packet or create the smallest actual `packet.md` in the project's task location. Keep the objective, authorization, current facts, next action, and completion verification recoverable. Skill invocations and child assignments do not create competing tasks or packets.",
        "",
        "Load `svc-task-packet` for that rule, then only the additional Skill whose description matches the current pressure. Required resources stay inside each Skill; optional routes to other Skills do not require them to be installed. Project instructions and local conventions remain authoritative.",
        "",
        "Available entries at adoption planning time:",
        "",
    ]
    for name, _ in snapshot:
        entry = root / name / "SKILL.md"
        # Project-local routes survive checkout relocation; explicit external
        # installations require an absolute pointer to their actual location.
        try:
            pointer = entry.relative_to(repo).as_posix()
        except ValueError:
            pointer = entry.as_posix()
        if "`" in pointer or "\n" in pointer or "\r" in pointer:
            raise SvcError(
                "invalid-skill-path",
                "Skill entry path cannot be represented safely in project instructions.",
                {"path": pointer},
            )
        lines.append(f"- `{name}`: `{pointer}`")
    return "\n".join(lines)


def plan_adoption(
    repo: Path, *, agent: str, skills_root: Path, remove: bool = False
) -> AdoptionPlan:
    root = repo.resolve()
    if not root.is_dir():
        raise SvcError(
            "repo-not-directory",
            "Project root must be an existing directory.",
            {"repo": str(root)},
        )
    if agent not in {"codex", "claude"}:
        raise SvcError("invalid-agent", "Choose codex or claude.")
    relative = "AGENTS.md" if agent == "codex" else "CLAUDE.md"
    target = root / relative
    source_root = Path(os.path.abspath(skills_root))
    snapshot: tuple[tuple[str, str], ...] = ()
    blockers: list[Blocker] = []
    mutations = []
    try:
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise SvcError(
                "path-not-file",
                "Adoption target must be a regular file.",
                {"path": str(target)},
            )
        content = target.read_bytes() if target.exists() else None
        text = content.decode("utf-8") if content is not None else ""
        match = _BLOCK.search(text)
        if text.count(_BEGIN) or text.count(_END):
            if (
                text.count(_BEGIN) != 1
                or text.count(_END) != 1
                or match is None
                or sha256_bytes(match.group(2).encode()) != match.group(1)
            ):
                raise SvcError(
                    "adoption-drift",
                    "Modified or malformed adoption block will be preserved.",
                    {"path": relative},
                )
        if remove:
            after = text[: match.start()] + text[match.end() :] if match else text
            reason = "remove clean SVC adoption block"
            action: PlanAction = "rewrite"
        else:
            snapshot = _entry_snapshot(source_root)
            body = _body(root, source_root, snapshot)
            block = (
                f"{_BEGIN} sha256={sha256_bytes(body.encode())} -->\n{body}\n{_END}\n"
            )
            if match:
                after = text[: match.start()] + block + text[match.end() :]
                action = "refresh"
            else:
                separator = "" if not text else "\n" if text.endswith("\n") else "\n\n"
                after = text + separator + block
                action = "append" if content is not None else "create"
            reason = "establish explicit SVC project adoption"
        if after.encode() != (content or b""):
            mutations.append(make_write(root, relative, action, reason, after.encode()))
    except (SvcError, UnicodeDecodeError, OSError) as error:
        code = error.code if isinstance(error, SvcError) else "adoption-unreadable"
        message = error.message if isinstance(error, SvcError) else str(error)
        blockers.append(Blocker(code, relative, message))
    identity = sha256_bytes(repr((agent, str(source_root), snapshot, remove)).encode())
    local = LocalPlan(
        "skills unadopt" if remove else "skills adopt",
        root,
        identity,
        tuple(mutations),
        tuple(blockers),
    )
    return AdoptionPlan(
        local, agent, source_root, remove, tuple(name for name, _ in snapshot)
    )


def apply_adoption(plan: AdoptionPlan, approved_digest: str) -> LocalApplyResult:
    """Re-observe installed entries and project state before exact apply."""
    current = plan_adoption(
        plan.local.repo,
        agent=plan.agent,
        skills_root=plan.skills_root,
        remove=plan.remove,
    )
    return apply_local_plan(current.local, approved_digest)
