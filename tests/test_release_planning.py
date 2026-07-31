from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest

from tools.release import (
    ReleaseError,
    classify_main_qualification,
    target_qualification,
    target_release_plan,
)


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


@pytest.mark.parametrize(
    "annotated",
    (
        pytest.param(False, id="lightweight"),
        pytest.param(True, id="annotated"),
    ),
)
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


def test_recovery_tag_plan_uses_durable_exact_main_evidence_without_main_ref() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "work"
        root.mkdir()
        _, candidate = target_git_repository(root)
        evidence = main_qualification_state(candidate)
        classified = classify_main_qualification(candidate, evidence)
        expected_qualification = {
            "state": "qualified",
            "run_id": 42,
            "commit": candidate,
            "jobs": sorted(QUALIFICATION_JOBS),
        }
        assert classified == expected_qualification

        plan = target_release_plan(
            "v11.0.1",
            candidate,
            main_ref="mutable-main-must-not-be-read",
            qualification_observation=evidence,
            root=root,
        )
        assert plan["qualification"] == classified

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
        target_git_repository(root)
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
