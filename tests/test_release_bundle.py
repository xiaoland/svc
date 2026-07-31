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
    create_target_release_bundle,
    stage_target_pypi,
    target_github_plan,
    target_preflight,
    target_pypi_plan,
    target_release_plan,
    verify_target_release_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
DURABLE_QUALIFICATION_JOBS = (
    "Distribution",
    "Python 3.11",
    "Python 3.14",
    "Quality and architecture",
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


def target_bundle_seed_repository(root: Path) -> str:
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Release Test")
    git(root, "config", "user.email", "release-test@example.invalid")
    (root / "changes").mkdir()
    (root / "changes/README.md").write_text("Fragments.\n", encoding="utf-8")
    (root / "src/migrations").mkdir(parents=True)
    (root / "README.md").write_text("baseline\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "cutover baseline")
    git(root, "tag", "v11.0.0")
    (root / "changes/visible-change.patch.md").write_text(
        "Make the release path tag-authoritative.\n",
        encoding="utf-8",
    )
    git(root, "add", ".")
    git(root, "commit", "-m", "add release evidence")
    candidate = git(root, "rev-parse", "HEAD")
    git(root, "tag", "v11.0.1")
    remote = root.parent / f"{root.name}-remote.git"
    subprocess.run(
        ["git", "clone", "--bare", str(root), str(remote)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    git(root, "remote", "add", "origin", str(remote))
    return candidate


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
        candidate = target_bundle_seed_repository(root)
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
        recovery_plan["qualification"] = {
            "state": "qualified",
            "run_id": 42,
            "commit": candidate,
            "jobs": list(DURABLE_QUALIFICATION_JOBS),
        }
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
        candidate=target_release_seed.candidate,
        plan=json.loads(target_release_seed.plan_bytes),
        bundle_dir=bundle_dir,
        bundle=json.loads(target_release_seed.bundle_bytes),
        recovery_plan_file=recovery_plan_file,
    )


def copy_target_bundle(fixture: TargetReleaseFixture, destination: Path) -> Path:
    return Path(shutil.copytree(fixture.bundle_dir, destination))


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


def cutover_predecessor_observation() -> dict[str, object]:
    assets = CUTOVER_BASELINE_FILES
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
            "resolved_tag_commit": CUTOVER_BASELINE_COMMIT,
            "asset_sha256": assets,
            "body": {
                "tag_name": "v11.0.0",
                "target_commitish": "main",
                "name": "SVC 11.0.0",
                "body": "baseline",
                "draft": False,
                "immutable": False,
                "assets": [{"name": name} for name in assets],
            },
        },
    }


def build_preflight_case() -> tuple[dict[str, object], dict[str, object]]:
    plan = {
        "tag": "v11.0.1",
        "commit": "2" * 40,
        "previous_tag": "v11.0.0",
        "title": "SVC 11.0.1",
        "notes": "candidate notes\n",
    }
    state = {
        "now": "2026-09-01T00:00:00Z",
        "prior_run_id": None,
        "predecessor": cutover_predecessor_observation(),
        "candidate": {
            "pypi": {"http_status": 404, "body": None},
            "github": {"http_status": 404, "body": None},
        },
        "artifact": {},
    }
    return plan, state


def failed_publish_bundle_observation() -> dict[str, object]:
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
    plan, state = build_preflight_case()
    assert target_preflight(plan, state)["decision"] == "build"


def test_target_preflight_fails_for_unbound_candidate_artifact() -> None:
    plan, state = build_preflight_case()
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
    plan, state = build_preflight_case()
    state["prior_run_id"] = 42
    state["artifact"] = failed_publish_bundle_observation()
    recovered = target_preflight(plan, state)
    assert recovered["decision"] == "requires-bundle"
    assert recovered["bundle_state"] == "available"


def test_target_preflight_preserves_existing_draft_during_recovery() -> None:
    plan, state = build_preflight_case()
    state["prior_run_id"] = 42
    state["artifact"] = failed_publish_bundle_observation()
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
        "predecessor": cutover_predecessor_observation(),
        "candidate": candidate_observation,
        "artifact": {},
    }

    exact = target_preflight(fixture.plan, state)

    assert exact["decision"] == "exact-complete"
    assert exact["pypi_state"] == "all-exact"
    assert exact["github_state"] == "published-exact"


def test_sdist_round_trip_preserves_projected_version_and_catalog_without_scm(
    tmp_path: Path,
) -> None:
    version = "12.3.4"
    first_dist = tmp_path / "tag-build"
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
    unpacked = tmp_path / "unpacked"
    shutil.unpack_archive(sdist, unpacked)
    source = next(unpacked.iterdir())
    assert not (source / ".git").exists()
    generated_project = (source / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{version}"' in generated_project

    wheel_dist = tmp_path / "wheel-from-sdist"
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
