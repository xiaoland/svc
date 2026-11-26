"""Exercise the release checker and builder against isolated Git history."""

import json
import subprocess
from pathlib import Path

import pytest

from test_skills import PUBLIC_SKILLS
from tools.build_corpus_archive import build
from tools.check_corpus_release import check
from tools.prepare_corpus_release import sync


def test_release_line_reset_and_immutability(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()

    def git(*args: str) -> str:
        return subprocess.run(
            ("git", *args), cwd=root, check=True, capture_output=True, text=True
        ).stdout.strip()

    def commit() -> str:
        git("add", ".")
        git("-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Release fixture")
        return git("rev-parse", "HEAD")

    def prepare(version: str, legacy: bool = False) -> None:
        config = root / "pyproject.toml"
        content = f'[tool.svc.corpus]\nversion = "{version}"\n'
        config.write_text(content + 'tag-prefix = "skills-v"\n')
        sync(root)
        if legacy:
            config.write_text(content)

    git("init", "--quiet")
    git("config", "user.name", "Release fixture")
    git("config", "user.email", "fixture@example.org")
    git("config", "core.hooksPath", str(root / "disabled-hooks"))
    (root / "cli").mkdir()
    for path in (root / "LICENSE", root / "cli/LICENSE"):
        path.write_text("MIT License\n")
    for name in PUBLIC_SKILLS:
        directory = root / "corpus" / name
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text(
            f'---\nname: {name}\ndescription: "Fixture"\n---\n'
        )
    prepare("17.0.0", legacy=True)
    commit()
    legacy_tag = "corpus-v17.0.0"
    git("tag", legacy_tag)

    prepare("1.0.0")
    check(root, compare_ref=legacy_tag)
    revision = commit()
    out = tmp_path / "assets"
    assert len(build(root, out, revision)) == 16
    new_tag = "skills-v1.0.0"
    git("tag", new_tag)
    check(root, artifacts=out)
    catalog = json.loads((out / "svc-skills-1.0.0.json").read_bytes())
    assert (catalog["schema_version"], catalog["tag"], catalog["revision"]) == (
        3,
        new_tag,
        revision,
    )
    assert {entry["name"] for entry in catalog["skills"]} == set(PUBLIC_SKILLS)

    entry = root / "corpus/svc-workflow/SKILL.md"
    content = entry.read_bytes()
    entry.write_bytes(content + b"\nChanged after release.\n")
    with pytest.raises(ValueError, match="Published Corpus release is immutable"):
        check(root)
    entry.write_bytes(content)

    prepare("1.1.0")
    check(root, compare_ref=new_tag)
    newer = commit()
    git("switch", "--detach", new_tag)
    with pytest.raises(ValueError, match="Corpus version must not regress"):
        check(root, compare_ref=newer)
