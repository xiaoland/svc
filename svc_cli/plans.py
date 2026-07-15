"""Exact, plan-first local file changes for project integration surfaces."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from .catalog import canonical_json, sha256_bytes
from .errors import SvcError


PLAN_SCHEMA_VERSION = 1


def normalized_target_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or "." in path.parts
        or ".." in path.parts
        or path.as_posix() != value
    ):
        raise ValueError(f"Plan target must be a normalized relative path: {value!r}")
    return value


@dataclass(frozen=True)
class Blocker:
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


@dataclass(frozen=True)
class PlannedWrite:
    path: str
    action: str
    reason: str
    before_sha256: str | None
    before_mode: int | None
    parent_states: tuple[tuple[str, str], ...]
    content: bytes = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        normalized_target_path(self.path)

    @property
    def after_sha256(self) -> str:
        return sha256_bytes(self.content)

    def signature(self) -> dict[str, str | None]:
        return {
            "path": self.path,
            "action": self.action,
            "reason": self.reason,
            "before_sha256": self.before_sha256,
            "before_mode": self.before_mode,
            "parent_states": [list(state) for state in self.parent_states],
            "after_sha256": self.after_sha256,
        }

    def as_dict(self) -> dict[str, str | None]:
        return self.signature()


@dataclass(frozen=True)
class LocalPlan:
    command: str
    repo: Path
    target_version: str
    writes: tuple[PlannedWrite, ...]
    blockers: tuple[Blocker, ...] = ()

    def __post_init__(self) -> None:
        paths = tuple(write.path for write in self.writes)
        if len(paths) != len(set(paths)):
            raise ValueError("A local plan may write each path only once")

    @property
    def status(self) -> str:
        if self.blockers:
            return "blocked"
        return "ready" if self.writes else "noop"

    @property
    def digest(self) -> str:
        return sha256_bytes(canonical_json(self.signature()))

    def signature(self) -> dict[str, object]:
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "command": self.command,
            "repo": str(self.repo.resolve()),
            "target_version": self.target_version,
            "operations": [write.signature() for write in self.writes],
            "blockers": [blocker.as_dict() for blocker in self.blockers],
        }

    def as_dict(self) -> dict[str, object]:
        action_counts: dict[str, int] = {}
        for write in self.writes:
            action_counts[write.action] = action_counts.get(write.action, 0) + 1
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "command": self.command,
            "status": self.status,
            "target_version": self.target_version,
            "operations": [write.as_dict() for write in self.writes],
            "blockers": [blocker.as_dict() for blocker in self.blockers],
            "summary": action_counts,
            "plan_digest": self.digest,
        }


def make_write(
    repo: Path,
    path: str,
    action: str,
    reason: str,
    content: bytes,
) -> PlannedWrite:
    target = _absolute_target(repo, path)
    before = _read_optional_bytes(target)
    before_mode = _read_optional_mode(target)
    return PlannedWrite(
        path=path,
        action=action,
        reason=reason,
        before_sha256=sha256_bytes(before) if before is not None else None,
        before_mode=before_mode,
        parent_states=_parent_states(repo.resolve(), target),
        content=content,
    )


def apply_local_plan(plan: LocalPlan, approved_digest: str) -> dict[str, object]:
    """Apply a plan only when its exact snapshot is still current.

    The plan stages all bytes outside the repository, rechecks every precondition,
    then performs atomic per-file replacements. Ordinary failures restore the
    complete pre-run tree and remove any empty directories created by this apply.
    If another writer changes an already-written target during the transaction,
    rollback preserves that intervening content and reports a rollback conflict.
    """

    if approved_digest != plan.digest:
        raise SvcError(
            "plan-digest-mismatch",
            "The supplied plan digest does not match the current plan.",
            {"expected": plan.digest, "received": approved_digest},
        )
    if plan.blockers:
        raise SvcError(
            "plan-blocked",
            "The plan has unresolved blockers.",
            {"blockers": [blocker.as_dict() for blocker in plan.blockers]},
        )
    if not plan.repo.is_dir():
        raise SvcError("repo-not-directory", "Project root is not a directory.", {"repo": str(plan.repo)})

    _assert_preconditions(plan)
    if not plan.writes:
        return {
            "status": "noop",
            "changed": 0,
            "verification": "passed",
            "plan_digest": plan.digest,
        }

    with tempfile.TemporaryDirectory(prefix="svc-plan-") as staging_directory:
        staging = Path(staging_directory)
        staged: dict[str, bytes] = {}
        for index, write in enumerate(plan.writes):
            staged_path = staging / str(index)
            staged_path.write_bytes(write.content)
            if sha256_bytes(staged_path.read_bytes()) != write.after_sha256:
                raise SvcError("staging-failed", "Staged output did not match the plan.", {"path": write.path})
            staged[write.path] = staged_path.read_bytes()

        _assert_preconditions(plan)
        originals = {
            write.path: _read_optional_bytes(_absolute_target(plan.repo, write.path))
            for write in plan.writes
        }
        created_directories: list[Path] = []
        committed: list[PlannedWrite] = []
        try:
            for write in plan.writes:
                target = _absolute_target(plan.repo, write.path)
                _assert_write_precondition(plan.repo.resolve(), target, write)
                _ensure_parent_directories(plan.repo.resolve(), target, created_directories)
                _commit_write(target, staged[write.path])
                committed.append(write)
            _verify_postconditions(plan)
        except SvcError as error:
            rollback = _rollback(plan, committed, originals, created_directories)
            error.details = {**error.details, "rollback": rollback}
            raise
        except OSError as error:
            rollback = _rollback(plan, committed, originals, created_directories)
            raise SvcError(
                "apply-failed",
                f"Project integration apply failed: {error}",
                {"rollback": rollback},
            ) from error

    return {
        "status": "applied",
        "changed": len(plan.writes),
        "verification": "passed",
        "plan_digest": plan.digest,
    }


def _absolute_target(repo: Path, relative: str) -> Path:
    normalized = normalized_target_path(relative)
    root = repo.resolve()
    target = root.joinpath(*PurePosixPath(normalized).parts)
    try:
        target.resolve(strict=False).relative_to(root)
    except ValueError as error:
        raise SvcError("unsafe-target", "Plan target escapes the project root.", {"path": relative}) from error
    return target


def _read_optional_bytes(path: Path) -> bytes | None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise SvcError("path-not-file", "Integration target must be a regular file.", {"path": str(path)})
    return path.read_bytes()


def _read_optional_mode(path: Path) -> int | None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise SvcError("path-not-file", "Integration target must be a regular file.", {"path": str(path)})
    return path.stat().st_mode & 0o777


def _parent_states(root: Path, target: Path) -> tuple[tuple[str, str], ...]:
    parents: list[Path] = []
    cursor = target.parent
    while cursor != root:
        parents.append(cursor)
        cursor = cursor.parent
    return tuple(
        (parent.relative_to(root).as_posix(), _path_state(parent))
        for parent in reversed(parents)
    )


def _path_state(path: Path) -> str:
    if not path.exists() and not path.is_symlink():
        return "missing"
    if path.is_symlink():
        return "symlink"
    if path.is_dir():
        return "directory"
    return "other"


def _assert_preconditions(plan: LocalPlan) -> None:
    for write in plan.writes:
        _assert_write_precondition(plan.repo.resolve(), _absolute_target(plan.repo, write.path), write)


def _assert_write_precondition(root: Path, path: Path, write: PlannedWrite) -> None:
    current = _read_optional_bytes(path)
    actual = sha256_bytes(current) if current is not None else None
    if actual != write.before_sha256:
        raise SvcError(
            "stale-plan",
            "Project content changed after planning.",
            {"path": write.path, "expected_sha256": write.before_sha256, "actual_sha256": actual},
        )
    actual_mode = _read_optional_mode(path)
    if actual_mode != write.before_mode:
        raise SvcError(
            "stale-plan",
            "Project file mode changed after planning.",
            {"path": write.path, "expected_mode": write.before_mode, "actual_mode": actual_mode},
        )
    for relative, expected_state in write.parent_states:
        actual_state = _path_state(root.joinpath(*PurePosixPath(relative).parts))
        if actual_state != expected_state:
            raise SvcError(
                "stale-plan",
                "Project parent path changed after planning.",
                {"path": write.path, "parent": relative, "expected_state": expected_state, "actual_state": actual_state},
            )


def _ensure_parent_directories(root: Path, target: Path, created: list[Path]) -> None:
    pending: list[Path] = []
    cursor = target.parent
    while cursor != root and not cursor.exists():
        pending.append(cursor)
        cursor = cursor.parent
    if cursor.exists() and not cursor.is_dir():
        raise SvcError("parent-not-directory", "Integration target parent is not a directory.", {"path": str(cursor)})
    for directory in reversed(pending):
        directory.mkdir()
        created.append(directory)


def _write_atomic(path: Path, content: bytes, mode: int | None = None) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".svc-write-", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _commit_write(path: Path, content: bytes) -> None:
    _write_atomic(path, content, _read_optional_mode(path))


def _verify_postconditions(plan: LocalPlan) -> None:
    for write in plan.writes:
        content = _read_optional_bytes(_absolute_target(plan.repo, write.path))
        if content is None or sha256_bytes(content) != write.after_sha256:
            raise SvcError("postcondition-failed", "Applied output differs from the approved plan.", {"path": write.path})


def _rollback(
    plan: LocalPlan,
    committed: list[PlannedWrite],
    originals: dict[str, bytes | None],
    created_directories: list[Path],
) -> str:
    outcome = "succeeded"
    try:
        for write in reversed(committed):
            path = _absolute_target(plan.repo, write.path)
            current = _read_optional_bytes(path)
            current_digest = sha256_bytes(current) if current is not None else None
            if current_digest != write.after_sha256:
                # A concurrent writer owns the newer state. Restoring our snapshot
                # would silently overwrite it, which this transaction must never do.
                outcome = "conflicted"
                continue
            original = originals[write.path]
            if original is None:
                if path.exists() or path.is_symlink():
                    path.unlink()
            else:
                _write_atomic(path, original)
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError:
                pass
    except (OSError, SvcError):
        return "failed"
    return outcome
