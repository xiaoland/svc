from __future__ import annotations

import contextlib
import json
import subprocess
import sys
import tempfile
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.release import (
    ReleaseError,
    bump,
    bump_impact,
    check,
    check_pr,
    create_release_bundle,
    fragments,
    prepare,
    pypi_bundle_plan,
    pypi_plan,
    release_plan,
    tag_plan,
    verify_release_bundle,
    verify_migration,
    verify_tag,
    verify_version_exception,
    verify_prepared,
)


ROOT = Path(__file__).resolve().parents[1]


def release_metadata(
    previous: str = "9.8.0", current: str = "10.0.0", impact: str = "major"
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "previous_version": previous,
        "svc_version": current,
        "behavioral_impact": {
            "level": impact,
            "reasons": ["consumer-visible protocol change"],
            "migration": {
                "status": "not-applicable",
                "reason": "No released consumer state exists.",
            },
        },
    }


def zero_known_adoption_exception() -> dict[str, object]:
    return {
        "kind": "zero-known-adopted-consumers",
        "from_version": "10.0.0",
        "to_version": "10.0.1",
        "one_time": True,
        "owner_assertion": "The product owner confirms zero known adopted consumers.",
        "reason": "The real MAJOR impact is assigned to 10.0.1 once.",
    }


def write_prepared_release(root: Path, previous: str, current: str) -> None:
    (root / "src").mkdir(exist_ok=True)
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "fixture"\nversion = "{current}"\n\n[build-system]\n',
        encoding="utf-8",
    )
    (root / "src/manifest.json").write_text(
        json.dumps(
            release_metadata(previous=previous, current=current, impact="patch"),
            indent=2,
        ),
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        f"## [{current}] - 2026-07-20\n\n"
        f"[{current}]: https://github.com/xiaoland/svc/releases/tag/v{current}\n",
        encoding="utf-8",
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


def prepared_git_repository(root: Path) -> tuple[str, str]:
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Release Test")
    git(root, "config", "user.email", "release-test@example.invalid")
    write_prepared_release(root, "10.0.0", "10.0.1")
    git(root, "add", ".")
    git(root, "commit", "-m", "prepare v10.0.1")
    base = git(root, "rev-parse", "HEAD")
    git(root, "tag", "-a", "v10.0.1", "-m", "SVC 10.0.1")
    write_prepared_release(root, "10.0.1", "10.0.2")
    git(root, "add", ".")
    git(root, "commit", "-m", "prepare v10.0.2")
    return base, git(root, "rev-parse", "HEAD")


def pypi_response(urls: list[dict[str, object]]):
    response = SimpleNamespace(read=lambda: json.dumps({"urls": urls}).encode())
    return contextlib.nullcontext(response)


def test_behavioral_bumps_are_exact() -> None:
    assert bump("10.2.3", "major") == "11.0.0"
    assert bump("10.2.3", "minor") == "10.3.0"
    assert bump("10.2.3", "patch") == "10.2.4"
    assert bump_impact("9.8.0", "10.0.0") == "major"
    with pytest.raises(ReleaseError, match="single Behavioral SemVer bump"):
        bump_impact("10.2.3", "10.3.1")


def test_fragments_reject_unknown_names_and_empty_content() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        changes = root / "changes"
        changes.mkdir()
        (changes / "42.feature.md").write_text("Visible change\n", encoding="utf-8")
        with pytest.raises(ReleaseError, match="Invalid change fragment"):
            fragments(root)
        (changes / "42.feature.md").unlink()
        (changes / "42.patch.md").touch()
        with pytest.raises(ReleaseError, match="Empty change fragment"):
            fragments(root)


def test_feature_pr_does_not_prebump_released_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "changes").mkdir()
        (root / "src").mkdir()
        (root / "changes/42.minor.md").write_text(
            "Add an optional capability.\n", encoding="utf-8"
        )
        (root / "pyproject.toml").write_text(
            '[project]\nname = "fixture"\nversion = "10.0.0"\n\n[build-system]\n',
            encoding="utf-8",
        )
        (root / "src/manifest.json").write_text(
            json.dumps(release_metadata()), encoding="utf-8"
        )
        monkeypatch.setattr("tools.release.git_tags", lambda *_args: ["10.0.0"])
        plan = check(root)
        assert plan["target_version"] == "10.1.0"
        assert plan["impact"] == "minor"


def test_pending_major_requires_a_separate_staged_migration_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "changes").mkdir()
        (root / "src").mkdir()
        (root / "changes/42.major.md").write_text(
            "Change a required obligation.\n", encoding="utf-8"
        )
        (root / "pyproject.toml").write_text(
            '[project]\nname = "fixture"\nversion = "10.0.0"\n\n[build-system]\n',
            encoding="utf-8",
        )
        metadata = release_metadata(previous="9.9.0", current="10.0.0")
        manifest_path = root / "src/manifest.json"
        manifest_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr("tools.release.git_tags", lambda *_args: ["10.0.0"])
        with pytest.raises(
            ReleaseError,
            match="migration guide or explicit non-applicability",
        ):
            check(root)

        metadata["release_policy"] = {
            "migration": {
                "status": "not-applicable",
                "reason": "The protocol has no persisted consumer state yet.",
            }
        }
        manifest_path.write_text(json.dumps(metadata), encoding="utf-8")
        plan = check(root)
        assert plan["target_version"] == "11.0.0"


def test_zero_known_adoption_exception_stages_only_the_exact_major_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "changes").mkdir()
        (root / "src").mkdir()
        (root / "changes/v10-dev-runtime.major.md").write_text(
            "Change the required project protocol.\n", encoding="utf-8"
        )
        (root / "pyproject.toml").write_text(
            '[project]\nname = "fixture"\nversion = "10.0.0"\n\n[build-system]\n',
            encoding="utf-8",
        )
        metadata = release_metadata(previous="9.8.0", current="10.0.0")
        metadata["release_policy"] = {
            "migration": {
                "status": "not-applicable",
                "reason": "The owner confirms no known adopted consumer requires migration.",
            },
            "version_exception": zero_known_adoption_exception(),
        }
        (root / "src/manifest.json").write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr("tools.release.git_tags", lambda *_args: ["10.0.0"])
        plan = check(root)
        assert plan["target_version"] == "10.0.1"
        assert plan["impact"] == "major"


def test_zero_known_adoption_exception_rejects_patch_disguise_and_prebump(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "changes").mkdir()
        (root / "src").mkdir()
        (root / "changes/42.patch.md").write_text("Fix a typo.\n", encoding="utf-8")
        (root / "pyproject.toml").write_text(
            '[project]\nname = "fixture"\nversion = "10.0.0"\n\n[build-system]\n',
            encoding="utf-8",
        )
        metadata = release_metadata(previous="9.8.0", current="10.0.0")
        metadata["release_policy"] = {
            "version_exception": zero_known_adoption_exception()
        }
        manifest_path = root / "src/manifest.json"
        manifest_path.write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr("tools.release.git_tags", lambda *_args: ["10.0.0"])
        with pytest.raises(ReleaseError, match="only for a MAJOR"):
            release_plan(root)

        metadata["svc_version"] = "10.0.1"
        manifest_path.write_text(json.dumps(metadata), encoding="utf-8")
        with pytest.raises(ReleaseError, match="without pre-bumping"):
            release_plan(root)


def test_zero_known_adoption_exception_rejects_missing_wrong_and_reused_values() -> (
    None
):
    exception = zero_known_adoption_exception()
    exception.pop("owner_assertion")
    with pytest.raises(ReleaseError, match="missing or unknown"):
        verify_version_exception("10.0.0", "10.0.1", "major", exception)

    exception = zero_known_adoption_exception()
    exception["to_version"] = "10.0.2"
    with pytest.raises(ReleaseError, match="Only the 10.0.0"):
        verify_version_exception("10.0.0", "10.0.2", "major", exception)

    with pytest.raises(ReleaseError, match="does not match"):
        verify_version_exception(
            "10.0.1", "10.0.2", "major", zero_known_adoption_exception()
        )


def test_prepare_moves_pending_major_policy_into_the_release_and_removes_the_staging_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "src").mkdir()
        (root / "pyproject.toml").write_text(
            '[project]\nname = "fixture"\nversion = "10.0.0"\n\n[build-system]\n',
            encoding="utf-8",
        )
        metadata = release_metadata(previous="9.9.0", current="10.0.0", impact="patch")
        metadata["release_policy"] = {
            "migration": {
                "status": "not-applicable",
                "reason": "This new protocol has no persisted consumer state.",
            }
        }
        manifest_path = root / "src/manifest.json"
        manifest_path.write_text(json.dumps(metadata), encoding="utf-8")
        (root / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
        plan = {
            "base_version": "10.0.0",
            "target_version": "11.0.0",
            "impact": "major",
            "reasons": ["Change a required obligation."],
        }
        commands: list[list[str]] = []

        def record_command(command: list[str], *_args, **_kwargs) -> SimpleNamespace:
            commands.append(command)
            return SimpleNamespace()

        monkeypatch.setattr("tools.release.release_plan", lambda *_args: plan)
        monkeypatch.setattr("tools.release.subprocess.run", record_command)
        monkeypatch.setattr("tools.release.verify_prepared", lambda *_args: {})
        prepare(root)

        prepared = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "release_policy" not in prepared
        assert (
            prepared["behavioral_impact"]["migration"]
            == metadata["release_policy"]["migration"]
        )
        assert ["pdm", "lock", "-d", "-G", ":all"] in commands


def test_prepare_consumes_the_zero_known_adoption_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "src").mkdir()
        (root / "pyproject.toml").write_text(
            '[project]\nname = "fixture"\nversion = "10.0.0"\n\n[build-system]\n',
            encoding="utf-8",
        )
        metadata = release_metadata(previous="9.8.0", current="10.0.0", impact="patch")
        metadata["release_policy"] = {
            "migration": {
                "status": "not-applicable",
                "reason": "The owner confirms no known adopted consumer requires migration.",
            },
            "version_exception": zero_known_adoption_exception(),
        }
        manifest_path = root / "src/manifest.json"
        manifest_path.write_text(json.dumps(metadata), encoding="utf-8")
        (root / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
        plan = {
            "base_version": "10.0.0",
            "target_version": "10.0.1",
            "impact": "major",
            "reasons": ["Change a required obligation."],
        }

        monkeypatch.setattr("tools.release.release_plan", lambda *_args: plan)
        monkeypatch.setattr(
            "tools.release.subprocess.run",
            lambda *_args, **_kwargs: SimpleNamespace(),
        )
        monkeypatch.setattr("tools.release.verify_prepared", lambda *_args: {})
        prepare(root)

        prepared = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "release_policy" not in prepared
        assert (
            prepared["behavioral_impact"]["version_exception"]
            == zero_known_adoption_exception()
        )


def test_major_release_requires_packaged_guide_or_reviewable_non_applicability() -> (
    None
):
    with pytest.raises(ReleaseError, match="packaged migration guide"):
        verify_migration("10.0.0", "11.0.0", "major")
    verify_migration(
        "10.0.0",
        "11.0.0",
        "major",
        {"status": "not-applicable", "reason": "No persisted consumer state."},
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        guide = root / "src/migrations/11.0.0.md"
        guide.parent.mkdir(parents=True)
        guide.write_text("# Migration\n", encoding="utf-8")
        verify_migration(
            "10.0.0",
            "11.0.0",
            "major",
            {"status": "guide", "path": "migrations/11.0.0.md"},
            root,
        )


def test_pypi_retry_accepts_only_identical_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        dist = Path(tmp)
        wheel = dist / "example.whl"
        wheel.write_bytes(b"stable bytes")
        digest = __import__("hashlib").sha256(wheel.read_bytes()).hexdigest()
        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda *_args, **_kwargs: pypi_response(
                [{"filename": wheel.name, "digests": {"sha256": digest}}]
            ),
        )
        result = pypi_plan(dist, ROOT)
        assert not result["needed"]


def test_tag_plan_stays_on_the_prepared_commit_after_later_main_changes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _, candidate = prepared_git_repository(root)
        (root / "changes").mkdir()
        (root / "changes/later.patch.md").write_text(
            "Add a later release fragment.\n", encoding="utf-8"
        )
        git(root, "add", ".")
        git(root, "commit", "-m", "later main change")
        git(root, "checkout", candidate)

        plan = tag_plan(candidate, root)
        assert plan["needed"]
        assert plan["tag"] == "v10.0.2"
        assert plan["commit"] == candidate

        git(root, "tag", "-a", "v10.0.2", "-m", "SVC 10.0.2")
        retry = tag_plan(candidate, root)
        assert not retry["needed"]
        assert retry["reason"] == "tag-already-created"
        assert retry["commit"] == candidate


def test_tag_validation_rejects_wrong_tag_version_or_commit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        base, candidate = prepared_git_repository(root)
        git(root, "tag", "-a", "v10.0.2", "-m", "wrong target", base)
        with pytest.raises(ReleaseError, match="points to"):
            tag_plan(candidate, root)

        git(root, "tag", "-d", "v10.0.2")
        git(root, "tag", "-a", "v10.0.3", "-m", "wrong version", candidate)
        with pytest.raises(
            ReleaseError, match="does not match prepared package version"
        ):
            verify_tag("v10.0.3", candidate, root)

        git(root, "tag", "-d", "v10.0.3")
        git(root, "tag", "-a", "v10.0.2", "-m", "right target", candidate)
        git(root, "checkout", base)
        with pytest.raises(ReleaseError, match="resolves to"):
            verify_tag("v10.0.2", base, root)


def test_release_bundle_binds_artifacts_to_the_tag_and_rejects_tampering() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _, candidate = prepared_git_repository(root)
        git(root, "tag", "-a", "v10.0.2", "-m", "SVC 10.0.2", candidate)
        dist = root / "dist"
        dist.mkdir()
        wheel = dist / "sustainable_vibe_coding-10.0.2-py3-none-any.whl"
        sdist = dist / "sustainable_vibe_coding-10.0.2.tar.gz"
        wheel.write_bytes(b"wheel bytes")
        sdist.write_bytes(b"sdist bytes")
        bundle_dir = root / "bundle"

        bundle = create_release_bundle("v10.0.2", candidate, dist, bundle_dir, root)
        assert bundle["tag"] == "v10.0.2"
        assert bundle["commit"] == candidate
        assert bundle["distributions"] == sorted(
            [f"python/{sdist.name}", f"python/{wheel.name}"]
        )
        assert "svc-release-manifest.json" in bundle["assets"]
        assert verify_release_bundle(bundle_dir, "v10.0.2")["version"] == "10.0.2"
        checker = subprocess.run(
            [
                sys.executable,
                str(bundle_dir / "release-check.py"),
                "verify-bundle",
                "--bundle-dir",
                str(bundle_dir),
                "--tag",
                "v10.0.2",
                "--json",
            ],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        assert json.loads(checker.stdout)["commit"] == candidate

        (bundle_dir / "python" / wheel.name).write_bytes(b"changed wheel bytes")
        with pytest.raises(ReleaseError, match="digest differs"):
            verify_release_bundle(bundle_dir, "v10.0.2")


def test_pypi_bundle_plan_requires_none_or_all_matching_distributions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _, candidate = prepared_git_repository(root)
        git(root, "tag", "-a", "v10.0.2", "-m", "SVC 10.0.2", candidate)
        dist = root / "dist"
        dist.mkdir()
        (dist / "sustainable_vibe_coding-10.0.2-py3-none-any.whl").write_bytes(b"wheel")
        (dist / "sustainable_vibe_coding-10.0.2.tar.gz").write_bytes(b"sdist")
        bundle_dir = root / "bundle"
        bundle = create_release_bundle("v10.0.2", candidate, dist, bundle_dir, root)
        files = bundle["files"]
        distributions = bundle["distributions"]
        assert isinstance(files, dict)
        assert isinstance(distributions, list)
        urls = [
            {
                "filename": Path(relative).name,
                "digests": {"sha256": files[relative]},
            }
            for relative in distributions
        ]

        not_found = urllib.error.HTTPError(
            "https://example.invalid", 404, "missing", None, None
        )

        def missing_response(*_args, **_kwargs):
            raise not_found

        monkeypatch.setattr("urllib.request.urlopen", missing_response)
        missing = pypi_bundle_plan(bundle_dir, "v10.0.2")
        assert missing["needed"]
        assert missing["tag"] == "v10.0.2"

        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda *_args, **_kwargs: pypi_response(urls),
        )
        matching = pypi_bundle_plan(bundle_dir, "v10.0.2")
        assert not matching["needed"]
        assert matching["tag"] == "v10.0.2"

        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda *_args, **_kwargs: pypi_response(urls[:1]),
        )
        with pytest.raises(ReleaseError, match="partial or differs"):
            pypi_bundle_plan(bundle_dir, "v10.0.2")

        mismatched = [*urls]
        mismatched[0] = {
            "filename": urls[0]["filename"],
            "digests": {"sha256": "0" * 64},
        }
        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda *_args, **_kwargs: pypi_response(mismatched),
        )
        with pytest.raises(ReleaseError, match="partial or differs"):
            pypi_bundle_plan(bundle_dir, "v10.0.2")


def test_prepared_release_has_no_fragments_and_has_release_notes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "changes").mkdir()
        (root / "src").mkdir()
        (root / "pyproject.toml").write_text(
            '[project]\nname = "fixture"\nversion = "10.0.0"\n\n[build-system]\n',
            encoding="utf-8",
        )
        (root / "src/manifest.json").write_text(
            json.dumps(release_metadata(), indent=2), encoding="utf-8"
        )
        (root / "CHANGELOG.md").write_text(
            "## [10.0.0] - 2026-07-13\n\n[10.0.0]: https://github.com/xiaoland/svc/releases/tag/v10.0.0\n",
            encoding="utf-8",
        )
        assert verify_prepared(root)["impact"] == "major"

        metadata = release_metadata()
        metadata["release_policy"] = {
            "migration": metadata["behavioral_impact"]["migration"]
        }
        (root / "src/manifest.json").write_text(json.dumps(metadata), encoding="utf-8")
        with pytest.raises(ReleaseError, match="must not retain"):
            verify_prepared(root)


def test_prepared_zero_known_adoption_exception_is_immutable() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "changes").mkdir()
        (root / "src").mkdir()
        (root / "pyproject.toml").write_text(
            '[project]\nname = "fixture"\nversion = "10.0.1"\n\n[build-system]\n',
            encoding="utf-8",
        )
        metadata = release_metadata(previous="10.0.0", current="10.0.1")
        metadata["behavioral_impact"]["version_exception"] = (
            zero_known_adoption_exception()
        )
        manifest_path = root / "src/manifest.json"
        manifest_path.write_text(json.dumps(metadata), encoding="utf-8")
        (root / "CHANGELOG.md").write_text(
            "## [10.0.1] - 2026-07-15\n\n[10.0.1]: https://github.com/xiaoland/svc/releases/tag/v10.0.1\n",
            encoding="utf-8",
        )
        assert verify_prepared(root)["impact"] == "major"

        metadata["behavioral_impact"]["version_exception"]["one_time"] = False
        manifest_path.write_text(json.dumps(metadata), encoding="utf-8")
        with pytest.raises(ReleaseError, match="one_time"):
            verify_prepared(root)


def test_pull_request_requires_fragment_or_release_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "changes").mkdir()
        diff = SimpleNamespace(stdout="README.md\n")
        monkeypatch.setattr(
            "tools.release.subprocess.run", lambda *_args, **_kwargs: diff
        )
        with pytest.raises(ReleaseError, match="requires a change fragment"):
            check_pr("origin/main", False, root)
        result = check_pr("origin/main", True, root)
        assert result["release"] == "none"


def test_prepared_release_pr_does_not_require_a_second_pyproject_version_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "changes").mkdir()
        diff = SimpleNamespace(stdout="CHANGELOG.md\nsrc/manifest.json\n")
        monkeypatch.setattr(
            "tools.release.subprocess.run", lambda *_args, **_kwargs: diff
        )
        monkeypatch.setattr(
            "tools.release.verify_prepared", lambda *_args: {"version": "10.0.0"}
        )
        result = check_pr("origin/main", False, root)
        assert result["version"] == "10.0.0"
