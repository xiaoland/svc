from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .manifest import Artifact, ReleaseManifest, canonical_json, sha256_bytes
from .migrations import resolve_migrations


MISSING = "missing"
SYMLINK = "symlink"
DIRECTORY = "directory"
STATE_SCHEMA_VERSION = 1
PLAN_SCHEMA_VERSION = 1
V98_IMPLEMENTATION_TASTE_SHA256 = (
    "1bcdfcc50c9c7c2a231df596a2e8b271ca193d8ae06a0d9ce3693bebac6af686"
)
V98_OBSOLETE_MANAGED_PATHS = (
    "docs/00-meta/input-intent.md",
    "docs/00-meta/input-constraint.md",
    "docs/00-meta/input-reality.md",
    "docs/00-meta/input-artifact.md",
    "docs/00-meta/mode-a-explore.md",
    "docs/00-meta/mode-b-solidify.md",
    "docs/00-meta/mode-c-execute.md",
    "docs/00-meta/mode-d-diagnose.md",
    "docs/00-meta/concepts.md",
)
V10_ROOT_MARKERS = (
    "docs/00-meta/working-protocol.md",
    "docs/00-meta/implementation-taste.md",
    "docs/10-prd/README.md",
)


class ProtocolError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


@dataclass(frozen=True)
class Operation:
    action: str
    path: str
    reason: str
    artifact_id: str | None = None
    before: str | None = None
    after: str | None = None


@dataclass(frozen=True)
class Plan:
    command: str
    source_version: str | None
    target_version: str
    manifest_sha256: str
    migrations: tuple[str, ...]
    operations: tuple[Operation, ...]
    blockers: tuple[dict[str, str], ...]
    snapshot: dict[str, str]

    def core(self) -> dict[str, Any]:
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "command": self.command,
            "source_version": self.source_version,
            "target_version": self.target_version,
            "manifest_sha256": self.manifest_sha256,
            "migrations": list(self.migrations),
            "operations": [asdict(item) for item in self.operations],
            "blockers": list(self.blockers),
            "snapshot": self.snapshot,
        }

    @property
    def digest(self) -> str:
        return sha256_bytes(canonical_json(self.core()))

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.core(),
            "plan_digest": self.digest,
            "dry_run": True,
            "summary": dict(sorted(Counter(item.action for item in self.operations).items())),
        }


def _repo_root(repo: Path) -> Path:
    root = repo.expanduser().resolve()
    if not root.is_dir():
        raise ProtocolError("invalid-repository", f"Repository is not a directory: {root}")
    return root


def _target(repo: Path, relative: str) -> Path:
    rel = PurePosixPath(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise ProtocolError("unsafe-path", f"Path escapes repository: {relative}")
    return repo.joinpath(*rel.parts)


def _path_state(repo: Path, relative: str) -> str:
    path = repo
    for part in PurePosixPath(relative).parts:
        path = path / part
        if path.is_symlink():
            return SYMLINK
    if not path.exists():
        return MISSING
    if path.is_dir():
        return DIRECTORY
    if not path.is_file():
        return "special"
    return sha256_bytes(path.read_bytes())


def _snapshot(repo: Path, paths: set[str]) -> dict[str, str]:
    return {path: _path_state(repo, path) for path in sorted(paths)}


def _blocker(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _state_path(manifest: ReleaseManifest) -> str:
    return manifest.state_artifact.target


def _load_state(repo: Path, manifest: ReleaseManifest) -> dict[str, Any] | None:
    relative = _state_path(manifest)
    state = _path_state(repo, relative)
    if state == MISSING:
        return None
    if state in {SYMLINK, DIRECTORY, "special"}:
        raise ProtocolError("invalid-state", f"State path is not a regular file: {relative}")
    try:
        raw = json.loads(_target(repo, relative).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProtocolError("invalid-state", f"Cannot read {relative}: {exc}") from exc
    if raw.get("schema_version") != STATE_SCHEMA_VERSION:
        raise ProtocolError("invalid-state", "Unsupported consumer state schema")
    return raw


def plan_init(repo: Path, manifest: ReleaseManifest) -> Plan:
    repo = _repo_root(repo)
    operations: list[Operation] = []
    blockers: list[dict[str, str]] = []
    paths = {artifact.target for artifact in manifest.artifacts}
    snapshot = _snapshot(repo, paths)

    state_target = _state_path(manifest)
    if snapshot[state_target] != MISSING:
        blockers.append(
            _blocker(
                "installed-state-exists",
                state_target,
                "Initialization cannot replace an existing installation state",
            )
        )

    for artifact in manifest.artifacts:
        before = snapshot[artifact.target]
        if artifact.file_class == "generated":
            action = "generate" if before == MISSING else "noop"
            operations.append(
                Operation(action, artifact.target, "record installation state", artifact.artifact_id, before)
            )
            continue
        if before in {SYMLINK, DIRECTORY, "special"}:
            blockers.append(
                _blocker("unsafe-target", artifact.target, f"Target is {before}, not a regular file")
            )
            operations.append(
                Operation("noop", artifact.target, "unsafe target", artifact.artifact_id, before, artifact.digest)
            )
        elif before == MISSING:
            operations.append(
                Operation("create", artifact.target, artifact.init_action, artifact.artifact_id, before, artifact.digest)
            )
        elif artifact.file_class == "consumer-owned":
            operations.append(
                Operation("noop", artifact.target, "preserve Consumer-owned content", artifact.artifact_id, before, before)
            )
        else:
            blockers.append(
                _blocker(
                    "managed-without-provenance",
                    artifact.target,
                    "Managed target exists without SVC installation state; use a supported migration",
                )
            )
            operations.append(
                Operation("noop", artifact.target, "refuse untracked managed content", artifact.artifact_id, before, before)
            )

    return Plan(
        command="init",
        source_version=None,
        target_version=manifest.svc_version,
        manifest_sha256=manifest.digest,
        migrations=(),
        operations=tuple(operations),
        blockers=tuple(blockers),
        snapshot=snapshot,
    )


def _validate_v10_consumer_owned(
    repo: Path,
    snapshot: dict[str, str],
    blockers: list[dict[str, str]],
) -> None:
    agents_path = "AGENTS.md"
    product_path = "docs/10-prd/README.md"
    if snapshot[agents_path] == MISSING:
        blockers.append(
            _blocker("consumer-action-required", agents_path, "Create v10 root instructions before apply")
        )
    elif snapshot[agents_path] not in {SYMLINK, DIRECTORY, "special"}:
        text = _target(repo, agents_path).read_text(encoding="utf-8", errors="replace")
        missing = [marker for marker in V10_ROOT_MARKERS if marker not in text]
        if missing:
            blockers.append(
                _blocker(
                    "consumer-action-required",
                    agents_path,
                    "Root instructions must reference: " + ", ".join(missing),
                )
            )
    else:
        blockers.append(_blocker("unsafe-target", agents_path, "Root instructions are not a regular file"))

    if snapshot[product_path] == MISSING:
        blockers.append(
            _blocker(
                "consumer-action-required",
                product_path,
                "Move or consolidate v9.8 product truth into the v10 Consumer-owned path",
            )
        )
    elif snapshot[product_path] in {SYMLINK, DIRECTORY, "special"}:
        blockers.append(_blocker("unsafe-target", product_path, "Product truth is not a regular file"))


def _plan_current_installation(
    repo: Path,
    manifest: ReleaseManifest,
    state: dict[str, Any],
) -> Plan:
    paths = {artifact.target for artifact in manifest.artifacts}
    snapshot = _snapshot(repo, paths)
    blockers: list[dict[str, str]] = []
    operations: list[Operation] = []
    for artifact in manifest.artifacts:
        before = snapshot[artifact.target]
        if artifact.file_class == "svc-managed" and before != artifact.digest:
            blockers.append(_blocker("managed-drift", artifact.target, "Managed content is missing or drifted"))
        elif artifact.file_class == "consumer-owned" and before == MISSING:
            blockers.append(_blocker("consumer-missing", artifact.target, "Consumer-owned file is missing"))
        operations.append(
            Operation("noop", artifact.target, "already at target version", artifact.artifact_id, before, before)
        )
    return Plan(
        command="migrate",
        source_version=state.get("installed_version"),
        target_version=manifest.svc_version,
        manifest_sha256=manifest.digest,
        migrations=(),
        operations=tuple(operations),
        blockers=tuple(blockers),
        snapshot=snapshot,
    )


def plan_migrate(
    repo: Path,
    manifest: ReleaseManifest,
    target_version: str,
    from_version: str | None = None,
) -> Plan:
    repo = _repo_root(repo)
    if target_version != manifest.svc_version:
        raise ProtocolError(
            "unsupported-target",
            f"This CLI contains SVC {manifest.svc_version}, not {target_version}",
        )

    state = _load_state(repo, manifest)
    if state and state.get("installed_version") == target_version:
        return _plan_current_installation(repo, manifest, state)

    source_version = state.get("installed_version") if state else from_version
    migration_ids: tuple[str, ...] = ()
    blockers: list[dict[str, str]] = []
    if state and from_version and from_version != source_version:
        blockers.append(
            _blocker("source-version-conflict", _state_path(manifest), "--from-version conflicts with state")
        )
    if source_version is None:
        blockers.append(
            _blocker(
                "unknown-source-version",
                _state_path(manifest),
                "v9.8 has no state; declare --from-version 9.8.0 explicitly",
            )
        )
    else:
        try:
            migration_ids = tuple(
                migration.migration_id
                for migration in resolve_migrations(source_version, target_version)
            )
        except ValueError as exc:
            blockers.append(_blocker("unsupported-migration", _state_path(manifest), str(exc)))

    paths = {artifact.target for artifact in manifest.artifacts}
    paths.update(V98_OBSOLETE_MANAGED_PATHS)
    paths.update({"AGENTS.md", "docs/10-prd/README.md"})
    snapshot = _snapshot(repo, paths)
    operations: list[Operation] = []

    if source_version == "9.8.0":
        _validate_v10_consumer_owned(repo, snapshot, blockers)
        for path in V98_OBSOLETE_MANAGED_PATHS:
            if snapshot[path] != MISSING:
                blockers.append(
                    _blocker(
                        "manual-cleanup-required",
                        path,
                        "v9.8 has no provenance digest; inspect and remove or relocate this obsolete file",
                    )
                )
                operations.append(Operation("manual", path, "Consumer must resolve unknown legacy content", before=snapshot[path]))

    for artifact in manifest.artifacts:
        before = snapshot[artifact.target]
        if artifact.file_class == "generated":
            if before != MISSING:
                blockers.append(
                    _blocker("state-conflict", artifact.target, "Unexpected state exists for a stateless v9.8 source")
                )
                operations.append(Operation("noop", artifact.target, "refuse unexpected state", artifact.artifact_id, before, before))
            else:
                operations.append(Operation("generate", artifact.target, "record migrated installation", artifact.artifact_id, before))
            continue
        if artifact.file_class == "consumer-owned":
            operations.append(
                Operation("noop", artifact.target, "preserve Consumer-owned content", artifact.artifact_id, before, before)
            )
            continue
        if before in {SYMLINK, DIRECTORY, "special"}:
            blockers.append(_blocker("unsafe-target", artifact.target, f"Managed target is {before}"))
            operations.append(Operation("noop", artifact.target, "unsafe target", artifact.artifact_id, before, before))
        elif before == MISSING:
            operations.append(Operation("create", artifact.target, "install v10 managed artifact", artifact.artifact_id, before, artifact.digest))
        elif before == artifact.digest:
            operations.append(Operation("noop", artifact.target, "managed artifact already current", artifact.artifact_id, before, before))
        elif (
            artifact.artifact_id == "implementation-taste"
            and source_version == "9.8.0"
            and before == V98_IMPLEMENTATION_TASTE_SHA256
        ):
            operations.append(Operation("update", artifact.target, "replace recognized v9.8 managed artifact", artifact.artifact_id, before, artifact.digest))
        else:
            blockers.append(
                _blocker("managed-drift", artifact.target, "Managed content does not match a recognized source digest")
            )
            operations.append(Operation("noop", artifact.target, "refuse managed drift", artifact.artifact_id, before, before))

    return Plan(
        command="migrate",
        source_version=source_version,
        target_version=target_version,
        manifest_sha256=manifest.digest,
        migrations=migration_ids,
        operations=tuple(operations),
        blockers=tuple(blockers),
        snapshot=snapshot,
    )


def _state_content(plan: Plan, manifest: ReleaseManifest) -> bytes:
    state = {
        "schema_version": STATE_SCHEMA_VERSION,
        "installed_version": manifest.svc_version,
        "release_manifest_sha256": manifest.digest,
        "managed_files": {
            artifact.target: {
                "artifact_id": artifact.artifact_id,
                "sha256": artifact.digest,
            }
            for artifact in manifest.managed
        },
        "applied_migrations": list(plan.migrations),
        "last_plan_digest": plan.digest,
        "verification": "passed",
    }
    return json.dumps(state, indent=2, sort_keys=True).encode() + b"\n"


def _operation_content(operation: Operation, plan: Plan, manifest: ReleaseManifest) -> bytes:
    if operation.action == "generate":
        return _state_content(plan, manifest)
    if operation.artifact_id is None:
        raise ProtocolError("invalid-plan", f"No artifact source for {operation.path}")
    return manifest.by_id(operation.artifact_id).content()


def _apply_to_tree(root: Path, plan: Plan, manifest: ReleaseManifest) -> None:
    for operation in plan.operations:
        path = _target(root, operation.path)
        if operation.action in {"create", "update", "generate"}:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(_operation_content(operation, plan, manifest))
        elif operation.action == "delete" and path.exists():
            path.unlink()


def _verify_tree(root: Path, plan: Plan, manifest: ReleaseManifest) -> None:
    for artifact in manifest.managed:
        if _path_state(root, artifact.target) != artifact.digest:
            raise ProtocolError("postcondition-failed", f"Managed digest mismatch: {artifact.target}")
    for artifact in manifest.consumer_owned:
        current = _path_state(root, artifact.target)
        if current in {MISSING, SYMLINK, DIRECTORY, "special"}:
            raise ProtocolError("postcondition-failed", f"Consumer-owned file is unavailable: {artifact.target}")
        before = plan.snapshot.get(artifact.target)
        operation = next(item for item in plan.operations if item.path == artifact.target)
        if operation.action == "noop" and before != current:
            raise ProtocolError("postcondition-failed", f"Consumer-owned file changed: {artifact.target}")
    if "9.8.0-to-10.0.0" in plan.migrations:
        for path in V98_OBSOLETE_MANAGED_PATHS:
            if _path_state(root, path) != MISSING:
                raise ProtocolError("postcondition-failed", f"Obsolete v9.8 path remains: {path}")

    state_path = _state_path(manifest)
    state = _load_state(root, manifest)
    if state is None or state.get("installed_version") != manifest.svc_version:
        raise ProtocolError("postcondition-failed", "Installed version was not recorded")
    if state.get("release_manifest_sha256") != manifest.digest:
        raise ProtocolError("postcondition-failed", "Installed manifest digest is stale")
    expected_managed = {
        artifact.target: {"artifact_id": artifact.artifact_id, "sha256": artifact.digest}
        for artifact in manifest.managed
    }
    if state.get("managed_files") != expected_managed:
        raise ProtocolError("postcondition-failed", "Installed managed-file inventory is invalid")
    state_operation = next((item for item in plan.operations if item.path == state_path), None)
    if state_operation and state_operation.action == "generate":
        if state.get("last_plan_digest") != plan.digest:
            raise ProtocolError("postcondition-failed", "Installed plan digest is invalid")


def _copy_snapshot_to_shadow(repo: Path, shadow: Path, plan: Plan) -> None:
    for relative, before in plan.snapshot.items():
        if before in {MISSING, SYMLINK, DIRECTORY, "special"}:
            continue
        target = _target(shadow, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_target(repo, relative), target)


def _atomic_write(path: Path, content: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _commit_write(path: Path, content: bytes) -> None:
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    _atomic_write(path, content, mode)


def _journal_entries(repo: Path, changes: list[Operation], journal: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    backup_dir = journal / "backups"
    backup_dir.mkdir(parents=True)
    for index, operation in enumerate(changes):
        path = _target(repo, operation.path)
        entry: dict[str, Any] = {"path": operation.path, "existed": path.is_file()}
        if path.is_file():
            backup_name = f"{index}.bin"
            _atomic_write(backup_dir / backup_name, path.read_bytes(), 0o600)
            entry["backup"] = backup_name
            entry["mode"] = stat.S_IMODE(path.stat().st_mode)
        entries.append(entry)
    return entries


def _existing_operation_parents(repo: Path, changes: list[Operation]) -> set[str]:
    existing: set[str] = set()
    for operation in changes:
        parent = _target(repo, operation.path).parent
        while parent != repo:
            if parent.exists():
                existing.add(parent.relative_to(repo).as_posix())
            parent = parent.parent
    return existing


def _rollback(
    repo: Path,
    journal: Path,
    entries: list[dict[str, Any]],
    applied: int,
    existing_parents: set[str],
) -> bool:
    try:
        for entry in reversed(entries[:applied]):
            path = _target(repo, entry["path"])
            if entry["existed"]:
                content = (journal / "backups" / entry["backup"]).read_bytes()
                _atomic_write(path, content, entry["mode"])
            elif path.exists() or path.is_symlink():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
        for entry in reversed(entries[:applied]):
            parent = _target(repo, entry["path"]).parent
            while parent != repo:
                relative = parent.relative_to(repo).as_posix()
                if relative in existing_parents:
                    break
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent
        return True
    except BaseException:
        return False


def _transaction_base(repo: Path) -> Path:
    state_root = repo / ".svc"
    base = state_root / "transactions"
    if state_root.is_symlink() or base.is_symlink():
        raise ProtocolError("unsafe-transaction-state", ".svc transaction paths cannot be symlinks")
    return base


def _cleanup_transaction(
    repo: Path,
    journal: Path,
    transaction_base_existed: bool,
    existing_parents: set[str],
) -> None:
    if journal.exists():
        shutil.rmtree(journal)
    base = journal.parent
    if not transaction_base_existed:
        try:
            base.rmdir()
        except OSError:
            pass
    if ".svc" not in existing_parents:
        try:
            (repo / ".svc").rmdir()
        except OSError:
            pass


def _write_journal(journal: Path, record: dict[str, Any]) -> None:
    _atomic_write(journal / "journal.json", canonical_json(record), 0o600)


def recover_pending_transaction(repo: Path) -> dict[str, Any] | None:
    repo = _repo_root(repo)
    base = _transaction_base(repo)
    if not base.exists():
        return None
    if not base.is_dir():
        raise ProtocolError("unsafe-transaction-state", ".svc/transactions is not a directory")
    journals = sorted(path for path in base.iterdir() if path.is_dir())
    if not journals:
        return None
    if len(journals) != 1:
        raise ProtocolError("recovery-required", "Multiple pending SVC transactions require inspection")

    journal = journals[0]
    try:
        record = json.loads((journal / "journal.json").read_text(encoding="utf-8"))
        entries = record["entries"]
        existing_parents = set(record["existing_parents"])
        transaction_base_existed = bool(record["transaction_base_existed"])
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ProtocolError(
            "recovery-required",
            f"Pending transaction journal is unreadable: {exc}",
        ) from exc

    if record.get("status") == "committed":
        _cleanup_transaction(repo, journal, transaction_base_existed, existing_parents)
        return {"status": "committed-journal-cleaned", "plan_digest": record.get("plan_digest")}
    if record.get("status") != "committing":
        raise ProtocolError("recovery-required", "Pending transaction has an unknown status")

    rolled_back = _rollback(
        repo,
        journal,
        entries,
        int(record.get("applied", 0)),
        existing_parents,
    )
    if not rolled_back:
        raise ProtocolError("recovery-required", "Automatic recovery of pending transaction failed")
    _cleanup_transaction(repo, journal, transaction_base_existed, existing_parents)
    return {"status": "rolled-back", "plan_digest": record.get("plan_digest")}


def apply_plan(repo: Path, plan: Plan, approved_digest: str, manifest: ReleaseManifest) -> dict[str, Any]:
    repo = _repo_root(repo)
    recovery = recover_pending_transaction(repo)
    if approved_digest != plan.digest:
        raise ProtocolError(
            "plan-digest-mismatch",
            "Apply requires the exact current dry-run plan digest",
            {"approved": approved_digest, "current": plan.digest},
        )
    if plan.blockers:
        raise ProtocolError("plan-blocked", "Plan has unresolved blockers", {"blockers": list(plan.blockers)})
    current_snapshot = _snapshot(repo, set(plan.snapshot))
    if current_snapshot != plan.snapshot:
        raise ProtocolError(
            "stale-plan",
            "Relevant repository state changed after planning",
            {"planned": plan.snapshot, "current": current_snapshot},
        )

    changes = [
        item for item in plan.operations if item.action in {"create", "update", "delete", "generate"}
    ]
    if not changes:
        _verify_tree(repo, plan, manifest)
        return {
            "status": "noop",
            "plan_digest": plan.digest,
            "changed": 0,
            "migrations": list(plan.migrations),
            "preconditions": "passed",
            "staged_verification": "not-required",
            "postconditions": "passed",
            "verification": "passed",
            "recovery": recovery,
        }

    with tempfile.TemporaryDirectory(prefix="svc-shadow-") as shadow_name:
        shadow = Path(shadow_name)
        _copy_snapshot_to_shadow(repo, shadow, plan)
        _apply_to_tree(shadow, plan, manifest)
        _verify_tree(shadow, plan, manifest)

    current_snapshot = _snapshot(repo, set(plan.snapshot))
    if current_snapshot != plan.snapshot:
        raise ProtocolError(
            "stale-plan",
            "Relevant repository state changed during staging",
            {"planned": plan.snapshot, "current": current_snapshot},
        )

    existing_parents = _existing_operation_parents(repo, changes)
    base = _transaction_base(repo)
    transaction_base_existed = base.exists()
    journal = base / plan.digest
    try:
        journal.mkdir(parents=True, exist_ok=False)
        entries = _journal_entries(repo, changes, journal)
        journal_record = {
            "plan_digest": plan.digest,
            "status": "committing",
            "applied": 0,
            "entries": entries,
            "existing_parents": sorted(existing_parents),
            "transaction_base_existed": transaction_base_existed,
        }
        _write_journal(journal, journal_record)
    except BaseException as exc:
        _cleanup_transaction(repo, journal, transaction_base_existed, existing_parents)
        raise ProtocolError("journal-failed", f"Cannot prepare transaction journal: {exc}") from exc

    applied = 0
    try:
        for index, operation in enumerate(changes, start=1):
            journal_record["applied"] = index
            _write_journal(journal, journal_record)
            path = _target(repo, operation.path)
            if operation.action == "delete":
                path.unlink()
                _fsync_directory(path.parent)
            else:
                _commit_write(path, _operation_content(operation, plan, manifest))
            applied = index
        _verify_tree(repo, plan, manifest)
        journal_record["status"] = "committed"
        _write_journal(journal, journal_record)
    except BaseException as exc:
        intended = int(journal_record.get("applied", applied))
        rolled_back = _rollback(repo, journal, entries, intended, existing_parents)
        if rolled_back:
            _cleanup_transaction(repo, journal, transaction_base_existed, existing_parents)
        raise ProtocolError(
            "apply-failed",
            f"Apply failed; rollback {'succeeded' if rolled_back else 'requires recovery'}: {exc}",
            {"rollback": "succeeded" if rolled_back else "recovery-required"},
        ) from exc

    cleanup = "completed"
    try:
        _cleanup_transaction(repo, journal, transaction_base_existed, existing_parents)
    except OSError:
        cleanup = "pending"

    return {
        "status": "applied",
        "plan_digest": plan.digest,
        "changed": len(changes),
        "migrations": list(plan.migrations),
        "preconditions": "passed",
        "staged_verification": "passed",
        "postconditions": "passed",
        "verification": "passed",
        "journal_cleanup": cleanup,
        "recovery": recovery,
    }


def inspect_status(repo: Path, manifest: ReleaseManifest) -> dict[str, Any]:
    repo = _repo_root(repo)
    state = _load_state(repo, manifest)
    artifacts: list[dict[str, Any]] = []
    expected_managed = {
        artifact.target: {"artifact_id": artifact.artifact_id, "sha256": artifact.digest}
        for artifact in manifest.managed
    }
    state_valid = bool(
        state is not None
        and state.get("installed_version") == manifest.svc_version
        and state.get("release_manifest_sha256") == manifest.digest
        and state.get("managed_files") == expected_managed
        and state.get("verification") == "passed"
        and isinstance(state.get("last_plan_digest"), str)
        and len(state["last_plan_digest"]) == 64
        and set(state["last_plan_digest"]) <= set("0123456789abcdef")
    )
    healthy = state_valid
    for artifact in manifest.artifacts:
        current = _path_state(repo, artifact.target)
        if artifact.file_class == "svc-managed":
            status = "current" if current == artifact.digest else ("missing" if current == MISSING else "drift")
        elif artifact.file_class == "consumer-owned":
            status = "missing" if current == MISSING else ("unsafe" if current in {SYMLINK, DIRECTORY, "special"} else "present")
        else:
            status = "current" if state_valid else ("missing" if state is None else "stale")
        if status not in {"current", "present"}:
            healthy = False
        artifacts.append(
            {
                "id": artifact.artifact_id,
                "class": artifact.file_class,
                "path": artifact.target,
                "status": status,
            }
        )

    detected_source = None
    if state is None and _path_state(repo, "docs/00-meta/implementation-taste.md") == V98_IMPLEMENTATION_TASTE_SHA256:
        detected_source = "9.8.0-candidate"
    return {
        "schema_version": 1,
        "healthy": healthy,
        "state_valid": state_valid,
        "installed_version": state.get("installed_version") if state else None,
        "target_version": manifest.svc_version,
        "detected_source": detected_source,
        "manifest_sha256": manifest.digest,
        "artifacts": artifacts,
        "summary": dict(sorted(Counter(item["status"] for item in artifacts).items())),
    }
