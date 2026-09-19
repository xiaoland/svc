from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tools.check_corpus_release import check


def _git(root: Path, *args: str) -> None:
    subprocess.run(("git", *args), cwd=root, check=True, capture_output=True)


def test_layout_migration_compares_corpus_content_by_relative_path(
    tmp_path: Path,
) -> None:
    old = tmp_path / "src"
    old.mkdir()
    (old / "index.md").write_text("# Corpus\n", encoding="utf-8")
    (old / "version.json").write_text(
        '{"schema_version":2,"corpus_version":"15.0.0","releases":[]}',
        encoding="utf-8",
    )
    _git(tmp_path, "init")
    _git(tmp_path, "add", "src")
    _git(
        tmp_path,
        "-c",
        "user.name=SVC Test",
        "-c",
        "user.email=svc@example.invalid",
        "commit",
        "-m",
        "baseline",
    )
    old.rename(tmp_path / "corpus")

    check(tmp_path, "HEAD")

    (tmp_path / "corpus/index.md").write_text("# Changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must advance together"):
        check(tmp_path, "HEAD")
