"""SVC Skill release validation and file-owned installation transactions.

The service consumes an explicit release archive.  It never imports Corpus
content from the CLI package, and it never assumes ownership of an existing
Skill directory without an SVC installation record.
"""

from __future__ import annotations

import io
import json
import os
import re
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Mapping, Sequence
from urllib.parse import unquote, urlsplit

from filelock import FileLock, Timeout

from .errors import Failure, SvcError
from .plans import (
    LocalPlan,
    PlannedFileMutation,
    apply_local_plan,
    canonical_json,
    make_delete,
    make_write,
    sha256_bytes,
)


REPOSITORY = "https://github.com/xiaoland/svc"
RELEASE_API = "https://api.github.com/repos/xiaoland/svc/releases"
RELEASE_DOWNLOAD = "https://github.com/xiaoland/svc/releases/download/corpus-v{version}/svc-corpus-{version}.zip"
CHECKSUM_DOWNLOAD = RELEASE_DOWNLOAD + ".sha256"
MANIFEST_SCHEMA_VERSION = 1
RECORD_SCHEMA_VERSION = 1
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_MEMBER_BYTES = 4 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 4096
DEFAULT_SKILLS = (
    "svc-methods",
    "svc-task-packet",
    "svc-verification",
    "svc-sub-agents",
    "svc-specs",
    "svc-taste",
)
Host = Literal["codex", "claude"]
Scope = Literal["project", "global"]
Operation = Literal["install", "update", "remove"]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:\+[0-9A-Za-z.-]+)?$"
)
_NAME = re.compile(r"^svc-[a-z0-9]+(?:-[a-z0-9]+)*$")


class SkillArchiveError(ValueError):
    """The archive is not a trusted SVC Skills release."""


class SkillSourceError(SvcError):
    """The release source could not be reached or read."""


@dataclass(frozen=True)
class SkillTarget:
    """One host and scope root. ``root`` is explicit for testability."""

    root: Path
    host: Host = "codex"
    scope: Scope = "project"

    @property
    def skills_root(self) -> Path:
        return skills_root(
            self.root,
            self.host,
            self.scope == "global",
            home=self.root if self.scope == "global" else None,
        )

    @property
    def lock_path(self) -> Path:
        return self.root.resolve() / ".svc-skills.lock"


@dataclass(frozen=True)
class SkillManifest:
    name: str
    path: str
    files: Mapping[str, str]


@dataclass(frozen=True)
class ReleaseManifest:
    version: str
    repository: str
    revision: str
    skills: tuple[SkillManifest, ...]


@dataclass(frozen=True)
class SkillArchive:
    manifest: ReleaseManifest
    files: Mapping[str, bytes]
    source: str
    archive_sha256: str

    def skill(self, name: str) -> SkillManifest:
        for skill in self.manifest.skills:
            if skill.name == name:
                return skill
        raise SkillArchiveError(f"Release does not contain {name!r}")

    def content(self, skill: SkillManifest, relative: str) -> bytes:
        return self.files[_archive_file(skill.path, relative)]


@dataclass(frozen=True)
class SkillRecord:
    name: str
    host: Host
    scope: Scope
    version: str
    source: str
    repository: str
    revision: str
    archive_sha256: str
    path: str
    files: Mapping[str, str]


SkillStatus = Literal[
    "absent",
    "current",
    "outdated",
    "modified",
    "missing",
    "unknown",
    "invalid",
    "unsafe",
]


@dataclass(frozen=True)
class SkillInspection:
    name: str
    status: SkillStatus
    path: str
    version: str | None = None
    revision: str | None = None
    files: Mapping[str, str] = field(default_factory=dict)
    message: str | None = None
    record: SkillRecord | None = None
    actual_version: str | None = None


@dataclass(frozen=True)
class SkillUnitPlan:
    name: str
    operation: Operation
    target: SkillTarget
    local_plan: LocalPlan | None
    inspection: SkillInspection
    reason: str
    error: str | None = None


@dataclass(frozen=True)
class SkillPlan:
    operation: Operation
    target: SkillTarget
    archive: SkillArchive | None
    units: tuple[SkillUnitPlan, ...]

    @property
    def digest(self) -> str:
        return sha256_bytes(
            canonical_json(
                {
                    "schema_version": 1,
                    "operation": self.operation,
                    "target": {
                        "root": str(self.target.root.resolve()),
                        "host": self.target.host,
                        "scope": self.target.scope,
                    },
                    "units": [
                        {
                            "name": unit.name,
                            "digest": unit.local_plan.digest
                            if unit.local_plan is not None
                            else None,
                            "error": unit.error,
                        }
                        for unit in self.units
                    ],
                }
            )
        )

    @property
    def status(self) -> Literal["blocked", "ready", "noop"]:
        if any(unit.error for unit in self.units):
            return "blocked"
        if any(unit.local_plan and unit.local_plan.mutations for unit in self.units):
            return "ready"
        return "noop"

    def as_dict(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "status": self.status,
            "digest": self.digest,
            "target": {
                "root": str(self.target.root.resolve()),
                "host": self.target.host,
                "scope": self.target.scope,
            },
            "units": [
                {
                    "name": unit.name,
                    "status": unit.inspection.status,
                    "reason": unit.reason,
                    "error": unit.error,
                    "operations": [
                        mutation.as_dict() for mutation in unit.local_plan.mutations
                    ]
                    if unit.local_plan
                    else [],
                }
                for unit in self.units
            ],
        }


@dataclass(frozen=True)
class SkillUnitResult:
    name: str
    status: Literal["applied", "noop", "blocked", "failed", "skipped"]
    inspection: SkillInspection
    message: str | None = None
    changed: int = 0
    failure: Failure | None = None
    verification: Literal["passed", "failed", "not-verified"] = "not-verified"


@dataclass(frozen=True)
class SkillApplyResult:
    operation: Operation
    status: Literal["applied", "noop", "blocked", "failed", "partial"]
    plan_digest: str
    units: tuple[SkillUnitResult, ...]
    verification: Literal["passed", "failed", "partial", "not-verified"] = (
        "not-verified"
    )


@dataclass(frozen=True)
class SkillCheck:
    target: SkillTarget
    units: tuple[SkillInspection, ...]


def read_release(
    source: Path | str,
    *,
    checksum: Path | str | None = None,
    timeout: float = 30.0,
) -> SkillArchive:
    """Read a local/offline archive or a URL and validate its full closure."""

    raw, label = _read_source(source, timeout)
    if len(raw) > MAX_ARCHIVE_BYTES:
        raise SkillArchiveError("Skills release archive is too large")
    if checksum is None:
        value = str(source)
        path = Path(value)
        checksum = (
            path.with_suffix(path.suffix + ".sha256")
            if path.exists()
            else value + ".sha256"
        )
    if checksum is not None:
        expected = _read_checksum(checksum, timeout)
        actual = sha256_bytes(raw)
        if actual != expected:
            raise SkillArchiveError("Skills release checksum does not match archive")
    return parse_release(raw, source=str(label))


def skills_root(
    repo: Path,
    agent: Host | str,
    global_scope: bool = False,
    *,
    home: Path | None = None,
) -> Path:
    """Return the discovery directory used by one supported Agent host."""

    if agent not in {"codex", "claude"}:
        raise ValueError(f"Unsupported Agent host: {agent!r}")
    base = (
        (home if global_scope and home is not None else Path.home())
        if global_scope
        else repo
    )
    host_dir = ".agents" if agent == "codex" else ".claude"
    return Path(os.path.abspath(base)) / host_dir / "skills"


def resolve_release(
    version: str | None = None, *, timeout: float = 30.0
) -> SkillArchive:
    """Resolve one immutable corpus release; omitted version means latest stable."""

    selected = version or _latest_release_version(timeout)
    if not _SEMVER.fullmatch(selected):
        raise SkillArchiveError(f"Invalid release version: {selected!r}")
    source = RELEASE_DOWNLOAD.format(version=selected)
    checksum = CHECKSUM_DOWNLOAD.format(version=selected)
    archive = read_release(source, checksum=checksum, timeout=timeout)
    if archive.manifest.version != selected:
        raise SkillArchiveError(
            "Downloaded Skills release identity does not match requested version"
        )
    return archive


def parse_release(raw: bytes, *, source: str = "bytes") -> SkillArchive:
    """Validate manifest, paths, hashes, and archive closure before extraction."""

    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except (OSError, zipfile.BadZipFile) as error:
        raise SkillArchiveError("Invalid Skills release ZIP") from error
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_MEMBERS:
            raise SkillArchiveError("Skills release has too many files")
        members: dict[str, bytes] = {}
        total_size = 0
        for info in infos:
            path = _archive_path(info.filename)
            if path in members:
                raise SkillArchiveError(f"Duplicate ZIP member: {path}")
            if info.is_dir() or _is_symlink(info):
                raise SkillArchiveError(f"ZIP member is not a regular file: {path}")
            if info.flag_bits & 0x1:
                raise SkillArchiveError(f"ZIP member is encrypted: {path}")
            if info.file_size > MAX_MEMBER_BYTES:
                raise SkillArchiveError(f"ZIP member is too large: {path}")
            total_size += info.file_size
            if total_size > MAX_ARCHIVE_BYTES:
                raise SkillArchiveError("Skills release contents are too large")
            members[path] = archive.read(info)
        if "manifest.json" not in members:
            raise SkillArchiveError("Skills release has no manifest.json")
        manifest = _parse_manifest(members["manifest.json"])
        expected = {"manifest.json"}
        for skill in manifest.skills:
            for relative, digest in skill.files.items():
                member = _archive_file(skill.path, relative)
                expected.add(member)
                actual = sha256_bytes(members.get(member, b""))
                if member not in members or actual != digest:
                    raise SkillArchiveError(f"Skill file hash mismatch: {member}")
                if relative == "SKILL.md":
                    _validate_skill_document(
                        skill.name, members[member], manifest.version
                    )
                if relative.lower().endswith(".md"):
                    _validate_markdown_links(skill.path, relative, members)
        if {skill.name for skill in manifest.skills} != set(DEFAULT_SKILLS):
            raise SkillArchiveError("Release must contain exactly the six SVC Skills")
        extras = sorted(
            member
            for member in set(members) - expected
            if not _allowed_release_file(member)
        )
        if extras:
            raise SkillArchiveError(f"Release contains unmanifested files: {extras[0]}")
        return SkillArchive(
            manifest=manifest,
            files=members,
            source=source,
            archive_sha256=sha256_bytes(raw),
        )


def status(
    target: SkillTarget, names: Sequence[str] | None = None
) -> tuple[SkillInspection, ...]:
    selected = _selected_names(target, names)
    return tuple(inspect_skill(target, name) for name in selected)


def inspect_skill(target: SkillTarget, name: str) -> SkillInspection:
    _validate_name(name)
    directory = target.skills_root / name
    state_path = target.skills_root / ".svc" / f"{name}.json"
    record, record_error = _read_record(state_path, target, name)
    if record_error:
        return SkillInspection(
            name, "invalid", _skill_path(target, name), message=record_error
        )
    files, tree_error = _tree_files(directory)
    if tree_error:
        return SkillInspection(
            name, "unsafe", _skill_path(target, name), message=tree_error
        )
    if record is None:
        if files:
            return SkillInspection(
                name, "unknown", _skill_path(target, name), files=files
            )
        if directory.exists() or directory.is_symlink():
            return SkillInspection(
                name,
                "unknown",
                _skill_path(target, name),
                message="An unrecorded Skill directory is not SVC-owned",
            )
        return SkillInspection(name, "absent", _skill_path(target, name))
    if not files:
        return SkillInspection(
            name,
            "missing",
            record.path,
            record=record,
            version=record.version,
            revision=record.revision,
        )
    if dict(files) != dict(record.files):
        return SkillInspection(
            name,
            "modified",
            record.path,
            version=record.version,
            revision=record.revision,
            files=files,
            message="Skill content differs from its SVC installation baseline",
            record=record,
        )
    return SkillInspection(
        name,
        "current",
        record.path,
        record.version,
        record.revision,
        files,
        record=record,
    )


def check(
    target: SkillTarget,
    archive: SkillArchive,
    names: Sequence[str] | None = None,
) -> SkillCheck:
    units: list[SkillInspection] = []
    for name in _selected_names(target, names):
        inspection = inspect_skill(target, name)
        if inspection.status == "current":
            try:
                skill = archive.skill(name)
            except SkillArchiveError:
                skill = None
            if (
                skill is None
                or inspection.record is None
                or inspection.record.version != archive.manifest.version
                or inspection.record.revision != archive.manifest.revision
                or inspection.record.archive_sha256 != archive.archive_sha256
                or dict(inspection.record.files) != dict(skill.files)
            ):
                inspection = SkillInspection(
                    name,
                    "outdated",
                    inspection.path,
                    inspection.version,
                    inspection.revision,
                    inspection.files,
                    "A newer or different release is available",
                    inspection.record,
                    archive.manifest.version,
                )
            else:
                inspection = SkillInspection(
                    inspection.name,
                    inspection.status,
                    inspection.path,
                    inspection.version,
                    inspection.revision,
                    inspection.files,
                    inspection.message,
                    inspection.record,
                    archive.manifest.version,
                )
        units.append(inspection)
    return SkillCheck(target, tuple(units))


def install(
    archive: SkillArchive,
    target: SkillTarget,
    names: Sequence[str] | None = None,
) -> SkillPlan:
    return _plan("install", archive, target, names)


def update(
    archive: SkillArchive,
    target: SkillTarget,
    names: Sequence[str] | None = None,
) -> SkillPlan:
    return _plan("update", archive, target, names)


def remove(
    target: SkillTarget,
    names: Sequence[str] | None = None,
) -> SkillPlan:
    selected = _selected_names(target, names)
    units: list[SkillUnitPlan] = []
    for name in selected:
        inspection = inspect_skill(target, name)
        if inspection.status == "absent":
            units.append(
                SkillUnitPlan(
                    name,
                    "remove",
                    target,
                    None,
                    inspection,
                    "Skill is already absent",
                )
            )
            continue
        if inspection.status != "current" or inspection.record is None:
            units.append(
                SkillUnitPlan(
                    name,
                    "remove",
                    target,
                    None,
                    inspection,
                    "remove only operates on an unmodified SVC-owned Skill",
                    "Skill is not an unmodified SVC-owned installation",
                )
            )
            continue
        units.append(
            SkillUnitPlan(
                name,
                "remove",
                target,
                _make_remove_plan(target, inspection.record),
                inspection,
                "remove the SVC-owned files and installation record",
            )
        )
    return SkillPlan("remove", target, None, tuple(units))


def apply_plan(plan: SkillPlan, approved_digest: str | None) -> SkillApplyResult:
    if approved_digest != plan.digest:
        raise SvcError(
            "plan-digest-mismatch",
            "The supplied Skills plan digest does not match the current plan.",
            {"expected": plan.digest, "received": approved_digest},
        )
    if plan.status == "blocked":
        units = tuple(
            SkillUnitResult(
                unit.name,
                "blocked",
                unit.inspection,
                unit.error,
            )
            for unit in plan.units
        )
        return SkillApplyResult(
            plan.operation, "blocked", plan.digest, units, "not-verified"
        )

    results: list[SkillUnitResult] = []
    batch_parent_paths: list[Path] = []
    for index, unit in enumerate(plan.units):
        if unit.local_plan is None:
            results.append(SkillUnitResult(unit.name, "noop", unit.inspection))
            continue
        try:
            with _operation_lock(unit.target):
                observed = inspect_skill(unit.target, unit.name)
                if (
                    observed.status != unit.inspection.status
                    or dict(observed.files) != dict(unit.inspection.files)
                    or observed.record != unit.inspection.record
                ):
                    raise SvcError(
                        "stale-plan",
                        "Skill state changed after planning.",
                        {"skill": unit.name},
                    )
                applied = apply_local_plan(
                    unit.local_plan,
                    unit.local_plan.digest,
                    allowed_parent_paths=tuple(batch_parent_paths),
                )
        except (SvcError, OSError, Timeout) as error:
            failure = (
                error
                if isinstance(error, SvcError)
                else SvcError("skills-apply-failed", str(error))
            )
            actual = _observe_after_failure(unit.target, unit.name, unit.inspection)
            results.append(
                SkillUnitResult(
                    unit.name,
                    "failed",
                    actual,
                    failure.message,
                    failure=failure.snapshot(),
                    verification="failed",
                )
            )
            for skipped in plan.units[index + 1 :]:
                results.append(
                    SkillUnitResult(
                        skipped.name,
                        "skipped",
                        skipped.inspection,
                        "A previous Skill unit failed; no later unit was attempted",
                    )
                )
            break
        try:
            result_inspection = inspect_skill(unit.target, unit.name)
            if plan.operation == "remove":
                _cleanup_removed_skill(unit.target, unit.name)
                result_inspection = inspect_skill(unit.target, unit.name)
            elif plan.archive is not None:
                result_inspection = _actualize(result_inspection, plan.archive)
        except OSError as error:
            result_inspection = _observe_after_failure(
                unit.target, unit.name, unit.inspection
            )
            failure = SvcError(
                "skills-postcondition-failed",
                f"Cannot inspect Skill after apply: {error}",
                {"repository_effect": "uncertain"},
            )
            results.append(
                SkillUnitResult(
                    unit.name,
                    "failed",
                    result_inspection,
                    failure.message,
                    failure=failure.snapshot(),
                    verification="failed",
                )
            )
            for skipped in plan.units[index + 1 :]:
                results.append(
                    SkillUnitResult(
                        skipped.name,
                        "skipped",
                        skipped.inspection,
                        "A previous Skill unit failed; no later unit was attempted",
                    )
                )
            break
        expected_status = "absent" if plan.operation == "remove" else "current"
        if result_inspection.status != expected_status:
            failure = SvcError(
                "skills-postcondition-failed",
                "Applied Skill does not satisfy its postcondition.",
                {
                    "expected_status": expected_status,
                    "actual_status": result_inspection.status,
                    "repository_effect": (
                        "committed-baseline-conflict"
                        if result_inspection.record is not None
                        else "preserved-external-content"
                    ),
                },
            )
            results.append(
                SkillUnitResult(
                    unit.name,
                    "failed",
                    result_inspection,
                    failure.message,
                    failure=failure.snapshot(),
                    verification="failed",
                )
            )
            for skipped in plan.units[index + 1 :]:
                results.append(
                    SkillUnitResult(
                        skipped.name,
                        "skipped",
                        skipped.inspection,
                        "A previous Skill unit failed; no later unit was attempted",
                    )
                )
            break
        results.append(
            SkillUnitResult(
                unit.name,
                "applied" if applied.status == "applied" else "noop",
                result_inspection,
                changed=applied.changed,
                verification="passed",
            )
        )
        if applied.status == "applied":
            root = unit.local_plan.repo.resolve()
            for mutation in unit.local_plan.mutations:
                for relative, expected in mutation.parent_preconditions:
                    parent = root / PurePosixPath(relative)
                    if (
                        expected == "missing"
                        and parent.is_dir()
                        and parent not in batch_parent_paths
                    ):
                        batch_parent_paths.append(parent)
    statuses = {result.status for result in results}
    final: Literal["applied", "noop", "blocked", "failed", "partial"]
    if "failed" in statuses:
        final = "partial" if "applied" in statuses else "failed"
    elif "blocked" in statuses:
        final = "blocked"
    elif "applied" in statuses:
        final = "applied"
    else:
        final = "noop"
    verification: Literal["passed", "failed", "partial", "not-verified"] = (
        "partial"
        if final == "partial"
        else "failed"
        if final == "failed"
        else "passed"
        if final in {"applied", "noop"}
        else "not-verified"
    )
    return SkillApplyResult(
        plan.operation, final, plan.digest, tuple(results), verification
    )


def _observe_after_failure(
    target: SkillTarget, name: str, fallback: SkillInspection
) -> SkillInspection:
    try:
        return inspect_skill(target, name)
    except OSError as error:
        return SkillInspection(
            name,
            "unsafe",
            fallback.path,
            message=f"Cannot inspect Skill after failure: {error}",
        )


def _actualize(inspection: SkillInspection, archive: SkillArchive) -> SkillInspection:
    if inspection.status != "current" or inspection.record is None:
        return inspection
    try:
        skill = archive.skill(inspection.name)
    except SkillArchiveError:
        return inspection
    if (
        inspection.record.archive_sha256 != archive.archive_sha256
        or inspection.record.version != archive.manifest.version
        or inspection.record.revision != archive.manifest.revision
        or dict(inspection.record.files) != dict(skill.files)
    ):
        return inspection
    return SkillInspection(
        inspection.name,
        inspection.status,
        inspection.path,
        inspection.version,
        inspection.revision,
        inspection.files,
        inspection.message,
        inspection.record,
        archive.manifest.version,
    )


def _matches_archive(
    inspection: SkillInspection, skill: SkillManifest, archive: SkillArchive
) -> bool:
    record = inspection.record
    return (
        inspection.status == "current"
        and record is not None
        and record.version == archive.manifest.version
        and record.revision == archive.manifest.revision
        and record.archive_sha256 == archive.archive_sha256
        and dict(record.files) == dict(skill.files)
    )


def _plan(
    operation: Literal["install", "update"],
    archive: SkillArchive,
    target: SkillTarget,
    names: Sequence[str] | None,
) -> SkillPlan:
    selected = _selected_names(target, names, archive)
    units: list[SkillUnitPlan] = []
    for name in selected:
        inspection = inspect_skill(target, name)
        try:
            skill = archive.skill(name)
        except SkillArchiveError as error:
            units.append(
                SkillUnitPlan(
                    name,
                    operation,
                    target,
                    None,
                    inspection,
                    "release selection",
                    str(error),
                )
            )
            continue
        same_release = _matches_archive(inspection, skill, archive)
        allowed = (
            operation == "install" and (inspection.status == "absent" or same_release)
        ) or (operation == "update" and inspection.status == "current")
        if not allowed:
            units.append(
                SkillUnitPlan(
                    name,
                    operation,
                    target,
                    None,
                    inspection,
                    f"{operation} requires an unmodified SVC-owned boundary",
                    f"Cannot {operation} Skill in status {inspection.status!r}",
                )
            )
            continue
        record = _record_for_archive(target, skill, archive)
        try:
            local_plan = _make_skill_plan(
                target, skill, archive, inspection.record, record, operation
            )
        except (SvcError, OSError) as error:
            units.append(
                SkillUnitPlan(
                    name,
                    operation,
                    target,
                    None,
                    inspection,
                    "release selection",
                    str(error),
                )
            )
        else:
            units.append(
                SkillUnitPlan(
                    name,
                    operation,
                    target,
                    local_plan,
                    inspection,
                    f"{operation} one Skill as an independent file transaction",
                )
            )
    return SkillPlan(operation, target, archive, tuple(units))


def _make_skill_plan(
    target: SkillTarget,
    skill: SkillManifest,
    archive: SkillArchive,
    old_record: SkillRecord | None,
    new_record: SkillRecord,
    operation: Operation,
) -> LocalPlan:
    _assert_safe_target(target)
    mutations: list[PlannedFileMutation] = []
    old_files = old_record.files if old_record else {}
    for relative in sorted(set(old_files) - set(skill.files)):
        mutations.append(
            make_delete(
                target.root,
                _target_file(target, skill.name, relative),
                "delete",
                "remove file absent from target release",
            )
        )
    for relative in sorted(skill.files):
        content = archive.content(skill, relative)
        path = _target_file(target, skill.name, relative)
        current = target.root.resolve() / PurePosixPath(path)
        if (
            current.is_file()
            and not current.is_symlink()
            and sha256_bytes(current.read_bytes()) == skill.files[relative]
        ):
            continue
        mutations.append(
            make_write(
                target.root,
                path,
                "create" if old_record is None else "rewrite",
                f"{operation} {skill.name}/{relative}",
                content,
            )
        )
    state_path = _record_path(target, skill.name)
    state_content = _record_bytes(new_record)
    if (
        state_path.is_file()
        and not state_path.is_symlink()
        and state_path.read_bytes() == state_content
    ):
        pass
    else:
        mutations.append(
            make_write(
                target.root,
                _relative_to_root(target.root, state_path),
                "create" if old_record is None else "rewrite",
                "write SVC Skill installation record",
                state_content,
            )
        )
    return LocalPlan(
        f"skills {operation}", target.root.resolve(), "1", tuple(mutations)
    )


def _assert_safe_target(target: SkillTarget) -> None:
    root = target.root.absolute()
    for path in (target.skills_root, target.skills_root / ".svc"):
        try:
            relative = path.absolute().relative_to(root)
        except ValueError as error:
            raise SvcError(
                "unsafe-target",
                "Skills target escapes its scope root.",
                {"path": str(path)},
            ) from error
        cursor = root
        for part in relative.parts:
            cursor /= part
            if cursor.is_symlink():
                raise SvcError(
                    "unsafe-target",
                    "Skills target contains a symlink parent.",
                    {"path": str(cursor)},
                )


def _make_remove_plan(target: SkillTarget, record: SkillRecord) -> LocalPlan:
    mutations = [
        make_delete(
            target.root,
            _target_file(target, record.name, relative),
            "delete",
            "remove SVC-owned Skill file",
        )
        for relative in sorted(record.files)
    ]
    mutations.append(
        make_delete(
            target.root,
            _relative_to_root(target.root, _record_path(target, record.name)),
            "delete",
            "remove SVC Skill installation record",
        )
    )
    return LocalPlan(
        "skills remove", target.root.resolve(), record.version, tuple(mutations)
    )


def _cleanup_removed_skill(target: SkillTarget, name: str) -> None:
    """Remove only empty directories created for this managed Skill."""

    directory = target.skills_root / name
    if directory.is_dir() and not directory.is_symlink():
        try:
            for root, dirs, _ in os.walk(directory, topdown=False, followlinks=False):
                for child in dirs:
                    child_path = Path(root) / child
                    if not child_path.is_symlink():
                        child_path.rmdir()
            directory.rmdir()
        except OSError:
            return
    state_directory = target.skills_root / ".svc"
    if state_directory.is_dir() and not state_directory.is_symlink():
        try:
            state_directory.rmdir()
        except OSError:
            pass


def _record_for_archive(
    target: SkillTarget, skill: SkillManifest, archive: SkillArchive
) -> SkillRecord:
    return SkillRecord(
        skill.name,
        target.host,
        target.scope,
        archive.manifest.version,
        archive.source,
        archive.manifest.repository,
        archive.manifest.revision,
        archive.archive_sha256,
        _skill_path(target, skill.name),
        dict(skill.files),
    )


def _record_bytes(record: SkillRecord) -> bytes:
    return canonical_json(
        {
            "schema_version": RECORD_SCHEMA_VERSION,
            "name": record.name,
            "host": record.host,
            "scope": record.scope,
            "version": record.version,
            "source": record.source,
            "repository": record.repository,
            "revision": record.revision,
            "archive_sha256": record.archive_sha256,
            "path": record.path,
            "files": dict(sorted(record.files.items())),
        }
    )


def _read_record(
    path: Path, target: SkillTarget, name: str
) -> tuple[SkillRecord | None, str | None]:
    if not path.exists() and not path.is_symlink():
        return None, None
    if path.is_symlink() or not path.is_file():
        return None, "installation record is not a regular file"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != RECORD_SCHEMA_VERSION
        ):
            raise ValueError("unsupported installation record schema")
        files = value["files"]
        if not isinstance(files, dict):
            raise ValueError("record files must be an object")
        _validate_files(files)
        if (
            value.get("name") != name
            or value.get("host") != target.host
            or value.get("scope") != target.scope
        ):
            raise ValueError("installation record identity mismatch")
        if not isinstance(value.get("version"), str) or not _SEMVER.fullmatch(
            value["version"]
        ):
            raise ValueError("invalid record version")
        if not isinstance(value.get("source"), str) or not value["source"]:
            raise ValueError("invalid record source location")
        if value.get("repository") != REPOSITORY or not _REVISION.fullmatch(
            value.get("revision", "")
        ):
            raise ValueError("invalid record source")
        if not isinstance(value.get("archive_sha256"), str) or not _SHA256.fullmatch(
            value["archive_sha256"]
        ):
            raise ValueError("invalid record archive hash")
        path_value = value.get("path")
        if not isinstance(path_value, str) or path_value != _skill_path(target, name):
            raise ValueError("invalid record path")
        return SkillRecord(
            name,
            target.host,
            target.scope,
            value["version"],
            value["source"],
            REPOSITORY,
            value["revision"],
            value["archive_sha256"],
            path_value,
            dict(files),
        ), None
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        return None, str(error)


def _tree_files(directory: Path) -> tuple[dict[str, str], str | None]:
    if not directory.exists() and not directory.is_symlink():
        return {}, None
    if directory.is_symlink() or not directory.is_dir():
        return {}, "Skill path is not a regular directory"
    result: dict[str, str] = {}
    for root, dirs, files in os.walk(directory, followlinks=False):
        root_path = Path(root)
        for child in dirs:
            if (root_path / child).is_symlink():
                return {}, "Skill tree contains a symlink"
        for child in files:
            path = root_path / child
            if path.is_symlink() or not path.is_file():
                return {}, "Skill tree contains a non-regular file"
            relative = path.relative_to(directory).as_posix()
            result[relative] = sha256_bytes(path.read_bytes())
    return result, None


def _selected_names(
    target: SkillTarget,
    names: Sequence[str] | None,
    archive: SkillArchive | None = None,
) -> tuple[str, ...]:
    values = tuple(names) if names is not None else tuple(DEFAULT_SKILLS)
    if not values:
        raise ValueError("No Skills selected")
    for name in values:
        _validate_name(name)
    if len(set(values)) != len(values):
        raise ValueError("Skills selection contains duplicates")
    return values


def _validate_name(name: str) -> None:
    if not _NAME.fullmatch(name):
        raise ValueError(f"Invalid SVC Skill name: {name!r}")


def _validate_files(value: Mapping[str, Any]) -> None:
    for relative, digest in value.items():
        if (
            not isinstance(relative, str)
            or _relative_path(relative) is None
            or not isinstance(digest, str)
            or not _SHA256.fullmatch(digest)
        ):
            raise ValueError("Invalid Skill file map")
    if "SKILL.md" not in value:
        raise ValueError("Skill file map must contain SKILL.md")


def _parse_manifest(raw: bytes) -> ReleaseManifest:
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise SkillArchiveError("manifest.json is not valid UTF-8 JSON") from error
    if (
        not isinstance(value, dict)
        or set(value)
        != {"schema_version", "version", "repository", "revision", "skills"}
        or value.get("schema_version") != MANIFEST_SCHEMA_VERSION
    ):
        raise SkillArchiveError("Unsupported Skills release manifest schema")
    version, repository, revision, entries = (
        value.get(key) for key in ("version", "repository", "revision", "skills")
    )
    if (
        not isinstance(version, str)
        or not _SEMVER.fullmatch(version)
        or repository != REPOSITORY
        or not isinstance(revision, str)
        or not _REVISION.fullmatch(revision)
        or not isinstance(entries, list)
        or not entries
    ):
        raise SkillArchiveError("Invalid Skills release identity")
    skills: list[SkillManifest] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"name", "path", "files"}:
            raise SkillArchiveError("Invalid Skill manifest entry")
        name, path, files = entry.get("name"), entry.get("path"), entry.get("files")
        if (
            not isinstance(name, str)
            or not _NAME.fullmatch(name)
            or name not in DEFAULT_SKILLS
            or name in seen
            or not isinstance(path, str)
            or _relative_path(path) is None
            or path != f"corpus/{name}"
            or not isinstance(files, dict)
        ):
            raise SkillArchiveError("Invalid Skill manifest entry")
        try:
            _validate_files(files)
        except ValueError as error:
            raise SkillArchiveError(str(error)) from error
        seen.add(name)
        skills.append(SkillManifest(name, path, dict(files)))
    return ReleaseManifest(version, repository, revision, tuple(skills))


_MARKDOWN_LINK = re.compile(r'\[[^\]\n]+\]\((?:<([^>\n]+)>|([^\s)]+))(?:\s+"[^"]*")?\)')


def _validate_skill_document(name: str, raw: bytes, version: str) -> None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SkillArchiveError(f"{name}/SKILL.md is not UTF-8") from error
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise SkillArchiveError(f"{name}/SKILL.md has no frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise SkillArchiveError(f"{name}/SKILL.md frontmatter is unclosed") from error
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9_-]*): (.*)", line)
        if (
            match is None
            or match.group(1) in fields
            or match.group(1)
            not in {
                "name",
                "description",
                "metadata",
            }
        ):
            raise SkillArchiveError(f"{name}/SKILL.md frontmatter is invalid")
        fields[match.group(1)] = match.group(2)
    if set(fields) != {"name", "description", "metadata"}:
        raise SkillArchiveError(f"{name}/SKILL.md frontmatter identity is invalid")
    try:
        description = json.loads(fields["description"])
    except (KeyError, json.JSONDecodeError) as error:
        raise SkillArchiveError(f"{name}/SKILL.md description is invalid") from error
    if (
        not isinstance(description, str)
        or not description.strip()
        or len(description) > 1024
        or fields["name"] != name
        or _NAME.fullmatch(name) is None
        or len(name) > 64
    ):
        raise SkillArchiveError(f"{name}/SKILL.md frontmatter identity is invalid")
    try:
        metadata = json.loads(fields["metadata"])
    except (KeyError, json.JSONDecodeError) as error:
        raise SkillArchiveError(f"{name}/SKILL.md metadata is invalid") from error
    if (
        not isinstance(metadata, dict)
        or set(metadata) != {"version"}
        or not isinstance(metadata.get("version"), str)
        or metadata.get("version") != version
    ):
        raise SkillArchiveError(f"{name}/SKILL.md metadata version is inconsistent")


def _validate_markdown_links(
    skill_path: str, relative: str, members: Mapping[str, bytes]
) -> None:
    try:
        text = members[_archive_file(skill_path, relative)].decode("utf-8")
    except UnicodeDecodeError as error:
        raise SkillArchiveError(f"{skill_path}/{relative} is not UTF-8") from error
    text = _markdown_prose(text)
    for match in _MARKDOWN_LINK.finditer(text):
        target = match.group(1) or match.group(2) or ""
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc:
            continue
        target_path = unquote(parsed.path)
        if target_path.startswith("/") or "\\" in target_path:
            raise SkillArchiveError(f"Unsafe Markdown target: {skill_path}/{relative}")
        parts: list[str] = []
        for part in (
            *PurePosixPath(relative).parent.parts,
            *PurePosixPath(target_path).parts,
        ):
            if part in {"", "."}:
                continue
            if part == "..":
                if not parts:
                    raise SkillArchiveError(
                        f"Markdown target escapes Skill: {skill_path}/{relative}"
                    )
                parts.pop()
            else:
                parts.append(part)
        member = _archive_file(skill_path, PurePosixPath(*parts).as_posix())
        if member not in members:
            raise SkillArchiveError(f"Missing Markdown target: {member}")
        if parsed.fragment:
            if not member.lower().endswith(".md"):
                raise SkillArchiveError(
                    f"Unsupported Markdown fragment target: {skill_path}/{relative}"
                )
            if unquote(parsed.fragment) not in _markdown_anchors(members[member]):
                raise SkillArchiveError(f"Missing Markdown fragment target: {member}")


def _markdown_prose(text: str) -> str:
    """Remove fenced, indented, and inline code before following prose links."""

    lines: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence is None and not line.startswith("    "):
            lines.append(line)
    prose = "\n".join(lines)
    return re.sub(r"`[^`\n]*`", "", prose)


def _markdown_anchors(raw: bytes) -> set[str]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SkillArchiveError("Markdown fragment target is not UTF-8") from error
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for title in re.findall(
        r"^#{1,6}\s+(.+?)\s*#*\s*$", _markdown_prose(text), re.MULTILINE
    ):
        slug = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        anchors.add(f"{slug}-{count}" if count else slug)
    return anchors


def _read_source(source: Path | str, timeout: float) -> tuple[bytes, str]:
    value = str(source)
    path = Path(value)
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise SkillArchiveError("Skills release source must be a regular file")
        try:
            with path.open("rb") as stream:
                return stream.read(MAX_ARCHIVE_BYTES + 1), str(path)
        except OSError as error:
            raise SkillSourceError(
                "skills-source-failed", f"Cannot read Skills release source: {error}"
            ) from error
    if not value.startswith(("https://", "http://")):
        raise SkillArchiveError(f"Skills release source does not exist: {value}")
    try:
        with urllib.request.urlopen(value, timeout=timeout) as response:
            return response.read(MAX_ARCHIVE_BYTES + 1), value
    except OSError as error:
        raise SkillSourceError(
            "skills-source-failed", f"Cannot download Skills release: {error}"
        ) from error


def _read_checksum(source: Path | str, timeout: float) -> str:
    raw, _ = _read_source(source, timeout)
    token = raw.decode("ascii", errors="strict").split()[0] if raw.split() else ""
    if not _SHA256.fullmatch(token):
        raise SkillArchiveError("Invalid Skills release checksum")
    return token


def _latest_release_version(timeout: float) -> str:
    candidates: list[tuple[tuple[int, int, int], str]] = []
    for page in range(1, 21):
        request = urllib.request.Request(
            f"{RELEASE_API}?per_page=100&page={page}",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "svc-cli",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read(1_048_576)
            entries = json.loads(raw.decode("utf-8"))
        except OSError as error:
            raise SkillSourceError(
                "skills-source-failed", f"Cannot resolve latest Skills release: {error}"
            ) from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SkillArchiveError(
                f"Cannot resolve latest Skills release: {error}"
            ) from error
        if not isinstance(entries, list):
            raise SkillArchiveError("GitHub releases response is not a list")
        for entry in entries:
            if (
                not isinstance(entry, dict)
                or entry.get("draft")
                or entry.get("prerelease")
            ):
                continue
            tag = entry.get("tag_name")
            if not isinstance(tag, str) or not tag.startswith("corpus-v"):
                continue
            version = tag.removeprefix("corpus-v")
            parsed = _stable_semver(version)
            if parsed is not None:
                candidates.append((parsed, version))
        if len(entries) < 100:
            break
    if candidates:
        return max(candidates)[1]
    raise SkillArchiveError("No stable corpus Skills release is available")


def _stable_semver(value: str) -> tuple[int, int, int] | None:
    match = _SEMVER.fullmatch(value)
    if match is None:
        return None
    return (
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
    )


def _archive_path(value: str) -> str:
    if "\\" in value or "\0" in value or _relative_path(value) is None:
        raise SkillArchiveError(f"Unsafe archive path: {value!r}")
    return value


def _allowed_release_file(value: str) -> bool:
    return value in {"LICENSE", "LICENSE.md", "LICENSE.txt", "NOTICE"}


def _relative_path(value: str) -> str | None:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        return None
    return value


def _archive_file(skill_path: str, relative: str) -> str:
    return f"{skill_path}/{relative}"


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return (info.external_attr >> 16) & 0o170000 == 0o120000


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _skill_path(target: SkillTarget, name: str) -> str:
    host_dir = ".agents" if target.host == "codex" else ".claude"
    return f"{host_dir}/skills/{name}"


def _target_file(target: SkillTarget, name: str, relative: str) -> str:
    return f"{_skill_path(target, name)}/{relative}"


def _record_path(target: SkillTarget, name: str) -> Path:
    return target.skills_root / ".svc" / f"{name}.json"


def _relative_to_root(root: Path, path: Path) -> str:
    return path.absolute().relative_to(root.absolute()).as_posix()


class _operation_lock:
    def __init__(self, target: SkillTarget) -> None:
        self.lock = FileLock(str(target.lock_path), mode=0o600)

    def __enter__(self) -> None:
        try:
            self.lock.acquire(timeout=0)
        except Timeout as error:
            raise SvcError(
                "skills-busy", "Another Skills operation is in progress."
            ) from error

    def __exit__(self, *_: object) -> None:
        self.lock.release()
