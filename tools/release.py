from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parents[1]
FRAGMENT_RE = re.compile(
    r"^(?P<name>[a-z0-9][a-z0-9-]*)\.(?P<impact>major|minor|patch)\.md$"
)
VERSION_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
IMPACT_ORDER = {"patch": 0, "minor": 1, "major": 2}
RELEASE_BUNDLE_MANIFEST = "svc-release-manifest.json"
RELEASE_BUNDLE_CHECKER = "release-check.py"
RELEASE_BUNDLE_METADATA = "svc-release-metadata.json"
RELEASE_BUNDLE_NOTES = "RELEASE_NOTES.md"
RELEASE_BUNDLE_CHECKSUMS = "SHA256SUMS"
TARGET_RELEASE_PLAN = "svc-target-release-plan.json"
TARGET_RELEASE_BUNDLE_SCHEMA_VERSION = 2
CUTOVER_BASELINE_TAG = "v11.0.0"
CUTOVER_BASELINE_COMMIT = "f99baad7cf9b8798475c3037636dbc8a0e7a738b"
CUTOVER_BASELINE_FILES = {
    "sustainable_vibe_coding-11.0.0-py3-none-any.whl": (
        "f57fbe6a212a37ae49a8736f648667f0e42b6e56375c346546cebeae828af507"
    ),
    "sustainable_vibe_coding-11.0.0.tar.gz": (
        "377cd1ab36fc8f227566743019775f96ef3324b5a7a7ba1ff8e150ac9f6900b0"
    ),
}
TARGET_RELEASE_METADATA_SCHEMA_VERSION = 1
REQUIRED_MAIN_QUALIFICATION_JOBS = {
    "Python 3.11",
    "Python 3.14",
    "Quality and architecture",
    "Distribution",
    "Release policy",
}
GITHUB_ACTIONS_APP_ID = 15368


class ReleaseError(ValueError):
    pass


def parse_version(value: str) -> tuple[int, int, int]:
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise ReleaseError(f"Version must be stable SemVer: {value}")
    return tuple(int(match.group(name)) for name in ("major", "minor", "patch"))


def release_tag(version: str) -> str:
    parse_version(version)
    return f"v{version}"


def tag_version(tag: str) -> str:
    if not tag.startswith("v"):
        raise ReleaseError(f"Release tag must start with v: {tag}")
    version = tag.removeprefix("v")
    parse_version(version)
    if tag != release_tag(version):
        raise ReleaseError(f"Release tag must be canonical SemVer: {tag}")
    return version


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def distribution_files(directory: Path) -> list[Path]:
    files = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and (path.name.endswith(".whl") or path.name.endswith(".tar.gz"))
    )
    if not files:
        raise ReleaseError(f"No wheel or sdist in {directory}")
    return files


def distribution_metadata_version(path: Path) -> str:
    """Read the core metadata version from one wheel or source distribution."""
    if path.name.endswith(".whl"):
        try:
            with zipfile.ZipFile(path) as archive:
                metadata_names = [
                    name
                    for name in archive.namelist()
                    if name.endswith(".dist-info/METADATA")
                ]
                if len(metadata_names) != 1:
                    raise ReleaseError(
                        f"Wheel must contain one METADATA file: {path.name}"
                    )
                metadata = archive.read(metadata_names[0]).decode("utf-8")
        except (OSError, UnicodeDecodeError, zipfile.BadZipFile) as error:
            raise ReleaseError(f"Could not inspect wheel metadata: {path.name}") from error
    elif path.name.endswith(".tar.gz"):
        try:
            with tarfile.open(path, "r:gz") as archive:
                metadata_members = [
                    member
                    for member in archive.getmembers()
                    if member.isfile() and member.name.count("/") == 1
                    and member.name.endswith("/PKG-INFO")
                ]
                if len(metadata_members) != 1:
                    raise ReleaseError(
                        f"Sdist must contain one top-level PKG-INFO: {path.name}"
                    )
                stream = archive.extractfile(metadata_members[0])
                if stream is None:
                    raise ReleaseError(f"Could not read sdist metadata: {path.name}")
                metadata = stream.read().decode("utf-8")
        except (OSError, UnicodeDecodeError, tarfile.TarError) as error:
            raise ReleaseError(f"Could not inspect sdist metadata: {path.name}") from error
    else:
        raise ReleaseError(f"Unsupported distribution file: {path.name}")
    versions = [
        line.removeprefix("Version: ").strip()
        for line in metadata.splitlines()
        if line.startswith("Version: ")
    ]
    names = [
        line.removeprefix("Name: ").strip()
        for line in metadata.splitlines()
        if line.startswith("Name: ")
    ]
    if len(names) != 1 or names[0] != "sustainable-vibe-coding":
        raise ReleaseError(f"Distribution metadata project name differs: {path.name}")
    if len(versions) != 1:
        raise ReleaseError(f"Distribution metadata has no unique version: {path.name}")
    parse_version(versions[0])
    return versions[0]


def bump(value: str, impact: str) -> str:
    major, minor, patch = parse_version(value)
    if impact == "major":
        return f"{major + 1}.0.0"
    if impact == "minor":
        return f"{major}.{minor + 1}.0"
    if impact == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ReleaseError(f"Unknown impact: {impact}")


def bump_impact(previous: str, current: str) -> str:
    before = parse_version(previous)
    after = parse_version(current)
    if after <= before:
        raise ReleaseError(f"Release version must increase: {previous} -> {current}")
    if after[0] > before[0] and after[1:] == (0, 0):
        return "major"
    if after[0] == before[0] and after[1] > before[1] and after[2] == 0:
        return "minor"
    if after[:2] == before[:2] and after[2] > before[2]:
        return "patch"
    raise ReleaseError(f"Version is not a single Behavioral SemVer bump: {previous} -> {current}")


def git_commit(reference: str, root: Path = ROOT) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", f"{reference}^{{commit}}"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        raise ReleaseError(f"Git reference does not resolve to a commit: {reference}") from error
    commit = result.stdout.strip()
    if not COMMIT_RE.fullmatch(commit):
        raise ReleaseError(f"Git reference did not resolve to a full commit SHA: {reference}")
    return commit


def _bundle_path(bundle_dir: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ReleaseError("Release bundle path must be a non-empty string")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != relative:
        raise ReleaseError(f"Release bundle path must be a safe POSIX relative path: {relative}")
    return bundle_dir / path


def _sorted_unique_strings(value: object, description: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ReleaseError(f"Release bundle {description} must be a non-empty string list")
    if value != sorted(set(value)):
        raise ReleaseError(f"Release bundle {description} must be sorted and unique")
    return value


def _git_output(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )
    return result.stdout.strip()


def _require_commit(reference: str, root: Path) -> str:
    commit = git_commit(reference, root)
    object_type = _git_output(root, "cat-file", "-t", commit)
    if object_type != "commit":
        raise ReleaseError(f"Git reference does not peel to one commit: {reference}")
    return commit


def remote_release_tags(
    remote: str = "origin", root: Path = ROOT
) -> dict[str, str]:
    """Resolve strict remote release refs to peeled commits without tag metadata."""
    try:
        output = _git_output(
            root,
            "ls-remote",
            "--tags",
            remote,
            "refs/tags/v*",
        )
    except subprocess.CalledProcessError as error:
        raise ReleaseError(f"Could not read release tags from remote {remote}") from error
    direct: dict[str, str] = {}
    peeled: dict[str, str] = {}
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) != 2:
            raise ReleaseError("Remote tag response is malformed")
        object_id, reference = fields
        if not COMMIT_RE.fullmatch(object_id):
            raise ReleaseError(f"Remote tag has an invalid object ID: {reference}")
        is_peeled = reference.endswith("^{}")
        raw_reference = reference.removesuffix("^{}")
        prefix = "refs/tags/"
        if not raw_reference.startswith(prefix):
            raise ReleaseError(f"Remote tag response has an unexpected ref: {reference}")
        tag = raw_reference.removeprefix(prefix)
        try:
            tag_version(tag)
        except ReleaseError:
            continue
        target = peeled if is_peeled else direct
        if tag in target and target[tag] != object_id:
            raise ReleaseError(f"Remote tag ref is ambiguous: {tag}")
        target[tag] = object_id
    resolved: dict[str, str] = {}
    for tag, object_id in direct.items():
        commit = peeled.get(tag)
        if commit is None:
            try:
                object_type = _git_output(root, "cat-file", "-t", object_id)
            except subprocess.CalledProcessError as error:
                raise ReleaseError(
                    f"Remote tag object is unavailable locally: {tag}"
                ) from error
            if object_type != "commit":
                raise ReleaseError(f"Remote tag does not peel to a commit: {tag}")
            commit = object_id
        try:
            if _require_commit(commit, root) != commit:
                raise AssertionError("unreachable")
        except (ReleaseError, subprocess.CalledProcessError) as error:
            raise ReleaseError(f"Remote tag does not peel to a commit: {tag}") from error
        resolved[tag] = commit
    orphaned = set(peeled) - set(direct)
    if orphaned:
        raise ReleaseError(
            f"Remote returned peeled tags without exact refs: {sorted(orphaned)}"
        )
    return resolved


def _is_ancestor(ancestor: str, descendant: str, root: Path) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise ReleaseError(
            f"Could not compare Git ancestry: {ancestor} -> {descendant}"
        )
    return result.returncode == 0


def previous_release_tag(
    commit: str,
    remote: str = "origin",
    root: Path = ROOT,
) -> tuple[str, str]:
    """Return the greatest strict reachable tag at or after the cutover anchor."""
    candidate_commit = _require_commit(commit, root)
    tags = remote_release_tags(remote, root)
    baseline_commit = tags.get(CUTOVER_BASELINE_TAG)
    if baseline_commit is None:
        raise ReleaseError(f"Remote is missing cutover baseline {CUTOVER_BASELINE_TAG}")
    if not _is_ancestor(baseline_commit, candidate_commit, root):
        raise ReleaseError(
            f"Candidate commit is not descended from {CUTOVER_BASELINE_TAG}"
        )
    reachable = [
        (tag, tagged_commit)
        for tag, tagged_commit in tags.items()
        if parse_version(tag_version(tag))
        >= parse_version(tag_version(CUTOVER_BASELINE_TAG))
        and tagged_commit != candidate_commit
        and _is_ancestor(tagged_commit, candidate_commit, root)
    ]
    if not reachable:
        raise ReleaseError(f"No previous release tag is reachable from {commit}")
    return max(reachable, key=lambda item: parse_version(tag_version(item[0])))


def _fragment_name(path: str) -> re.Match[str]:
    prefix = "changes/"
    if not path.startswith(prefix):
        raise ReleaseError(f"Change fragment must be under changes/: {path}")
    match = FRAGMENT_RE.fullmatch(path.removeprefix(prefix))
    if not match:
        raise ReleaseError(f"Invalid change fragment name: {path}")
    return match


def _git_blob(root: Path, commit: str, path: str) -> str:
    try:
        return _git_output(root, "show", f"{commit}:{path}")
    except subprocess.CalledProcessError as error:
        raise ReleaseError(f"Tagged source is missing required path: {path}") from error


def _fragment_summary(path: str, content: str) -> str:
    if not content.strip():
        raise ReleaseError(f"Empty change fragment: {path}")
    for line in content.splitlines():
        summary = line.strip().lstrip("#*- ").strip()
        if summary:
            return summary
    raise ReleaseError(f"Change fragment has no summary: {path}")


def validate_append_only_fragments(
    commit: str,
    root: Path = ROOT,
) -> None:
    """Reject every post-cutover fragment mutation, deletion, rename, or reuse."""
    baseline = _require_commit(CUTOVER_BASELINE_TAG, root)
    candidate = _require_commit(commit, root)
    if not _is_ancestor(baseline, candidate, root):
        raise ReleaseError(
            f"Candidate commit is not descended from {CUTOVER_BASELINE_TAG}"
        )
    history = _git_output(
        root,
        "log",
        "--format=",
        "--name-status",
        "--find-renames",
        f"{baseline}..{candidate}",
        "--",
        "changes",
    )
    additions: set[str] = set()
    for line in history.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        status = fields[0]
        paths = fields[1:]
        relevant = [
            path
            for path in paths
            if path not in {"changes/.gitkeep", "changes/README.md"}
        ]
        if not relevant:
            continue
        for path in relevant:
            _fragment_name(path)
        if status != "A" or len(relevant) != 1:
            raise ReleaseError(
                "Post-cutover change fragments are append-only; "
                f"observed {status} for {relevant}"
            )
        path = relevant[0]
        if path in additions:
            raise ReleaseError(f"Change fragment path was reused: {path}")
        additions.add(path)
        creation_count = len(
            _git_output(
                root,
                "log",
                "--format=%H",
                "--diff-filter=A",
                candidate,
                "--",
                path,
            ).splitlines()
        )
        if creation_count != 1:
            raise ReleaseError(f"Change fragment path was reused: {path}")


def target_fragments(
    previous_tag: str,
    commit: str,
    root: Path = ROOT,
) -> list[dict[str, object]]:
    previous_commit = _require_commit(previous_tag, root)
    candidate = _require_commit(commit, root)
    validate_append_only_fragments(candidate, root)
    diff = _git_output(
        root,
        "diff",
        "--name-status",
        "--no-renames",
        previous_commit,
        candidate,
        "--",
        "changes",
    )
    selected: list[dict[str, object]] = []
    for line in diff.splitlines():
        if not line:
            continue
        status, path = line.split("\t", 1)
        if path in {"changes/.gitkeep", "changes/README.md"}:
            continue
        match = _fragment_name(path)
        if status != "A":
            raise ReleaseError(
                f"Release-window fragment is not a new append-only path: {path}"
            )
        content = _git_blob(root, candidate, path)
        slug = match.group("name")
        migration: str | None = None
        if match.group("impact") == "major":
            migration = f"src/migrations/{slug}.md"
            migration_content = _git_blob(root, candidate, migration)
            if not migration_content.strip():
                raise ReleaseError(
                    f"MAJOR migration note must be non-empty: {migration}"
                )
        selected.append(
            {
                "path": path,
                "impact": match.group("impact"),
                "summary": _fragment_summary(path, content),
                "migration": migration,
            }
        )
    return sorted(selected, key=lambda item: str(item["path"]))


def _target_notes(
    version: str,
    previous_tag: str,
    selected: list[dict[str, object]],
) -> str:
    lines = [f"# SVC {version}", "", f"Previous release: {previous_tag}", ""]
    if not selected:
        lines.append(
            "No externally visible behavioral changes were declared for this release."
        )
        return "\n".join(lines) + "\n"
    labels = {"major": "Major changes", "minor": "Minor changes", "patch": "Patches"}
    for impact in ("major", "minor", "patch"):
        group = [item for item in selected if item["impact"] == impact]
        if not group:
            continue
        lines.extend([f"## {labels[impact]}", ""])
        for item in group:
            lines.append(f"- {item['summary']} (`{item['path']}`)")
            if item["migration"] is not None:
                lines.append(f"  Migration: `{item['migration']}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def target_qualification(
    commit: str,
    *,
    base: str | None = None,
    release_none: bool = False,
    remote: str = "origin",
    root: Path = ROOT,
) -> dict[str, object]:
    """Qualify PR/main source and derive its tag-free rehearsal version."""
    candidate = _require_commit(commit, root)
    previous_tag, previous_commit = previous_release_tag(candidate, remote, root)
    selected = target_fragments(previous_tag, candidate, root)
    if base is not None:
        comparison = _require_commit(base, root)
        pr_diff = _git_output(
            root,
            "diff",
            "--name-status",
            f"{comparison}...{candidate}",
            "--",
            "changes",
        )
        added = {
            fields[1]
            for line in pr_diff.splitlines()
            if len(fields := line.split("\t")) == 2
            and fields[0] == "A"
            and fields[1] not in {"changes/.gitkeep", "changes/README.md"}
        }
        for path in added:
            _fragment_name(path)
        if not added and not release_none:
            raise ReleaseError(
                "Pull request requires a change fragment or explicit release:none decision"
            )
    impacts = [str(item["impact"]) for item in selected]
    impact = (
        max(impacts, key=IMPACT_ORDER.__getitem__) if impacts else "patch"
    )
    previous_version = tag_version(previous_tag)
    target_version = bump(previous_version, impact)
    return {
        "commit": candidate,
        "previous_tag": previous_tag,
        "previous_commit": previous_commit,
        "previous_version": previous_version,
        "target_version": target_version,
        "impact": impact,
        "fragments": selected,
        "release": "none" if base is not None and not added else "changes",
        "pdm_build_scm_version": target_version,
    }


def classify_main_qualification(
    commit: str,
    observed: object,
) -> dict[str, object]:
    """Verify durable CI push-to-main evidence for one exact admitted commit."""
    if not COMMIT_RE.fullmatch(commit):
        raise ReleaseError("Qualification commit must be a full SHA-1")
    if not isinstance(observed, dict):
        return {"state": "ambiguous", "reason": "invalid-observation"}
    runs_observation = observed.get("runs")
    jobs_by_run = observed.get("jobs_by_run")
    checks_observation = observed.get("check_runs")
    if (
        not isinstance(runs_observation, dict)
        or not isinstance(jobs_by_run, dict)
        or not isinstance(checks_observation, dict)
    ):
        return {
            "state": "ambiguous",
            "reason": "missing-runs-jobs-or-check-runs",
        }
    if (
        runs_observation.get("http_status") != 200
        or checks_observation.get("http_status") != 200
    ):
        return {"state": "ambiguous", "reason": "qualification-api-error"}
    runs_body = runs_observation.get("body")
    checks_body = checks_observation.get("body")
    if (
        not isinstance(runs_body, dict)
        or not isinstance(runs_body.get("workflow_runs"), list)
        or not isinstance(checks_body, dict)
        or not isinstance(checks_body.get("check_runs"), list)
    ):
        return {"state": "ambiguous", "reason": "invalid-runs-or-check-runs-body"}
    matching_runs = [
        run
        for run in runs_body["workflow_runs"]
        if isinstance(run, dict)
        and isinstance(run.get("id"), int)
        and run["id"] > 0
        and isinstance(run.get("path"), str)
        and (
            run["path"] == ".github/workflows/ci.yml"
            or (
                run["path"].startswith(".github/workflows/ci.yml@")
                and bool(run["path"].removeprefix(".github/workflows/ci.yml@"))
            )
        )
        and run.get("event") == "push"
        and run.get("head_branch") == "main"
        and run.get("head_sha") == commit
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
    ]
    if len(matching_runs) != 1:
        return {
            "state": "mismatch" if matching_runs else "ambiguous",
            "reason": "successful-main-run-count",
        }
    run = matching_runs[0]
    run_id = run["id"]
    check_suite_id = run.get("check_suite_id")
    if not isinstance(check_suite_id, int) or check_suite_id <= 0:
        return {"state": "ambiguous", "reason": "run-check-suite-unavailable"}
    jobs_observation = jobs_by_run.get(str(run_id))
    if (
        not isinstance(jobs_observation, dict)
        or jobs_observation.get("http_status") != 200
        or not isinstance(jobs_observation.get("body"), dict)
    ):
        return {"state": "ambiguous", "reason": "selected-run-jobs-unavailable"}
    jobs_body = jobs_observation["body"]
    if not isinstance(jobs_body.get("jobs"), list):
        return {"state": "ambiguous", "reason": "invalid-jobs-body"}
    jobs = jobs_body["jobs"]
    required_jobs = [
        job
        for job in jobs
        if isinstance(job, dict) and job.get("name") in REQUIRED_MAIN_QUALIFICATION_JOBS
    ]
    names = [
        job.get("name")
        for job in required_jobs
        if isinstance(job, dict) and isinstance(job.get("name"), str)
    ]
    jobs_match = (
        len(required_jobs) == len(REQUIRED_MAIN_QUALIFICATION_JOBS)
        and len(names) == len(required_jobs)
        and set(names) == REQUIRED_MAIN_QUALIFICATION_JOBS
        and len(names) == len(set(names))
        and all(
            isinstance(job, dict)
            and job.get("head_sha") == commit
            and job.get("status") == "completed"
            and job.get("conclusion") == "success"
            for job in required_jobs
        )
    )
    checks = checks_body["check_runs"]
    suite_checks = [
        check
        for check in checks
        if isinstance(check, dict)
        and isinstance(check.get("check_suite"), dict)
        and check["check_suite"].get("id") == check_suite_id
    ]
    required_checks = [
        check
        for check in suite_checks
        if isinstance(check, dict)
        and check.get("name") in REQUIRED_MAIN_QUALIFICATION_JOBS
    ]
    check_names = [
        check.get("name")
        for check in required_checks
        if isinstance(check, dict) and isinstance(check.get("name"), str)
    ]
    checks_match = (
        len(required_checks) == len(REQUIRED_MAIN_QUALIFICATION_JOBS)
        and len(check_names) == len(required_checks)
        and set(check_names) == REQUIRED_MAIN_QUALIFICATION_JOBS
        and len(check_names) == len(set(check_names))
        and all(
            isinstance(check, dict)
            and check.get("head_sha") == commit
            and check.get("status") == "completed"
            and check.get("conclusion") == "success"
            and isinstance(check.get("app"), dict)
            and check["app"].get("id") == GITHUB_ACTIONS_APP_ID
            for check in required_checks
        )
    )
    if not jobs_match or not checks_match:
        return {
            "state": "mismatch",
            "reason": "required-jobs-or-check-runs-differ",
        }
    return {
        "state": "qualified",
        "run_id": run_id,
        "commit": commit,
        "jobs": sorted(REQUIRED_MAIN_QUALIFICATION_JOBS),
    }


def target_release_plan(
    tag: str,
    commit: str,
    *,
    main_ref: str = "origin/main",
    remote: str = "origin",
    qualification_observation: Mapping[str, object] | None = None,
    root: Path = ROOT,
) -> dict[str, object]:
    """Plan a strict tag-authoritative release without reading mutable metadata."""
    version = tag_version(tag)
    candidate = _require_commit(commit, root)
    if _require_commit("HEAD", root) != candidate:
        raise ReleaseError("Release source is not checked out at the requested commit")
    tags = remote_release_tags(remote, root)
    tagged_commit = tags.get(tag)
    if tagged_commit is None:
        raise ReleaseError(f"Exact remote release tag does not exist: {tag}")
    if tagged_commit != candidate:
        raise ReleaseError(
            f"Remote release tag {tag} peels to {tagged_commit}, not {candidate}"
        )
    if qualification_observation is None:
        main_commit = _require_commit(main_ref, root)
        if not _is_ancestor(candidate, main_commit, root):
            raise ReleaseError(f"Release tag commit is not reachable from {main_ref}")
        qualification_proof: dict[str, object] = {
            "state": "reachable",
            "main_ref": main_ref,
        }
    else:
        qualification_proof = classify_main_qualification(
            candidate, qualification_observation
        )
        if qualification_proof.get("state") != "qualified":
            raise ReleaseError(
                "Recovery requires exact successful CI push-to-main qualification"
            )
    qualification = target_qualification(
        candidate,
        remote=remote,
        root=root,
    )
    expected_version = str(qualification["target_version"])
    if version != expected_version:
        raise ReleaseError(
            f"Release tag {tag} is not the exact {qualification['impact']} bump "
            f"after {qualification['previous_tag']}: v{expected_version}"
        )
    selected = qualification["fragments"]
    if not isinstance(selected, list):
        raise AssertionError("qualification returned invalid fragments")
    title = f"SVC {version}"
    notes = _target_notes(
        version,
        str(qualification["previous_tag"]),
        selected,
    )
    metadata = {
        "schema_version": TARGET_RELEASE_METADATA_SCHEMA_VERSION,
        "tag": tag,
        "version": version,
        "commit": candidate,
        "previous_tag": qualification["previous_tag"],
        "impact": qualification["impact"],
        "fragments": selected,
        "title": title,
        "notes_sha256": hashlib.sha256(notes.encode()).hexdigest(),
    }
    return {
        **qualification,
        "tag": tag,
        "version": version,
        "title": title,
        "notes": notes,
        "notes_path": RELEASE_BUNDLE_NOTES,
        "metadata": metadata,
        "qualification": qualification_proof,
    }


def _expected_hashes(expected: Mapping[str, object]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name, digest in expected.items():
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(digest, str)
            or not SHA256_RE.fullmatch(digest)
        ):
            raise ReleaseError("Expected files must map names to SHA-256 digests")
        hashes[name] = digest
    return hashes


def classify_pypi_state(
    expected: Mapping[str, object],
    observed: object,
) -> dict[str, object]:
    """Classify raw PyPI JSON while preserving missing-only upload information."""
    local = _expected_hashes(expected)
    if not isinstance(observed, dict):
        return {"state": "ambiguous", "reason": "invalid-observation"}
    status = observed.get("http_status")
    if status == 404:
        return {
            "state": "none",
            "present": [],
            "missing": sorted(local),
            "upload": sorted(local),
            "unexpected": [],
            "mismatched": [],
            "readback_required": False,
            "ready_for_github": False,
        }
    if status != 200:
        return {
            "state": "ambiguous",
            "reason": f"unexpected-http-status:{status}",
        }
    body = observed.get("body")
    if not isinstance(body, dict) or not isinstance(body.get("urls"), list):
        return {"state": "ambiguous", "reason": "invalid-pypi-body"}
    remote: dict[str, str] = {}
    duplicate = False
    for item in body["urls"]:
        if not isinstance(item, dict):
            return {"state": "ambiguous", "reason": "invalid-pypi-file"}
        name = item.get("filename")
        digests = item.get("digests")
        digest = digests.get("sha256") if isinstance(digests, dict) else None
        if not isinstance(name, str) or not isinstance(digest, str):
            return {"state": "ambiguous", "reason": "invalid-pypi-file"}
        if name in remote:
            duplicate = True
        remote[name] = digest
    if duplicate:
        return {"state": "ambiguous", "reason": "duplicate-pypi-file"}
    present = sorted(set(local) & set(remote))
    missing = sorted(set(local) - set(remote))
    unexpected = sorted(set(remote) - set(local))
    mismatched = sorted(
        name for name in set(local) & set(remote) if local[name] != remote[name]
    )
    if unexpected or mismatched:
        state = "mismatch"
    elif not remote:
        state = "none"
    elif missing:
        state = "exact-subset"
    else:
        state = "all-exact"
    return {
        "state": state,
        "present": present,
        "missing": missing,
        "upload": missing if state in {"none", "exact-subset"} else [],
        "unexpected": unexpected,
        "mismatched": mismatched,
        "readback_required": state == "exact-subset",
        "ready_for_github": state == "all-exact",
    }


def classify_github_state(
    expected: Mapping[str, object],
    observed: object,
) -> dict[str, object]:
    """Classify one raw GitHub Release and its downloaded asset hashes."""
    if not isinstance(observed, dict):
        return {"state": "ambiguous", "reason": "invalid-observation"}
    status = observed.get("http_status")
    if status == 404:
        assets = expected.get("assets", {})
        if not isinstance(assets, Mapping):
            raise ReleaseError("Expected GitHub assets must be a hash map")
        return {
            "state": "absent",
            "present": [],
            "missing": sorted(assets),
            "upload": sorted(assets),
            "publish": False,
        }
    if status != 200:
        return {
            "state": "ambiguous",
            "reason": f"unexpected-http-status:{status}",
        }
    body = observed.get("body")
    if not isinstance(body, dict):
        return {"state": "ambiguous", "reason": "invalid-github-body"}
    releases = body.get("releases")
    if releases is None:
        releases = [body]
    if not isinstance(releases, list) or len(releases) != 1:
        return {"state": "ambiguous", "reason": "ambiguous-github-release"}
    release = releases[0]
    if not isinstance(release, dict):
        return {"state": "ambiguous", "reason": "invalid-github-release"}
    expected_assets_raw = expected.get("assets")
    if not isinstance(expected_assets_raw, Mapping):
        raise ReleaseError("Expected GitHub assets must be a hash map")
    expected_assets = _expected_hashes(expected_assets_raw)
    observed_assets_raw = observed.get("asset_sha256", {})
    if not isinstance(observed_assets_raw, Mapping):
        return {"state": "ambiguous", "reason": "invalid-github-asset-hashes"}
    observed_assets = dict(observed_assets_raw)
    asset_names = release.get("assets", [])
    if not isinstance(asset_names, list) or not all(
        isinstance(item, dict) and isinstance(item.get("name"), str)
        for item in asset_names
    ):
        return {"state": "ambiguous", "reason": "invalid-github-assets"}
    names = [str(item["name"]) for item in asset_names]
    if len(names) != len(set(names)):
        return {"state": "ambiguous", "reason": "duplicate-github-assets"}
    resolved_tag_commit = observed.get("resolved_tag_commit")
    identity_matches = (
        release.get("tag_name") == expected.get("tag")
        and resolved_tag_commit == expected.get("commit")
        and release.get("name") == expected.get("title")
        and release.get("body") == expected.get("notes")
    )
    present = sorted(set(expected_assets) & set(names))
    missing = sorted(set(expected_assets) - set(names))
    unexpected = sorted(set(names) - set(expected_assets))
    mismatched = sorted(
        name
        for name in present
        if observed_assets.get(name) != expected_assets[name]
    )
    if (
        not identity_matches
        or unexpected
        or mismatched
        or set(observed_assets) != set(names)
    ):
        state = "mismatch"
    elif release.get("draft") is True:
        state = "draft-subset" if missing else "draft-exact"
    elif release.get("draft") is False and missing:
        state = "mismatch"
    elif release.get("immutable") is True:
        state = "published-exact"
    elif expected.get("allow_legacy_mutable") is True:
        state = "legacy-published-exact"
    else:
        state = "mismatch"
    return {
        "state": state,
        "present": present,
        "missing": missing,
        "upload": missing if state == "draft-subset" else [],
        "unexpected": unexpected,
        "mismatched": mismatched,
        "publish": state in {"draft-subset", "draft-exact"},
    }


def _parse_time(value: object, description: str) -> datetime:
    if not isinstance(value, str):
        raise ReleaseError(f"{description} must be an RFC3339 timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ReleaseError(f"{description} must be an RFC3339 timestamp") from error
    if result.tzinfo is None:
        raise ReleaseError(f"{description} must include a timezone")
    return result.astimezone(UTC)


def _workflow_path_matches(value: object, path: str) -> bool:
    return isinstance(value, str) and (
        value == path
        or (
            value.startswith(f"{path}@")
            and bool(value.removeprefix(f"{path}@"))
        )
    )


def classify_bundle_retention(
    expected: Mapping[str, object],
    observed: object,
    *,
    now: str,
    minimum_days: int = 89,
) -> dict[str, object]:
    """Classify the exact named Actions artifact and its bounded availability."""
    if not isinstance(observed, dict):
        return {"state": "ambiguous", "reason": "invalid-observation"}
    run = observed.get("run")
    artifacts = observed.get("artifacts")
    if not isinstance(run, dict) or not isinstance(artifacts, dict):
        return {"state": "ambiguous", "reason": "invalid-artifact-observation"}
    if run.get("http_status") == 404 or artifacts.get("http_status") == 404:
        return {"state": "missing", "reason": "run-or-artifact-not-found"}
    if run.get("http_status") != 200 or artifacts.get("http_status") != 200:
        return {"state": "ambiguous", "reason": "artifact-api-error"}
    expected_run = expected.get("run_id")
    expected_name = expected.get("name")
    expected_commit = expected.get("commit")
    if not isinstance(expected_run, int) or expected_run <= 0:
        raise ReleaseError("Expected artifact run_id must be a positive integer")
    if not isinstance(expected_name, str) or not expected_name:
        raise ReleaseError("Expected artifact name must be non-empty")
    if not isinstance(expected_commit, str) or not COMMIT_RE.fullmatch(
        expected_commit
    ):
        raise ReleaseError("Expected artifact commit must be a full SHA-1")
    run_body = run.get("body")
    artifact_body = artifacts.get("body")
    if (
        not isinstance(run_body, dict)
        or run_body.get("id") != expected_run
        or not _workflow_path_matches(
            run_body.get("path"), ".github/workflows/publish.yml"
        )
        or run_body.get("event") not in {"push", "workflow_dispatch"}
        or run_body.get("head_sha") != expected_commit
        or run_body.get("status") != "completed"
        or run_body.get("conclusion")
        not in {"success", "failure", "cancelled", "timed_out"}
        or not isinstance(artifact_body, dict)
        or not isinstance(artifact_body.get("artifacts"), list)
    ):
        return {"state": "mismatch", "reason": "run-identity-differs"}
    matches = [
        item
        for item in artifact_body["artifacts"]
        if isinstance(item, dict) and item.get("name") == expected_name
    ]
    if len(matches) != 1:
        return {
            "state": "missing" if not matches else "ambiguous",
            "reason": "named-artifact-count",
        }
    artifact = matches[0]
    if artifact.get("expired") is True:
        return {"state": "expired", "artifact_id": artifact.get("id")}
    current = _parse_time(now, "now")
    expiry = _parse_time(artifact.get("expires_at"), "artifact expires_at")
    minimum_expiry = current + timedelta(days=minimum_days)
    if expiry < minimum_expiry:
        return {
            "state": "expired",
            "reason": "retention-window-too-short",
            "artifact_id": artifact.get("id"),
            "expires_at": expiry.isoformat(),
        }
    return {
        "state": "available",
        "artifact_id": artifact.get("id"),
        "run_id": expected_run,
        "name": expected_name,
        "expires_at": expiry.isoformat(),
    }


def _release_body(observed: object) -> dict[str, object] | None:
    if not isinstance(observed, dict) or observed.get("http_status") != 200:
        return None
    body = observed.get("body")
    if not isinstance(body, dict):
        return None
    releases = body.get("releases")
    if releases is None:
        return body
    if (
        isinstance(releases, list)
        and len(releases) == 1
        and isinstance(releases[0], dict)
    ):
        return releases[0]
    return None


def _surface_presence(observed: object, surface: str) -> str:
    if not isinstance(observed, dict):
        return "ambiguous"
    status = observed.get("http_status")
    if status == 404:
        return "none" if surface == "pypi" else "absent"
    if status != 200:
        return "ambiguous"
    if surface == "github":
        return "present" if _release_body(observed) is not None else "ambiguous"
    body = observed.get("body")
    if not isinstance(body, dict) or not isinstance(body.get("urls"), list):
        return "ambiguous"
    return "none" if not body["urls"] else "present"


def _json_asset(
    observed: Mapping[str, object],
    name: str,
) -> tuple[dict[str, object], bytes]:
    raw_assets = observed.get("asset_content")
    if not isinstance(raw_assets, Mapping):
        raise ReleaseError("GitHub observation is missing downloaded asset content")
    raw = raw_assets.get(name)
    if not isinstance(raw, str):
        raise ReleaseError(f"GitHub observation is missing text asset: {name}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ReleaseError(f"GitHub asset is not valid JSON: {name}") from error
    if not isinstance(parsed, dict):
        raise ReleaseError(f"GitHub JSON asset must be an object: {name}")
    return parsed, raw.encode()


def _target_external_expectations(
    observed: Mapping[str, object],
    tag: str,
    commit: str,
    *,
    expected_previous_tag: str | None = None,
    expected_title: str | None = None,
    expected_metadata: object | None = None,
) -> tuple[dict[str, str], dict[str, object]]:
    """Derive expected external state only from a validated durable bundle manifest."""
    manifest, manifest_bytes = _json_asset(observed, RELEASE_BUNDLE_MANIFEST)
    manifest_fields = {
        "schema_version",
        "tag",
        "version",
        "commit",
        "previous_tag",
        "title",
        "notes",
        "plan",
        "checker",
        "distributions",
        "release_assets",
        "files",
        "checksum",
    }
    if set(manifest) != manifest_fields:
        raise ReleaseError("Published target bundle manifest has unknown fields")
    if manifest.get("schema_version") != TARGET_RELEASE_BUNDLE_SCHEMA_VERSION:
        raise ReleaseError("Published target bundle schema version is unsupported")
    if manifest.get("tag") != tag or manifest.get("commit") != commit:
        raise ReleaseError("Published target bundle tag or commit differs")
    version = tag_version(tag)
    previous_tag = manifest.get("previous_tag")
    title = manifest.get("title")
    distributions = manifest.get("distributions")
    release_assets = manifest.get("release_assets")
    files = manifest.get("files")
    checksum = manifest.get("checksum")
    if (
        manifest.get("version") != version
        or not isinstance(previous_tag, str)
        or (expected_previous_tag is not None and previous_tag != expected_previous_tag)
        or (expected_title is not None and title != expected_title)
        or manifest.get("notes") != RELEASE_BUNDLE_NOTES
        or manifest.get("plan") != TARGET_RELEASE_PLAN
        or manifest.get("checker") != RELEASE_BUNDLE_CHECKER
        or not isinstance(title, str)
        or not isinstance(distributions, list)
        or not all(isinstance(path, str) for path in distributions)
        or not isinstance(release_assets, list)
        or not all(isinstance(path, str) for path in release_assets)
        or not isinstance(files, dict)
        or not isinstance(checksum, dict)
    ):
        raise ReleaseError("Published target bundle manifest is malformed")
    previous_version = tag_version(previous_tag)
    if parse_version(previous_version) >= parse_version(version):
        raise ReleaseError("Published target bundle predecessor is not older")
    file_hashes = _expected_hashes(files)
    expected_file_paths = set(distributions) | {
        TARGET_RELEASE_PLAN,
        RELEASE_BUNDLE_METADATA,
        RELEASE_BUNDLE_NOTES,
        RELEASE_BUNDLE_CHECKER,
    }
    if set(file_hashes) != expected_file_paths:
        raise ReleaseError("Published target bundle file map is incomplete")
    expected_release_assets = sorted(
        set(distributions)
        | {
            RELEASE_BUNDLE_METADATA,
            RELEASE_BUNDLE_CHECKSUMS,
            RELEASE_BUNDLE_MANIFEST,
        }
    )
    if release_assets != expected_release_assets:
        raise ReleaseError("Published target bundle release assets differ")
    if (
        len(distributions) != 2
        or sum(
            relative.startswith("python/sustainable_vibe_coding-")
            and relative.endswith(".whl")
            and f"-{version}-" in relative
            for relative in distributions
        )
        != 1
        or f"python/sustainable_vibe_coding-{version}.tar.gz" not in distributions
    ):
        raise ReleaseError("Published target bundle distributions differ")
    if (
        set(checksum) != {"path", "sha256"}
        or checksum.get("path") != RELEASE_BUNDLE_CHECKSUMS
        or not isinstance(checksum.get("sha256"), str)
        or not SHA256_RE.fullmatch(str(checksum["sha256"]))
    ):
        raise ReleaseError("Published target bundle checksum is invalid")
    distribution_hashes = {
        Path(relative).name: file_hashes[relative] for relative in distributions
    }
    if len(distribution_hashes) != len(distributions):
        raise ReleaseError("Published target bundle distribution names are ambiguous")
    metadata, metadata_bytes = _json_asset(observed, RELEASE_BUNDLE_METADATA)
    metadata_digest = file_hashes.get(RELEASE_BUNDLE_METADATA)
    if metadata_digest != hashlib.sha256(metadata_bytes).hexdigest():
        raise ReleaseError("Published target release metadata digest differs")
    metadata_fields = {
        "schema_version",
        "tag",
        "version",
        "commit",
        "previous_tag",
        "impact",
        "fragments",
        "title",
        "notes_sha256",
    }
    if (
        set(metadata) != metadata_fields
        or metadata.get("schema_version") != TARGET_RELEASE_METADATA_SCHEMA_VERSION
        or metadata.get("tag") != tag
        or metadata.get("version") != version
        or metadata.get("commit") != commit
        or metadata.get("previous_tag") != previous_tag
        or metadata.get("title") != title
        or metadata.get("impact") not in IMPACT_ORDER
        or not isinstance(metadata.get("fragments"), list)
        or (expected_metadata is not None and metadata != expected_metadata)
    ):
        raise ReleaseError("Published target release metadata identity differs")
    fragments = metadata["fragments"]
    if not all(
        isinstance(item, dict)
        and item.get("impact") in IMPACT_ORDER
        and isinstance(item.get("path"), str)
        and isinstance(item.get("summary"), str)
        for item in fragments
    ):
        raise ReleaseError("Published target release fragments are malformed")
    impact = (
        max(
            (str(item["impact"]) for item in fragments),
            key=IMPACT_ORDER.__getitem__,
        )
        if fragments
        else "patch"
    )
    if metadata["impact"] != impact or bump(previous_version, impact) != version:
        raise ReleaseError("Published target release Behavioral SemVer differs")
    notes_sha256 = metadata.get("notes_sha256")
    release = _release_body(observed)
    if release is None or not isinstance(release.get("body"), str):
        raise ReleaseError("Published target Release body is unavailable")
    notes = str(release["body"])
    if notes_sha256 != hashlib.sha256(notes.encode()).hexdigest():
        raise ReleaseError("Published target Release notes differ from bundle metadata")
    raw_hashes = observed.get("asset_sha256")
    if not isinstance(raw_hashes, Mapping):
        raise ReleaseError("GitHub observation is missing downloaded asset hashes")
    asset_hashes: dict[str, str] = {}
    for relative in release_assets:
        name = Path(relative).name
        if name in asset_hashes:
            raise ReleaseError("Published target Release asset names are ambiguous")
        if relative in file_hashes:
            digest = file_hashes[relative]
        elif relative == RELEASE_BUNDLE_CHECKSUMS:
            digest = checksum.get("sha256")
        elif relative == RELEASE_BUNDLE_MANIFEST:
            digest = hashlib.sha256(manifest_bytes).hexdigest()
        else:
            raise ReleaseError(f"Published target bundle asset is unbound: {relative}")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise ReleaseError(f"Published target bundle asset digest is invalid: {relative}")
        if raw_hashes.get(name) != digest:
            raise ReleaseError(f"Published target Release asset digest differs: {name}")
        asset_hashes[name] = digest
    return distribution_hashes, {
        "tag": tag,
        "commit": commit,
        "title": title,
        "notes": notes,
        "assets": asset_hashes,
    }


def _legacy_predecessor_complete(observed: Mapping[str, object]) -> bool:
    pypi = classify_pypi_state(CUTOVER_BASELINE_FILES, observed.get("pypi"))
    github = observed.get("github")
    release = _release_body(github)
    if not isinstance(github, dict) or release is None:
        return False
    raw_hashes = github.get("asset_sha256")
    names = release.get("assets")
    if not isinstance(raw_hashes, Mapping) or not isinstance(names, list):
        return False
    published_names = {
        item.get("name") for item in names if isinstance(item, dict)
    }
    return (
        pypi.get("state") == "all-exact"
        and github.get("resolved_tag_commit") == CUTOVER_BASELINE_COMMIT
        and release.get("tag_name") == CUTOVER_BASELINE_TAG
        and release.get("name") == "SVC 11.0.0"
        and release.get("draft") is False
        and all(name in published_names for name in CUTOVER_BASELINE_FILES)
        and all(
            raw_hashes.get(name) == digest
            for name, digest in CUTOVER_BASELINE_FILES.items()
        )
    )


def target_preflight(
    plan: Mapping[str, object],
    state: Mapping[str, object],
) -> dict[str, object]:
    """Reduce raw external observations to one fail-closed pre-build decision."""
    tag = plan.get("tag")
    previous_tag = plan.get("previous_tag")
    if not isinstance(tag, str) or not isinstance(previous_tag, str):
        raise ReleaseError("Target preflight requires a complete target plan")
    candidate = state.get("candidate")
    predecessor = state.get("predecessor")
    if not isinstance(candidate, dict) or not isinstance(predecessor, dict):
        raise ReleaseError("Target preflight requires candidate and predecessor state")
    predecessor_commit = plan.get("previous_commit")
    if previous_tag == CUTOVER_BASELINE_TAG:
        predecessor_complete = _legacy_predecessor_complete(predecessor)
    elif isinstance(predecessor_commit, str):
        try:
            previous_distributions, previous_github_expected = (
                _target_external_expectations(
                    predecessor["github"],
                    previous_tag,
                    predecessor_commit,
                )
            )
            predecessor_pypi = classify_pypi_state(
                previous_distributions, predecessor.get("pypi")
            )
            predecessor_github = classify_github_state(
                previous_github_expected, predecessor.get("github")
            )
            predecessor_complete = (
                predecessor_pypi.get("state") == "all-exact"
                and predecessor_github.get("state") == "published-exact"
            )
        except (KeyError, ReleaseError):
            predecessor_complete = False
    else:
        predecessor_complete = False
    if not predecessor_complete:
        return {
            "decision": "fail",
            "reason": "predecessor-not-exact-complete",
            "pypi_state": "not-exact-complete",
            "github_state": "not-exact-complete",
            "bundle_state": None,
            "missing_distributions": [],
            "missing_assets": [],
        }
    pypi_presence = _surface_presence(candidate.get("pypi"), "pypi")
    github_presence = _surface_presence(candidate.get("github"), "github")
    if pypi_presence == "ambiguous" or github_presence == "ambiguous":
        return {
            "decision": "fail",
            "reason": "candidate-state-ambiguous",
            "pypi_state": pypi_presence,
            "github_state": github_presence,
            "bundle_state": None,
            "missing_distributions": [],
            "missing_assets": [],
        }
    prior_run = state.get("prior_run_id")
    if pypi_presence == "none" and github_presence == "absent" and prior_run is None:
        return {
            "decision": "build",
            "reason": "candidate-surfaces-empty",
            "pypi_state": pypi_presence,
            "github_state": github_presence,
            "bundle_state": None,
            "missing_distributions": [],
            "missing_assets": [],
        }
    if github_presence == "present":
        try:
            candidate_distributions, candidate_github_expected = (
                _target_external_expectations(
                    candidate["github"],
                    tag,
                    str(plan.get("commit")),
                    expected_previous_tag=previous_tag,
                    expected_title=(
                        str(plan["title"])
                        if isinstance(plan.get("title"), str)
                        else None
                    ),
                    expected_metadata=plan.get("metadata"),
                )
            )
            candidate_pypi = classify_pypi_state(
                candidate_distributions, candidate.get("pypi")
            )
            candidate_github = classify_github_state(
                candidate_github_expected, candidate.get("github")
            )
            pypi_state = str(candidate_pypi["state"])
            github_state = str(candidate_github["state"])
        except (KeyError, ReleaseError):
            pypi_state = pypi_presence
            release = _release_body(candidate.get("github"))
            github_observation = candidate.get("github")
            draft_identity_matches = (
                release is not None
                and isinstance(github_observation, dict)
                and release.get("draft") is True
                and release.get("tag_name") == tag
                and github_observation.get("resolved_tag_commit")
                == plan.get("commit")
                and release.get("name") == plan.get("title")
                and release.get("body") == plan.get("notes")
            )
            github_state = (
                "draft-present" if draft_identity_matches else "mismatch"
            )
        if pypi_state == "all-exact" and github_state == "published-exact":
            return {
                "decision": "exact-complete",
                "reason": "candidate-already-complete",
                "pypi_state": pypi_state,
                "github_state": github_state,
                "bundle_state": None,
                "missing_distributions": [],
                "missing_assets": [],
            }
        if github_state == "mismatch" or pypi_state in {"mismatch", "ambiguous"}:
            return {
                "decision": "fail",
                "reason": "candidate-state-mismatch-or-ambiguous",
                "pypi_state": pypi_state,
                "github_state": github_state,
                "bundle_state": None,
                "missing_distributions": [],
                "missing_assets": [],
            }
    else:
        pypi_state = pypi_presence
        github_state = github_presence
    artifact_observed = state.get("artifact")
    now = state.get("now")
    if not isinstance(prior_run, int) or prior_run <= 0 or not isinstance(now, str):
        return {
            "decision": "fail",
            "reason": "incomplete-state-requires-prior-run",
            "pypi_state": pypi_state,
            "github_state": github_state,
            "bundle_state": None,
            "missing_distributions": [],
            "missing_assets": [],
        }
    bundle = classify_bundle_retention(
        {
            "run_id": prior_run,
            "name": f"svc-release-{tag}",
            "commit": plan.get("commit"),
        },
        artifact_observed,
        now=now,
        minimum_days=0,
    )
    return {
        "decision": (
            "requires-bundle" if bundle.get("state") == "available" else "fail"
        ),
        "reason": (
            "resume-from-original-bundle"
            if bundle.get("state") == "available"
            else "original-bundle-unavailable"
        ),
        "pypi_state": pypi_state,
        "github_state": github_state,
        "bundle_state": bundle.get("state"),
        "missing_distributions": [],
        "missing_assets": [],
    }


def _load_json_object(path: Path, description: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseError(f"Could not read {description}: {path}") from error
    if not isinstance(value, dict):
        raise ReleaseError(f"{description} must contain a JSON object")
    return value


def _target_plan_identity(plan: Mapping[str, object]) -> dict[str, object]:
    required = {
        "tag",
        "version",
        "commit",
        "previous_tag",
        "title",
        "notes",
        "notes_path",
        "metadata",
    }
    if not required <= set(plan):
        raise ReleaseError("Target release plan is missing required fields")
    tag = plan["tag"]
    version = plan["version"]
    commit = plan["commit"]
    previous_tag = plan["previous_tag"]
    title = plan["title"]
    notes = plan["notes"]
    if (
        not isinstance(tag, str)
        or tag_version(tag) != version
        or not isinstance(commit, str)
        or not COMMIT_RE.fullmatch(commit)
        or not isinstance(previous_tag, str)
        or not isinstance(title, str)
        or title != f"SVC {version}"
        or not isinstance(notes, str)
        or not notes
        or plan["notes_path"] != RELEASE_BUNDLE_NOTES
        or not isinstance(plan["metadata"], dict)
    ):
        raise ReleaseError("Target release plan identity is invalid")
    return {
        "tag": tag,
        "version": version,
        "commit": commit,
        "previous_tag": previous_tag,
        "title": title,
        "notes": notes,
        "metadata": plan["metadata"],
    }


def _validate_plan_qualification(
    plan: Mapping[str, object],
) -> dict[str, object]:
    qualification = plan.get("qualification")
    commit = plan.get("commit")
    if not isinstance(qualification, dict):
        raise ReleaseError("Target release plan has no qualification proof")
    state = qualification.get("state")
    if state == "reachable":
        if set(qualification) != {"state", "main_ref"} or not isinstance(
            qualification.get("main_ref"), str
        ):
            raise ReleaseError("Target release main-reachability proof is invalid")
    elif state == "qualified":
        if (
            set(qualification) != {"state", "run_id", "commit", "jobs"}
            or not isinstance(qualification.get("run_id"), int)
            or qualification["run_id"] <= 0
            or qualification.get("commit") != commit
            or qualification.get("jobs")
            != sorted(REQUIRED_MAIN_QUALIFICATION_JOBS)
        ):
            raise ReleaseError("Target release durable qualification proof is invalid")
    else:
        raise ReleaseError("Target release qualification proof state is invalid")
    return qualification


def _release_semantic_plan(plan: Mapping[str, object]) -> dict[str, object]:
    """Exclude only the replaceable admission proof from exact plan comparison."""
    _target_plan_identity(plan)
    _validate_plan_qualification(plan)
    return {key: value for key, value in plan.items() if key != "qualification"}


def create_target_release_bundle(
    plan_file: Path,
    dist_dir: Path,
    bundle_dir: Path,
) -> dict[str, object]:
    """Seal target-model distributions using a persisted tag-authoritative plan."""
    plan = _load_json_object(plan_file, "target release plan")
    identity = _target_plan_identity(plan)
    _validate_plan_qualification(plan)
    source_distributions = distribution_files(dist_dir)
    version = str(identity["version"])
    expected_sdist = f"sustainable_vibe_coding-{version}.tar.gz"
    wheel_names = [
        path.name
        for path in source_distributions
        if path.name.endswith(".whl")
        and path.name.startswith(f"sustainable_vibe_coding-{version}-")
    ]
    sdist_names = [
        path.name for path in source_distributions if path.name == expected_sdist
    ]
    if len(source_distributions) != 2 or len(wheel_names) != 1 or len(sdist_names) != 1:
        raise ReleaseError(
            "Target release requires exactly one version-matching wheel and sdist"
        )
    if any(
        distribution_metadata_version(path) != version
        for path in source_distributions
    ):
        raise ReleaseError("Target distribution metadata version differs from its tag")
    if bundle_dir.exists() and any(bundle_dir.iterdir()):
        raise ReleaseError(f"Release bundle directory must be empty: {bundle_dir}")
    bundle_dir.mkdir(parents=True, exist_ok=True)
    python_dir = bundle_dir / "python"
    python_dir.mkdir()
    distribution_paths: list[str] = []
    for source in source_distributions:
        destination = python_dir / source.name
        shutil.copy2(source, destination)
        distribution_paths.append(destination.relative_to(bundle_dir).as_posix())
    (bundle_dir / TARGET_RELEASE_PLAN).write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (bundle_dir / RELEASE_BUNDLE_METADATA).write_text(
        json.dumps(identity["metadata"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (bundle_dir / RELEASE_BUNDLE_NOTES).write_text(
        str(identity["notes"]),
        encoding="utf-8",
    )
    shutil.copy2(Path(__file__).resolve(), bundle_dir / RELEASE_BUNDLE_CHECKER)
    internal = [
        *distribution_paths,
        TARGET_RELEASE_PLAN,
        RELEASE_BUNDLE_METADATA,
        RELEASE_BUNDLE_NOTES,
        RELEASE_BUNDLE_CHECKER,
    ]
    files = {
        relative: sha256_file(_bundle_path(bundle_dir, relative))
        for relative in sorted(internal)
    }
    checksum_path = bundle_dir / RELEASE_BUNDLE_CHECKSUMS
    checksum_path.write_text(
        "".join(f"{files[path]}  {path}\n" for path in sorted(files)),
        encoding="utf-8",
    )
    release_assets = sorted(
        [
            *distribution_paths,
            RELEASE_BUNDLE_METADATA,
            RELEASE_BUNDLE_CHECKSUMS,
            RELEASE_BUNDLE_MANIFEST,
        ]
    )
    manifest = {
        "schema_version": TARGET_RELEASE_BUNDLE_SCHEMA_VERSION,
        **{key: identity[key] for key in ("tag", "version", "commit", "previous_tag", "title")},
        "notes": RELEASE_BUNDLE_NOTES,
        "plan": TARGET_RELEASE_PLAN,
        "checker": RELEASE_BUNDLE_CHECKER,
        "distributions": sorted(distribution_paths),
        "release_assets": release_assets,
        "files": files,
        "checksum": {
            "path": RELEASE_BUNDLE_CHECKSUMS,
            "sha256": sha256_file(checksum_path),
        },
    }
    (bundle_dir / RELEASE_BUNDLE_MANIFEST).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return verify_target_release_bundle(plan_file, bundle_dir)


def verify_target_release_bundle(
    plan_file: Path,
    bundle_dir: Path,
) -> dict[str, object]:
    """Verify target bundle bytes and bind them back to the persisted source plan."""
    plan = _load_json_object(plan_file, "target release plan")
    identity = _target_plan_identity(plan)
    trusted_semantics = _release_semantic_plan(plan)
    manifest = _load_json_object(
        bundle_dir / RELEASE_BUNDLE_MANIFEST,
        "target release bundle manifest",
    )
    expected_fields = {
        "schema_version",
        "tag",
        "version",
        "commit",
        "previous_tag",
        "title",
        "notes",
        "plan",
        "checker",
        "distributions",
        "release_assets",
        "files",
        "checksum",
    }
    if set(manifest) != expected_fields:
        raise ReleaseError("Target release bundle manifest has missing or unknown fields")
    if manifest["schema_version"] != TARGET_RELEASE_BUNDLE_SCHEMA_VERSION:
        raise ReleaseError("Target release bundle schema version is unsupported")
    for key in ("tag", "version", "commit", "previous_tag", "title"):
        if manifest[key] != identity[key]:
            raise ReleaseError(f"Target release bundle {key} differs from its plan")
    if (
        manifest["notes"] != RELEASE_BUNDLE_NOTES
        or manifest["plan"] != TARGET_RELEASE_PLAN
        or manifest["checker"] != RELEASE_BUNDLE_CHECKER
    ):
        raise ReleaseError("Target release bundle internal paths are invalid")
    distributions = _sorted_unique_strings(
        manifest["distributions"], "target distributions"
    )
    version = str(identity["version"])
    if (
        len(distributions) != 2
        or sum(
            relative.startswith("python/sustainable_vibe_coding-")
            and relative.endswith(".whl")
            and f"-{version}-" in relative
            for relative in distributions
        )
        != 1
        or f"python/sustainable_vibe_coding-{version}.tar.gz" not in distributions
    ):
        raise ReleaseError("Target bundle distributions do not match its version")
    assets = _sorted_unique_strings(manifest["release_assets"], "target assets")
    files_raw = manifest["files"]
    if not isinstance(files_raw, dict):
        raise ReleaseError("Target release bundle file map is invalid")
    files = _expected_hashes(files_raw)
    expected_files = set(distributions) | {
        TARGET_RELEASE_PLAN,
        RELEASE_BUNDLE_METADATA,
        RELEASE_BUNDLE_NOTES,
        RELEASE_BUNDLE_CHECKER,
    }
    if set(files) != expected_files:
        raise ReleaseError("Target release bundle file map is incomplete")
    expected_assets = sorted(
        set(distributions)
        | {
            RELEASE_BUNDLE_METADATA,
            RELEASE_BUNDLE_CHECKSUMS,
            RELEASE_BUNDLE_MANIFEST,
        }
    )
    if assets != expected_assets:
        raise ReleaseError("Target release bundle asset set is invalid")
    checksum = manifest["checksum"]
    if not isinstance(checksum, dict) or set(checksum) != {"path", "sha256"}:
        raise ReleaseError("Target release bundle checksum declaration is invalid")
    if (
        checksum["path"] != RELEASE_BUNDLE_CHECKSUMS
        or not isinstance(checksum["sha256"], str)
        or not SHA256_RE.fullmatch(checksum["sha256"])
    ):
        raise ReleaseError("Target release bundle checksum declaration is invalid")
    actual_paths = {
        path.relative_to(bundle_dir).as_posix()
        for path in bundle_dir.rglob("*")
        if path.is_file()
    }
    if actual_paths != expected_files | {
        RELEASE_BUNDLE_CHECKSUMS,
        RELEASE_BUNDLE_MANIFEST,
    }:
        raise ReleaseError("Target release bundle has missing or unexpected files")
    for relative, digest in files.items():
        if sha256_file(_bundle_path(bundle_dir, relative)) != digest:
            raise ReleaseError(f"Target release bundle digest differs: {relative}")
    if any(
        distribution_metadata_version(_bundle_path(bundle_dir, relative)) != version
        for relative in distributions
    ):
        raise ReleaseError("Target bundle distribution metadata version differs")
    expected_checksums = "".join(
        f"{files[path]}  {path}\n" for path in sorted(files)
    )
    checksum_path = bundle_dir / RELEASE_BUNDLE_CHECKSUMS
    if (
        checksum_path.read_text(encoding="utf-8") != expected_checksums
        or sha256_file(checksum_path) != checksum["sha256"]
    ):
        raise ReleaseError("Target release bundle checksum file differs")
    persisted_plan = _load_json_object(
        bundle_dir / TARGET_RELEASE_PLAN, "persisted target release plan"
    )
    if _release_semantic_plan(persisted_plan) != trusted_semantics:
        raise ReleaseError("Persisted target release semantics differ")
    metadata = _load_json_object(
        bundle_dir / RELEASE_BUNDLE_METADATA, "target release metadata"
    )
    if metadata != identity["metadata"]:
        raise ReleaseError("Target release metadata differs from its plan")
    if (bundle_dir / RELEASE_BUNDLE_NOTES).read_text(encoding="utf-8") != identity[
        "notes"
    ]:
        raise ReleaseError("Target release notes differ from its plan")
    return {
        **{key: identity[key] for key in ("tag", "version", "commit", "previous_tag", "title")},
        "notes": RELEASE_BUNDLE_NOTES,
        "distributions": distributions,
        "assets": assets,
        "files": files,
    }


def target_pypi_plan(
    bundle_dir: Path,
    state_file: Path,
) -> dict[str, object]:
    plan_file = bundle_dir / TARGET_RELEASE_PLAN
    bundle = verify_target_release_bundle(plan_file, bundle_dir)
    files = bundle["files"]
    distributions = bundle["distributions"]
    if not isinstance(files, dict) or not isinstance(distributions, list):
        raise AssertionError("target bundle verifier returned an invalid plan")
    expected = {Path(path).name: files[path] for path in distributions}
    if len(expected) != len(distributions):
        raise ReleaseError("Target bundle distribution filenames are not unique")
    observed = _load_json_object(state_file, "raw PyPI state")
    classified = classify_pypi_state(expected, observed)
    missing = classified.get("upload", [])
    relative_by_name = {Path(path).name: path for path in distributions}
    upload = (
        [relative_by_name[name] for name in missing]
        if isinstance(missing, list)
        else []
    )
    return {**classified, "upload": upload}


def stage_target_pypi(
    bundle_dir: Path,
    pypi_plan_file: Path,
    dist_dir: Path,
) -> dict[str, object]:
    plan = _load_json_object(pypi_plan_file, "target PyPI plan")
    upload = plan.get("upload")
    if not isinstance(upload, list) or not all(
        isinstance(path, str) for path in upload
    ):
        raise ReleaseError("Target PyPI plan upload list is invalid")
    if plan.get("state") not in {"none", "exact-subset"}:
        raise ReleaseError("Target PyPI staging requires a missing-file plan")
    if dist_dir.exists() and any(dist_dir.iterdir()):
        raise ReleaseError(f"Target PyPI staging directory must be empty: {dist_dir}")
    dist_dir.mkdir(parents=True, exist_ok=True)
    staged: list[str] = []
    for relative in upload:
        if not relative.startswith("python/"):
            raise ReleaseError(f"Target PyPI upload path is invalid: {relative}")
        source = _bundle_path(bundle_dir, relative)
        destination = dist_dir / source.name
        shutil.copy2(source, destination)
        staged.append(destination.name)
    return {"staged": staged, "count": len(staged)}


def target_github_plan(
    bundle_dir: Path,
    state_file: Path,
) -> dict[str, object]:
    plan_file = bundle_dir / TARGET_RELEASE_PLAN
    bundle = verify_target_release_bundle(plan_file, bundle_dir)
    files = bundle["files"]
    assets = bundle["assets"]
    if not isinstance(files, dict) or not isinstance(assets, list):
        raise AssertionError("target bundle verifier returned an invalid plan")
    asset_hashes: dict[str, str] = {}
    relative_by_name: dict[str, str] = {}
    for relative in assets:
        name = Path(relative).name
        relative_by_name[name] = relative
        if relative == RELEASE_BUNDLE_MANIFEST:
            digest = sha256_file(bundle_dir / RELEASE_BUNDLE_MANIFEST)
        elif relative == RELEASE_BUNDLE_CHECKSUMS:
            digest = sha256_file(bundle_dir / RELEASE_BUNDLE_CHECKSUMS)
        else:
            digest = str(files[relative])
        asset_hashes[name] = digest
    if len(relative_by_name) != len(assets):
        raise ReleaseError("Target bundle GitHub asset filenames are not unique")
    notes = (bundle_dir / RELEASE_BUNDLE_NOTES).read_text(encoding="utf-8")
    expected = {
        "tag": bundle["tag"],
        "commit": bundle["commit"],
        "title": bundle["title"],
        "notes": notes,
        "assets": asset_hashes,
    }
    observed = _load_json_object(state_file, "raw GitHub Release state")
    classified = classify_github_state(expected, observed)
    state = classified["state"]
    actions = {
        "absent": "create",
        "draft-subset": "resume-draft",
        "draft-exact": "resume-draft",
        "published-exact": "verified",
        "mismatch": "fail",
        "ambiguous": "fail",
    }
    upload_names = classified.get("upload", [])
    upload = (
        [relative_by_name[name] for name in upload_names]
        if isinstance(upload_names, list)
        else []
    )
    return {
        **classified,
        "action": actions.get(str(state), "fail"),
        "upload": upload,
    }


def required_option(value: str | Path | None, option: str) -> str | Path:
    if value is None or value == "":
        raise ReleaseError(f"{option} is required")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plan and verify SVC Behavioral SemVer releases."
    )
    parser.add_argument(
        "command",
        choices=(
            "target-qualify",
            "target-plan",
            "target-preflight",
            "target-bundle",
            "target-verify-bundle",
            "target-pypi-plan",
            "target-stage-pypi",
            "target-github-plan",
        ),
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    parser.add_argument("--bundle-dir", type=Path)
    parser.add_argument("--plan-file", type=Path)
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--pypi-plan-file", type=Path)
    parser.add_argument("--qualification-state", type=Path)
    parser.add_argument("--tag")
    parser.add_argument("--commit")
    parser.add_argument("--base")
    parser.add_argument("--main-ref", default="origin/main")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--release-none", action="store_true")
    args = parser.parse_args(argv)
    try:
        commands = {
            "target-qualify": lambda: target_qualification(
                str(required_option(args.commit, "--commit")),
                base=args.base,
                release_none=args.release_none,
                remote=args.remote,
            ),
            "target-plan": lambda: target_release_plan(
                str(required_option(args.tag, "--tag")),
                str(required_option(args.commit, "--commit")),
                main_ref=args.main_ref,
                remote=args.remote,
                qualification_observation=(
                    _load_json_object(
                        args.qualification_state,
                        "main qualification state",
                    )
                    if args.qualification_state is not None
                    else None
                ),
            ),
            "target-preflight": lambda: target_preflight(
                _load_json_object(
                    Path(required_option(args.plan_file, "--plan-file")),
                    "target release plan",
                ),
                _load_json_object(
                    Path(required_option(args.state_file, "--state-file")),
                    "target preflight state",
                ),
            ),
            "target-bundle": lambda: create_target_release_bundle(
                Path(required_option(args.plan_file, "--plan-file")),
                args.dist_dir,
                Path(required_option(args.bundle_dir, "--bundle-dir")),
            ),
            "target-verify-bundle": lambda: verify_target_release_bundle(
                Path(required_option(args.plan_file, "--plan-file")),
                Path(required_option(args.bundle_dir, "--bundle-dir")),
            ),
            "target-pypi-plan": lambda: target_pypi_plan(
                Path(required_option(args.bundle_dir, "--bundle-dir")),
                Path(required_option(args.state_file, "--state-file")),
            ),
            "target-stage-pypi": lambda: stage_target_pypi(
                Path(required_option(args.bundle_dir, "--bundle-dir")),
                Path(required_option(args.pypi_plan_file, "--pypi-plan-file")),
                args.dist_dir,
            ),
            "target-github-plan": lambda: target_github_plan(
                Path(required_option(args.bundle_dir, "--bundle-dir")),
                Path(required_option(args.state_file, "--state-file")),
            ),
        }
        result = commands[args.command]()
    except (OSError, ReleaseError, subprocess.CalledProcessError) as error:
        print(f"release: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=None if args.json else 2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
