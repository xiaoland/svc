from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from tools.release import (
    CUTOVER_BASELINE_COMMIT,
    CUTOVER_BASELINE_FILES,
    ReleaseError,
    classify_bundle_retention,
    classify_github_state,
    classify_main_qualification,
    classify_pypi_state,
    create_target_release_bundle,
    stage_target_pypi,
    target_github_plan,
    target_pypi_plan,
    target_preflight,
    target_qualification,
    target_release_plan,
    verify_target_release_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
QUALIFICATION_JOBS = (
    "Python 3.11",
    "Python 3.14",
    "Quality and architecture",
    "Distribution",
    "Release policy",
)


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.strip()


def target_git_repository(
    root: Path,
    *,
    impact: str = "patch",
    annotated: bool = False,
    migration: str | None = None,
) -> tuple[str, str]:
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Release Test")
    git(root, "config", "user.email", "release-test@example.invalid")
    (root / "changes").mkdir()
    (root / "changes/README.md").write_text("Fragments.\n", encoding="utf-8")
    (root / "src/migrations").mkdir(parents=True)
    (root / "README.md").write_text("baseline\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "cutover baseline")
    baseline = git(root, "rev-parse", "HEAD")
    git(root, "tag", "v11.0.0")
    (root / f"changes/visible-change.{impact}.md").write_text(
        "Make the release path tag-authoritative.\n",
        encoding="utf-8",
    )
    if impact == "major" and migration is not None:
        (root / "src/migrations/visible-change.md").write_text(
            migration,
            encoding="utf-8",
        )
    git(root, "add", ".")
    git(root, "commit", "-m", "add release evidence")
    candidate = git(root, "rev-parse", "HEAD")
    version = {"patch": "11.0.1", "minor": "11.1.0", "major": "12.0.0"}[impact]
    if annotated:
        git(root, "tag", "-a", f"v{version}", "-m", f"SVC {version}")
    else:
        git(root, "tag", f"v{version}")
    remote = root.parent / f"{root.name}-remote.git"
    subprocess.run(
        ["git", "clone", "--bare", str(root), str(remote)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    git(root, "remote", "add", "origin", str(remote))
    return baseline, candidate


def main_qualification_state(
    commit: str,
    *,
    run_id: int = 42,
) -> dict[str, object]:
    jobs = [
        {
            "name": name,
            "head_sha": commit,
            "status": "completed",
            "conclusion": "success",
        }
        for name in QUALIFICATION_JOBS
    ]
    checks = [
        {
            "name": name,
            "head_sha": commit,
            "status": "completed",
            "conclusion": "success",
            "app": {"id": 15368},
            "check_suite": {"id": 99},
        }
        for name in QUALIFICATION_JOBS
    ]
    jobs.append(
        {
            "name": "Unrelated helper",
            "head_sha": commit,
            "status": "completed",
            "conclusion": "success",
        }
    )
    checks.append(
        {
            "name": "Qualify tag and external state",
            "head_sha": commit,
            "status": "completed",
            "conclusion": "success",
            "app": {"id": 15368},
            "check_suite": {"id": 100},
        }
    )
    return {
        "runs": {
            "http_status": 200,
            "body": {
                "total_count": 1,
                "workflow_runs": [
                    {
                        "id": run_id,
                        "check_suite_id": 99,
                        "path": ".github/workflows/ci.yml@main",
                        "event": "push",
                        "head_branch": "main",
                        "head_sha": commit,
                        "status": "completed",
                        "conclusion": "success",
                    }
                ],
            },
        },
        "jobs_by_run": {
            str(run_id): {
                "http_status": 200,
                "body": {"total_count": len(jobs), "jobs": jobs},
            }
        },
        "check_runs": {
            "http_status": 200,
            "body": {"total_count": len(checks), "check_runs": checks},
        },
    }


def write_distributions(directory: Path, version: str) -> None:
    wheel = directory / f"sustainable_vibe_coding-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            f"sustainable_vibe_coding-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.4\nName: sustainable-vibe-coding\nVersion: {version}\n",
        )
    sdist = directory / f"sustainable_vibe_coding-{version}.tar.gz"
    metadata = (
        f"Metadata-Version: 2.4\nName: sustainable-vibe-coding\nVersion: {version}\n"
    ).encode()
    with tarfile.open(sdist, "w:gz") as archive:
        member = tarfile.TarInfo(
            f"sustainable_vibe_coding-{version}/PKG-INFO"
        )
        member.size = len(metadata)
        archive.addfile(member, io.BytesIO(metadata))


@dataclass(frozen=True)
class TargetReleaseFixture:
    root: Path
    candidate: str
    plan: dict[str, object]
    bundle_dir: Path
    bundle: dict[str, object]
    recovery_plan_file: Path


@dataclass(frozen=True)
class TargetReleaseSeed:
    candidate: str
    plan_bytes: bytes
    bundle_bytes: bytes
    bundle_files: tuple[tuple[str, bytes], ...]
    recovery_plan_bytes: bytes


@pytest.fixture(scope="module")
def target_release_seed() -> TargetReleaseSeed:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "work"
        root.mkdir()
        _, candidate = target_git_repository(root)
        plan = target_release_plan(
            "v11.0.1",
            candidate,
            main_ref="main",
            root=root,
        )
        plan_file = root / "plan.json"
        plan_file.write_text(json.dumps(plan), encoding="utf-8")
        dist = root / "dist"
        dist.mkdir()
        write_distributions(dist, "11.0.1")
        bundle_dir = root / "bundle"
        bundle = create_target_release_bundle(plan_file, dist, bundle_dir)
        recovery_plan = json.loads(json.dumps(plan))
        recovery_plan["qualification"] = classify_main_qualification(
            candidate,
            main_qualification_state(candidate),
        )
        bundle_files = tuple(
            (path.relative_to(bundle_dir).as_posix(), path.read_bytes())
            for path in sorted(bundle_dir.rglob("*"))
            if path.is_file()
        )
        return TargetReleaseSeed(
            candidate,
            json.dumps(plan).encode(),
            json.dumps(bundle).encode(),
            bundle_files,
            json.dumps(recovery_plan).encode(),
        )


@pytest.fixture
def target_release_fixture(
    target_release_seed: TargetReleaseSeed,
    tmp_path: Path,
) -> TargetReleaseFixture:
    root = tmp_path / "release-fixture"
    bundle_dir = root / "bundle"
    for relative, content in target_release_seed.bundle_files:
        path = bundle_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    recovery_plan_file = root / "trusted-recovery-plan.json"
    recovery_plan_file.write_bytes(target_release_seed.recovery_plan_bytes)
    return TargetReleaseFixture(
        root,
        target_release_seed.candidate,
        json.loads(target_release_seed.plan_bytes),
        bundle_dir,
        json.loads(target_release_seed.bundle_bytes),
        recovery_plan_file,
    )


def copy_target_bundle(fixture: TargetReleaseFixture, destination: Path) -> Path:
    return Path(shutil.copytree(fixture.bundle_dir, destination))


@pytest.mark.parametrize("annotated", [False, True])
def test_target_plan_derives_exact_tag_range_for_lightweight_and_annotated_tags(
    annotated: bool,
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "work"
        root.mkdir()
        baseline, candidate = target_git_repository(root, annotated=annotated)

        qualification = target_qualification(candidate, root=root)
        assert qualification["previous_tag"] == "v11.0.0"
        assert qualification["target_version"] == "11.0.1"
        assert qualification["pdm_build_scm_version"] == "11.0.1"

        plan = target_release_plan(
            "v11.0.1",
            candidate,
            main_ref="main",
            root=root,
        )
        assert plan["commit"] == candidate
        assert plan["previous_tag"] == "v11.0.0"
        assert plan["impact"] == "patch"
        assert plan["title"] == "SVC 11.0.1"
        assert "Make the release path tag-authoritative." in str(plan["notes"])
        assert git(root, "rev-parse", "v11.0.0") == baseline


def test_target_qualification_enforces_release_none_and_empty_window_patch() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "work"
        root.mkdir()
        baseline, candidate = target_git_repository(root)
        git(root, "tag", "-d", "v11.0.1")
        remote = Path(git(root, "remote", "get-url", "origin"))
        subprocess.run(
            ["git", "--git-dir", str(remote), "tag", "-d", "v11.0.1"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        (root / "changes/visible-change.patch.md").unlink()
        git(root, "add", ".")
        git(root, "commit", "-m", "remove fixture fragment before qualification")
        # This fixture deletion is intentionally before the simulated cutover range.
        empty = git(root, "rev-parse", "HEAD")
        git(root, "push", "origin", "main")

        with pytest.raises(ReleaseError, match="append-only"):
            target_qualification(empty, base=baseline, root=root)

        git(root, "reset", "--hard", baseline)
        (root / "README.md").write_text("internal-only\n", encoding="utf-8")
        git(root, "add", ".")
        git(root, "commit", "-m", "internal-only")
        empty = git(root, "rev-parse", "HEAD")
        git(root, "push", "--force", "origin", "main")
        with pytest.raises(ReleaseError, match="release:none"):
            target_qualification(empty, base=baseline, root=root)
        qualified = target_qualification(
            empty,
            base=baseline,
            release_none=True,
            root=root,
        )
        assert qualified["release"] == "none"
        assert qualified["impact"] == "patch"
        assert qualified["target_version"] == "11.0.1"


def test_recovery_tag_plan_uses_durable_exact_main_evidence_without_main_ref() -> (
    None
):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "work"
        root.mkdir()
        _, candidate = target_git_repository(root)
        evidence = main_qualification_state(candidate)
        classified = classify_main_qualification(candidate, evidence)
        assert classified["state"] == "qualified"
        assert classified["run_id"] == 42

        plan = target_release_plan(
            "v11.0.1",
            candidate,
            main_ref="mutable-main-must-not-be-read",
            qualification_observation=evidence,
            root=root,
        )
        assert plan["qualification"]["state"] == "qualified"
        assert plan["qualification"]["run_id"] == 42

        run = evidence["runs"]["body"]["workflow_runs"][0]
        run["path"] = ".github/workflows/ci.yml"
        assert classify_main_qualification(candidate, evidence)["state"] == "qualified"
        run["path"] = ".github/workflows/ci.yml.evil@main"
        assert classify_main_qualification(candidate, evidence)["state"] != "qualified"
        run["path"] = ".github/workflows/ci.yml@main"
        evidence["check_runs"]["body"]["check_runs"][0]["app"]["id"] = 1
        assert classify_main_qualification(candidate, evidence)["state"] == "mismatch"
        with pytest.raises(ReleaseError, match="push-to-main qualification"):
            target_release_plan(
                "v11.0.1",
                candidate,
                main_ref="mutable-main-must-not-be-read",
                qualification_observation=evidence,
                root=root,
            )


def test_target_plan_rejects_off_main_source_race_and_wrong_bump() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "work"
        root.mkdir()
        _, candidate = target_git_repository(root)
        git(root, "tag", "v11.0.2")
        git(root, "push", "origin", "v11.0.2")
        with pytest.raises(ReleaseError, match="exact patch bump"):
            target_release_plan(
                "v11.0.2",
                candidate,
                main_ref="main",
                root=root,
            )

        (root / "README.md").write_text("later main\n", encoding="utf-8")
        git(root, "add", ".")
        git(root, "commit", "-m", "later main")
        with pytest.raises(ReleaseError, match="not checked out"):
            target_release_plan(
                "v11.0.1",
                candidate,
                main_ref="main",
                root=root,
            )

        git(root, "checkout", "-b", "branch-only", candidate)
        (root / "README.md").write_text("branch only\n", encoding="utf-8")
        git(root, "add", ".")
        git(root, "commit", "-m", "branch only")
        branch_commit = git(root, "rev-parse", "HEAD")
        git(root, "tag", "v11.0.3")
        git(root, "push", "origin", "v11.0.3")
        with pytest.raises(ReleaseError, match="not reachable"):
            target_release_plan(
                "v11.0.3",
                branch_commit,
                main_ref="main",
                root=root,
            )


def test_target_plan_rejects_malformed_and_non_commit_remote_tags() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "work"
        root.mkdir()
        _, candidate = target_git_repository(root)
        with pytest.raises(ReleaseError, match="stable SemVer"):
            target_release_plan(
                "v11.0.1rc1",
                candidate,
                main_ref="main",
                root=root,
            )

        blob = root / "tag-blob"
        blob.write_text("not a commit\n", encoding="utf-8")
        object_id = git(root, "hash-object", "-w", str(blob))
        git(root, "update-ref", "refs/tags/v11.0.2", object_id)
        git(root, "push", "origin", "refs/tags/v11.0.2")
        with pytest.raises(ReleaseError, match="does not peel to a commit"):
            target_release_plan(
                "v11.0.1",
                candidate,
                main_ref="main",
                root=root,
            )


def test_target_major_requires_same_slug_non_empty_migration() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "work"
        root.mkdir()
        target_git_repository(root, impact="major")
        with pytest.raises(ReleaseError, match="missing required path"):
            target_qualification("HEAD", root=root)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "work"
        root.mkdir()
        _, candidate = target_git_repository(
            root,
            impact="major",
            migration="No consumer action applies because no persisted state exists.\n",
        )
        plan = target_release_plan(
            "v12.0.0",
            candidate,
            main_ref="main",
            root=root,
        )
        fragment = plan["fragments"][0]
        assert fragment["migration"] == "src/migrations/visible-change.md"
        assert "Migration: `src/migrations/visible-change.md`" in plan["notes"]


def test_target_planning_is_deterministic_and_does_not_mutate_source() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "work"
        root.mkdir()
        _, candidate = target_git_repository(root)
        before_status = git(root, "status", "--porcelain")
        before_tree = git(root, "rev-parse", "HEAD^{tree}")
        first = target_release_plan(
            "v11.0.1",
            candidate,
            main_ref="main",
            root=root,
        )
        second = target_release_plan(
            "v11.0.1",
            candidate,
            main_ref="main",
            root=root,
        )
        assert first == second
        assert first["metadata"] == second["metadata"]
        assert git(root, "status", "--porcelain") == before_status
        assert git(root, "rev-parse", "HEAD^{tree}") == before_tree


@pytest.mark.parametrize("operation", ("modify", "rename", "delete", "reuse"))
def test_target_fragment_ledger_rejects_append_only_violation(operation: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "work"
        root.mkdir()
        _, candidate = target_git_repository(root)
        path = root / "changes/visible-change.patch.md"
        if operation == "modify":
            path.write_text("Changed after merge.\n", encoding="utf-8")
        elif operation == "rename":
            path.rename(root / "changes/renamed.patch.md")
        else:
            path.unlink()
        git(root, "add", ".")
        git(root, "commit", "-m", operation)
        if operation == "reuse":
            path.write_text("Reused path.\n", encoding="utf-8")
            git(root, "add", ".")
            git(root, "commit", "-m", "reuse path")

        with pytest.raises(ReleaseError, match="append-only|reused"):
            target_qualification("HEAD", root=root)


def test_target_pypi_state_classifier_is_exact_and_fail_closed() -> None:
    hashes = {"a.whl": "a" * 64, "a.tar.gz": "b" * 64}
    assert classify_pypi_state(
        hashes, {"http_status": 404, "body": None}
    )["state"] == "none"
    subset = classify_pypi_state(
        hashes,
        {
            "http_status": 200,
            "body": {
                "urls": [
                    {"filename": "a.whl", "digests": {"sha256": "a" * 64}}
                ]
            },
        },
    )
    assert subset["state"] == "exact-subset"
    assert subset["upload"] == ["a.tar.gz"]
    assert subset["readback_required"]
    assert not subset["ready_for_github"]
    assert classify_pypi_state(
        hashes,
        {
            "http_status": 200,
            "body": {
                "urls": [
                    {"filename": "a.whl", "digests": {"sha256": "0" * 64}}
                ]
            },
        },
    )["state"] == "mismatch"
    all_exact = classify_pypi_state(
        hashes,
        {
            "http_status": 200,
            "body": {
                "urls": [
                    {"filename": name, "digests": {"sha256": digest}}
                    for name, digest in hashes.items()
                ]
            },
        },
    )
    assert all_exact["state"] == "all-exact"
    assert all_exact["ready_for_github"]
    assert not all_exact["upload"]
    unexpected = classify_pypi_state(
        hashes,
        {
            "http_status": 200,
            "body": {
                "urls": [
                    *[
                        {"filename": name, "digests": {"sha256": digest}}
                        for name, digest in hashes.items()
                    ],
                    {"filename": "unknown.whl", "digests": {"sha256": "0" * 64}},
                ]
            },
        },
    )
    assert unexpected["state"] == "mismatch"
    assert unexpected["unexpected"] == ["unknown.whl"]



def test_target_github_state_classifier_is_exact_and_fail_closed() -> None:
    hashes = {"a.whl": "a" * 64, "a.tar.gz": "b" * 64}
    expected = {
        "tag": "v11.0.1",
        "commit": "1" * 40,
        "title": "SVC 11.0.1",
        "notes": "notes",
        "assets": hashes,
    }
    draft = classify_github_state(
        expected,
        {
            "http_status": 200,
            "resolved_tag_commit": "1" * 40,
            "asset_sha256": {"a.whl": "a" * 64},
            "body": {
                "tag_name": "v11.0.1",
                "target_commitish": "main",
                "name": "SVC 11.0.1",
                "body": "notes",
                "draft": True,
                "immutable": False,
                "assets": [{"name": "a.whl"}],
            },
        },
    )
    assert draft["state"] == "draft-subset"
    assert draft["upload"] == ["a.tar.gz"]
    wrong_commit = classify_github_state(
        expected,
        {
            "http_status": 200,
            "resolved_tag_commit": "2" * 40,
            "asset_sha256": hashes,
            "body": {
                "tag_name": "v11.0.1",
                "name": "SVC 11.0.1",
                "body": "notes",
                "draft": False,
                "immutable": True,
                "assets": [{"name": name} for name in hashes],
            },
        },
    )
    assert wrong_commit["state"] == "mismatch"


def bundle_retention_fixture() -> tuple[dict[str, object], dict[str, object]]:
    expected = {
        "run_id": 42,
        "name": "svc-release-v11.0.1",
        "commit": "1" * 40,
    }
    observed = {
        "run": {
            "http_status": 200,
            "body": {
                "id": 42,
                "path": ".github/workflows/publish.yml@main",
                "event": "push",
                "head_sha": "1" * 40,
                "status": "completed",
                "conclusion": "failure",
            },
        },
        "artifacts": {
            "http_status": 200,
            "body": {
                "artifacts": [
                    {
                        "id": 7,
                        "name": "svc-release-v11.0.1",
                        "expired": False,
                        "expires_at": "2027-01-01T00:00:00Z",
                    }
                ]
            },
        },
    }
    return expected, observed


def test_target_bundle_retention_accepts_the_exact_live_artifact() -> None:
    expected, observed = bundle_retention_fixture()
    result = classify_bundle_retention(
        expected,
        observed,
        now="2026-09-01T00:00:00Z",
    )
    assert result["state"] == "available"
    assert result["artifact_id"] == 7


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    (
        ("path", ".github/workflows/ci.yml"),
        ("head_sha", "2" * 40),
        ("event", "pull_request"),
        ("status", "in_progress"),
    ),
)
def test_target_bundle_retention_rejects_wrong_run_identity_or_status(
    field: str,
    wrong_value: object,
) -> None:
    expected, observed = bundle_retention_fixture()
    run = observed["run"]
    assert isinstance(run, dict)
    body = run["body"]
    assert isinstance(body, dict)
    body[field] = wrong_value

    assert classify_bundle_retention(
        expected,
        observed,
        now="2026-09-01T00:00:00Z",
    )["state"] == "mismatch"


def test_target_bundle_retention_enforces_expiry_and_minimum_window() -> None:
    expected, observed = bundle_retention_fixture()
    artifacts = observed["artifacts"]
    assert isinstance(artifacts, dict)
    body = artifacts["body"]
    assert isinstance(body, dict)
    entries = body["artifacts"]
    assert isinstance(entries, list)
    artifact = entries[0]
    assert isinstance(artifact, dict)
    artifact["expired"] = True
    assert classify_bundle_retention(
        expected,
        observed,
        now="2026-09-01T00:00:00Z",
    )["state"] == "expired"

    artifact["expired"] = False
    artifact["expires_at"] = "2026-09-02T00:00:00Z"
    assert classify_bundle_retention(
        expected,
        observed,
        now="2026-09-01T00:00:00Z",
    )["state"] == "expired"
    assert classify_bundle_retention(
        expected,
        observed,
        now="2026-09-01T00:00:00Z",
        minimum_days=0,
    )["state"] == "available"


def test_target_bundle_accepts_original_and_trusted_recovery_plan(
    target_release_fixture: TargetReleaseFixture,
    tmp_path: Path,
) -> None:
    fixture = target_release_fixture
    bundle = fixture.bundle
    assert bundle["notes"] == "RELEASE_NOTES.md"
    assert bundle["title"] == "SVC 11.0.1"
    assert verify_target_release_bundle(
        fixture.bundle_dir / "svc-target-release-plan.json",
        fixture.bundle_dir,
    )["commit"] == fixture.candidate
    assert verify_target_release_bundle(
        fixture.recovery_plan_file,
        fixture.bundle_dir,
    )["commit"] == fixture.candidate

    changed_semantics = json.loads(
        fixture.recovery_plan_file.read_text(encoding="utf-8")
    )
    changed_semantics["notes"] = "untrusted replacement\n"
    changed_plan_file = tmp_path / "changed-plan.json"
    changed_plan_file.write_text(json.dumps(changed_semantics), encoding="utf-8")
    with pytest.raises(ReleaseError, match="semantics differ|notes differ"):
        verify_target_release_bundle(changed_plan_file, fixture.bundle_dir)


def test_target_pypi_plan_stages_only_missing_manifest_bound_distribution(
    target_release_fixture: TargetReleaseFixture,
    tmp_path: Path,
) -> None:
    fixture = target_release_fixture
    files = fixture.bundle["files"]
    assert isinstance(files, dict)
    wheel_name = "sustainable_vibe_coding-11.0.1-py3-none-any.whl"
    wheel_digest = files[f"python/{wheel_name}"]
    pypi_state = tmp_path / "pypi.json"
    pypi_state.write_text(
        json.dumps(
            {
                "http_status": 200,
                "body": {
                    "urls": [
                        {
                            "filename": wheel_name,
                            "digests": {"sha256": wheel_digest},
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    pypi = target_pypi_plan(fixture.bundle_dir, pypi_state)

    assert pypi["state"] == "exact-subset"
    assert pypi["upload"] == [
        "python/sustainable_vibe_coding-11.0.1.tar.gz"
    ]
    pypi_plan_file = tmp_path / "pypi-plan.json"
    pypi_plan_file.write_text(json.dumps(pypi), encoding="utf-8")
    staged = stage_target_pypi(
        fixture.bundle_dir,
        pypi_plan_file,
        tmp_path / "pypi-stage",
    )
    assert staged == {
        "staged": ["sustainable_vibe_coding-11.0.1.tar.gz"],
        "count": 1,
    }


def test_target_github_plan_uses_manifest_bound_assets(
    target_release_fixture: TargetReleaseFixture,
    tmp_path: Path,
) -> None:
    github_state = tmp_path / "github.json"
    github_state.write_text(
        json.dumps({"http_status": 404, "body": None}),
        encoding="utf-8",
    )

    github = target_github_plan(
        target_release_fixture.bundle_dir,
        github_state,
    )

    assert github["action"] == "create"
    assert github["upload"] == target_release_fixture.bundle["assets"]


def test_target_bundle_rejects_tampered_checker_without_executing_it(
    target_release_fixture: TargetReleaseFixture,
    tmp_path: Path,
) -> None:
    bundle_dir = copy_target_bundle(target_release_fixture, tmp_path / "bundle")
    executed = tmp_path / "artifact-checker-executed"
    (bundle_dir / "release-check.py").write_text(
        f"from pathlib import Path\nPath({str(executed)!r}).touch()\n",
        encoding="utf-8",
    )

    with pytest.raises(ReleaseError, match="digest differs"):
        verify_target_release_bundle(
            target_release_fixture.recovery_plan_file,
            bundle_dir,
        )
    assert not executed.exists()


def cutover_baseline_expectation() -> dict[str, object]:
    return {
        "tag": "v11.0.0",
        "commit": CUTOVER_BASELINE_COMMIT,
        "title": "SVC 11.0.0",
        "notes": "baseline",
        "assets": CUTOVER_BASELINE_FILES,
        "allow_legacy_mutable": True,
    }


def exact_external_observation(
    expected: dict[str, object],
    *,
    immutable: bool,
) -> dict[str, object]:
    assets = expected["assets"]
    assert isinstance(assets, dict)
    return {
        "pypi": {
            "http_status": 200,
            "body": {
                "urls": [
                    {"filename": name, "digests": {"sha256": digest}}
                    for name, digest in assets.items()
                ]
            },
        },
        "github": {
            "http_status": 200,
            "resolved_tag_commit": expected["commit"],
            "asset_sha256": assets,
            "body": {
                "tag_name": expected["tag"],
                "target_commitish": "main",
                "name": expected["title"],
                "body": expected["notes"],
                "draft": False,
                "immutable": immutable,
                "assets": [{"name": name} for name in assets],
            },
        },
    }


def preflight_fixture() -> tuple[dict[str, object], dict[str, object]]:
    predecessor_observed = exact_external_observation(
        cutover_baseline_expectation(),
        immutable=False,
    )
    state = {
        "now": "2026-09-01T00:00:00Z",
        "prior_run_id": None,
        "predecessor": {
            **predecessor_observed,
        },
        "candidate": {
            "pypi": {"http_status": 404, "body": None},
            "github": {"http_status": 404, "body": None},
        },
        "artifact": {},
    }
    plan = {
        "tag": "v11.0.1",
        "commit": "2" * 40,
        "previous_tag": "v11.0.0",
        "title": "SVC 11.0.1",
        "notes": "candidate notes\n",
    }
    return plan, state


def recovery_artifact_observation() -> dict[str, object]:
    return {
        "run": {
            "http_status": 200,
            "body": {
                "id": 42,
                "path": ".github/workflows/publish.yml",
                "event": "workflow_dispatch",
                "head_sha": "2" * 40,
                "status": "completed",
                "conclusion": "failure",
            },
        },
        "artifacts": {
            "http_status": 200,
            "body": {
                "artifacts": [
                    {
                        "id": 7,
                        "name": "svc-release-v11.0.1",
                        "expired": False,
                        "expires_at": "2026-09-02T00:00:00Z",
                    }
                ]
            },
        },
    }


def test_target_preflight_builds_for_complete_predecessor_and_absent_candidate() -> None:
    plan, state = preflight_fixture()
    assert target_preflight(plan, state)["decision"] == "build"


def test_target_preflight_fails_for_unbound_candidate_artifact() -> None:
    plan, state = preflight_fixture()
    candidate = state["candidate"]
    assert isinstance(candidate, dict)
    candidate["pypi"] = {
        "http_status": 200,
        "body": {
            "urls": [
                {
                    "filename": "svc-11.0.1.whl",
                    "digests": {"sha256": "c" * 64},
                }
            ]
        },
    }
    assert target_preflight(plan, state)["decision"] == "fail"


def test_target_preflight_requires_the_original_bundle_for_recovery() -> None:
    plan, state = preflight_fixture()
    state["prior_run_id"] = 42
    state["artifact"] = recovery_artifact_observation()
    recovered = target_preflight(plan, state)
    assert recovered["decision"] == "requires-bundle"
    assert recovered["bundle_state"] == "available"


def test_target_preflight_preserves_existing_draft_during_recovery() -> None:
    plan, state = preflight_fixture()
    state["prior_run_id"] = 42
    state["artifact"] = recovery_artifact_observation()
    candidate = state["candidate"]
    assert isinstance(candidate, dict)
    candidate["github"] = {
        "http_status": 200,
        "resolved_tag_commit": "2" * 40,
        "asset_sha256": {},
        "body": {
            "tag_name": "v11.0.1",
            "target_commitish": "main",
            "name": "SVC 11.0.1",
            "body": "candidate notes\n",
            "draft": True,
            "immutable": False,
            "assets": [],
        },
    }
    draft_recovery = target_preflight(plan, state)
    assert draft_recovery["decision"] == "requires-bundle"
    assert draft_recovery["github_state"] == "draft-present"


def test_target_preflight_derives_exact_complete_from_durable_manifest_assets(
    target_release_fixture: TargetReleaseFixture,
) -> None:
    fixture = target_release_fixture
    assets = fixture.bundle["assets"]
    files = fixture.bundle["files"]
    distributions = fixture.bundle["distributions"]
    assert isinstance(assets, list)
    assert isinstance(files, dict)
    assert isinstance(distributions, list)
    asset_sha256 = {
        Path(relative).name: hashlib.sha256(
            (fixture.bundle_dir / relative).read_bytes()
        ).hexdigest()
        for relative in assets
    }
    candidate_observation = {
        "pypi": {
            "http_status": 200,
            "body": {
                "urls": [
                    {
                        "filename": Path(relative).name,
                        "digests": {"sha256": files[relative]},
                    }
                    for relative in distributions
                ]
            },
        },
        "github": {
            "http_status": 200,
            "resolved_tag_commit": fixture.candidate,
            "asset_sha256": asset_sha256,
            "asset_content": {
                "svc-release-manifest.json": (
                    fixture.bundle_dir / "svc-release-manifest.json"
                ).read_text(encoding="utf-8"),
                "svc-release-metadata.json": (
                    fixture.bundle_dir / "svc-release-metadata.json"
                ).read_text(encoding="utf-8"),
            },
            "body": {
                "tag_name": "v11.0.1",
                "target_commitish": "main",
                "name": fixture.plan["title"],
                "body": fixture.plan["notes"],
                "draft": False,
                "immutable": True,
                "assets": [
                    {"name": Path(relative).name} for relative in assets
                ],
            },
        },
    }
    state = {
        "now": "2026-09-01T00:00:00Z",
        "prior_run_id": None,
        "predecessor": exact_external_observation(
            cutover_baseline_expectation(),
            immutable=False,
        ),
        "candidate": candidate_observation,
        "artifact": {},
    }

    exact = target_preflight(fixture.plan, state)

    assert exact["decision"] == "exact-complete"
    assert exact["pypi_state"] == "all-exact"
    assert exact["github_state"] == "published-exact"


def test_sdist_round_trip_preserves_projected_version_and_catalog_without_scm() -> (
    None
):
    version = "12.3.4"
    with tempfile.TemporaryDirectory() as tmp:
        temporary = Path(tmp)
        first_dist = temporary / "tag-build"
        environment = os.environ.copy()
        environment["PDM_BUILD_SCM_VERSION"] = version
        subprocess.run(
            ["pdm", "build", "--no-wheel", "--dest", str(first_dist)],
            cwd=ROOT,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        sdist = next(first_dist.glob("*.tar.gz"))
        unpacked = temporary / "unpacked"
        shutil.unpack_archive(sdist, unpacked)
        source = next(unpacked.iterdir())
        assert not (source / ".git").exists()
        generated_project = (source / "pyproject.toml").read_text(encoding="utf-8")
        assert f'version = "{version}"' in generated_project

        wheel_dist = temporary / "wheel-from-sdist"
        environment.pop("PDM_BUILD_SCM_VERSION", None)
        subprocess.run(
            ["pdm", "build", "--no-sdist", "--dest", str(wheel_dist)],
            cwd=source,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        wheel = next(wheel_dist.glob("*.whl"))
        assert f"-{version}-" in wheel.name
        with zipfile.ZipFile(wheel) as archive:
            catalog = json.loads(archive.read("svc_cli/data/catalog.json"))
            metadata_name = next(
                name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
            )
            metadata = archive.read(metadata_name).decode()
        assert catalog["svc_version"] == version
        assert f"Version: {version}\n" in metadata
