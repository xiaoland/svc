from __future__ import annotations

import os
import subprocess
from datetime import date
from pathlib import Path

import pytest

from tools import release_pr


DAY = date(2026, 11, 26)
RELEASE_BRANCH = "release/1.0.0"
HISTORICAL = b"## [17.0.0] - 2026-11-25\n\n### Added\n\n- Historical note.\n"


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ("git", *args),
        cwd=root,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
        text=True,
    ).strip()


def commit_all(root: Path, message: str) -> str:
    git(root, "add", "--all")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, str]:
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.name", "Release Test")
    git(tmp_path, "config", "user.email", "release@example.com")
    (tmp_path / "cli").mkdir()
    (tmp_path / "macos").mkdir()
    (tmp_path / "pyproject.toml").write_text('[tool.svc.corpus]\nversion = "1.0.0"\n')
    (tmp_path / "cli/pyproject.toml").write_text('[project]\nversion = "1!1.0.0"\n')
    (tmp_path / "macos/VERSION").write_text("1.0.0\n")
    source = Path(release_pr.__file__).resolve().parents[1]
    for name, stream in release_pr.STREAMS.items():
        (tmp_path / stream.changelog).write_bytes(HISTORICAL)
        (tmp_path / stream.towncrier).write_bytes(
            (source / stream.towncrier).read_bytes()
        )
        queue = stream.queue(tmp_path)
        queue.mkdir(parents=True)
        (queue / "42.fixed.md").write_text(f"{name} consumer change.\n")
    return tmp_path, commit_all(
        tmp_path, "Original release history and development fragments"
    )


def test_prepare_and_validate_selected_streams(repo: tuple[Path, str]) -> None:
    pytest.importorskip("towncrier")
    root, base = repo
    git(root, "tag", "corpus-v17.0.0", base)
    git(root, "tag", "cli-v18.3.0", base)
    plan = release_pr.prepare(root, base, ["skills", "cli"], DAY)

    assert plan.releases == {"skills": "1.0.0", "cli": "1.0.0"}
    assert release_pr.check(root, base, pr_branch=RELEASE_BRANCH) == plan
    for name in plan.releases:
        stream = release_pr.STREAMS[name]
        changelog = (root / stream.changelog).read_bytes()
        assert changelog.startswith(b"## [1.0.0] - 2026-11-26")
        assert f"{name} consumer change.".encode() in changelog
        assert changelog.endswith(HISTORICAL)
        assert not release_pr.files_in_queue(root, stream)
    macos = release_pr.STREAMS["macos"]
    assert (root / macos.changelog).read_bytes() == HISTORICAL
    assert len(release_pr.files_in_queue(root, macos)) == 1

    release = commit_all(root, "Prepare release")
    git(root, "tag", "skills-v1.0.0", release)
    git(root, "tag", "svc-cli-v1.0.0", release)
    git(root, "tag", "svc-cli-v2.0.0", release)
    assert release_pr.check(root, base, pr_branch=RELEASE_BRANCH) == plan

    (root / "ordinary.md").write_text("Next ordinary change.\n")
    assert release_pr.check(root, release, pr_branch="feat/document") is None


def test_plan_is_required_on_release_branch_and_changelogs_need_a_plan(
    repo: tuple[Path, str],
) -> None:
    root, base = repo
    with pytest.raises(ValueError, match="only a release"):
        release_pr.check(root, base, pr_branch=RELEASE_BRANCH)
    path = root / "CLI_CHANGELOG.md"
    path.write_bytes(HISTORICAL + b"\nUnexpected ordinary change.\n")
    with pytest.raises(ValueError, match="changes require a prepared cli release"):
        release_pr.check(root, base, pr_branch="feat/ordinary")


def test_release_plan_requires_the_named_branch_and_exact_base(
    repo: tuple[Path, str],
) -> None:
    pytest.importorskip("towncrier")
    root, base = repo
    release_pr.prepare(root, base, ["macos"], DAY)
    later = commit_all(root, "Prepare release")
    with pytest.raises(ValueError, match="only a release"):
        release_pr.check(root, base, pr_branch="feat/ordinary")
    forged = release_pr.Plan(later, DAY, {"macos": "1.0.0"})
    (root / release_pr.PLAN_PATH).write_text(forged.render())
    with pytest.raises(ValueError, match="different main commit"):
        release_pr.check(root, base, pr_branch=RELEASE_BRANCH)


def test_release_rejects_history_edit_and_unconsumed_fragments(
    repo: tuple[Path, str],
) -> None:
    pytest.importorskip("towncrier")
    root, base = repo
    release_pr.prepare(root, base, ["cli"], DAY)
    path = root / "CLI_CHANGELOG.md"
    generated = path.read_bytes()
    path.write_bytes(generated.replace(b"Historical note", b"Edited history"))
    with pytest.raises(ValueError, match="past|published history"):
        release_pr.check(root, base)
    path.write_bytes(generated)
    stream = release_pr.STREAMS["cli"]
    (stream.queue(root) / "43.fixed.md").write_text("Missed fragment.\n")
    with pytest.raises(ValueError, match="consume its Towncrier fragment queue"):
        release_pr.check(root, base)


def test_prepare_refuses_already_tagged_versions_without_partial_edits(
    repo: tuple[Path, str],
) -> None:
    pytest.importorskip("towncrier")
    root, base = repo
    git(root, "tag", "macos-v1.0.0", base)
    with pytest.raises(ValueError, match="macos-v1.0.0 already points"):
        release_pr.prepare(root, base, ["skills", "macos"], DAY)
    assert not git(root, "status", "--porcelain")


@pytest.mark.parametrize(
    ("name", "published", "proposed"),
    [
        ("skills", "skills-v2.0.0", "skills-v1.0.0"),
        ("cli", "svc-cli-v2.0.0", "svc-cli-v1.0.0"),
        ("macos", "macos-v2.0.0", "macos-v1.0.0"),
    ],
)
def test_new_version_must_advance_its_own_namespace(
    repo: tuple[Path, str], name: str, published: str, proposed: str
) -> None:
    root, base = repo
    git(root, "tag", published, base)
    with pytest.raises(
        ValueError, match=f"{proposed} must advance the published release {published}"
    ):
        release_pr.prepare(root, base, [name], DAY)
    assert not git(root, "status", "--porcelain")


def test_plan_rejects_an_ambiguous_duplicate_declaration() -> None:
    plan = release_pr.Plan("a" * 40, DAY, {"cli": "1.0.0"})
    confused = plan.render().replace('"cli": "1.0.0"', '"cli": "2.0.0", "cli": "1.0.0"')
    with pytest.raises(ValueError, match="generate .*release-plan.json"):
        release_pr.Plan.read(confused.encode())


def test_cli_release_requires_the_python_epoch(repo: tuple[Path, str]) -> None:
    root, base = repo
    package = root / "cli/pyproject.toml"
    package.write_text('[project]\nversion = "1.0.0"\n')
    commit_all(root, "Accidentally drop the CLI epoch")
    with pytest.raises(ValueError, match="CLI distribution version must use epoch"):
        release_pr.prepare(root, base, ["cli"], DAY)
