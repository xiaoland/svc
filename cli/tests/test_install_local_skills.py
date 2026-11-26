"""Verify committed-only Skills activation and reversible host ownership."""

import subprocess
from pathlib import Path

import pytest

from tools.check_skills import SKILL_NAMES
from tools.install_local_skills import install


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(("git", *args), cwd=root, text=True).strip()


def commit(root: Path) -> str:
    git(root, "add", "corpus")
    git(
        root,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.org",
        "-c",
        "commit.gpgsign=false",
        "-c",
        f"core.hooksPath={root / 'no-hooks'}",
        "commit",
        "-qm",
        "Skills fixture",
    )
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def source(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    root.mkdir()
    git(root, "init", "-q")
    for name in SKILL_NAMES:
        entry = root / "corpus" / name / "SKILL.md"
        entry.parent.mkdir(parents=True)
        entry.write_text(
            f'---\nname: {name}\ndescription: "Fixture"\n'
            'metadata: {"version": "1.0.0"}\n---\n'
        )
    commit(root)
    return root


def test_install_updates_and_rolls_back_only_committed_skills(
    source: Path, tmp_path: Path
) -> None:
    store = tmp_path / "store"
    host = tmp_path / "agent" / "skills"
    first = install(source, "HEAD", store, host)
    skill = Path("svc-workflow/SKILL.md")
    initial = (host / skill).read_text()
    entry = source / "corpus" / skill
    updated = initial + "\nCommitted change.\n"
    entry.write_text(updated)
    second = commit(source)
    entry.write_text(initial + "\nUncommitted change.\n")

    assert install(source, "HEAD", store, host) == second
    assert (host / skill).read_text() == updated
    assert (host / skill.parent).readlink() == store / "current" / skill.parent
    assert (store / "current").readlink() == Path("revisions") / second

    assert install(source, first, store, host) == first
    assert (host / skill).read_text() == initial
    assert (store / "current").readlink() == Path("revisions") / first

    (store / "revisions" / second / skill).write_text(initial)
    with pytest.raises(ValueError, match="快照与提交不同"):
        install(source, second, store, host)
    assert (host / skill).read_text() == initial


@pytest.mark.parametrize("legacy", ["svc-workflow", ".svc/svc-workflow.json"])
def test_existing_skill_or_owner_record_blocks_activation(
    source: Path, tmp_path: Path, legacy: str
) -> None:
    host = tmp_path / "host"
    store = tmp_path / "store"
    occupied = host / legacy
    if legacy.endswith(".json"):
        occupied.parent.mkdir(parents=True)
        occupied.write_text("{}")
    else:
        occupied.mkdir(parents=True)

    with pytest.raises(ValueError, match="先备份并移开"):
        install(source, "HEAD", store, host)
    assert not (store / "current").is_symlink()
    assert not any(path.is_symlink() for path in host.iterdir())
    assert occupied.exists()
