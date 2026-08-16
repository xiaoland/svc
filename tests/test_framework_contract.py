from __future__ import annotations

import os
from pathlib import Path

import pytest

from tools.build_monolith import validate_markdown_corpus


def test_document_gate_validates_reachable_and_orphan_documents(tmp_path: Path) -> None:
    root = tmp_path / "src"
    root.mkdir()
    (root / "index.md").write_text("# Home\n\n[Child](child.md)\n", encoding="utf-8")
    (root / "child.md").write_text("# Child\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("# Authoring instructions\n", encoding="utf-8")
    (root / "nested").mkdir()
    (root / "nested" / "AGENTS.md").write_text(
        "# Nested corpus document\n", encoding="utf-8"
    )
    (root / "orphan.md").write_text("# Orphan\n", encoding="utf-8")

    assert validate_markdown_corpus(root) == (
        root / "child.md",
        root / "index.md",
        root / "nested" / "AGENTS.md",
        root / "orphan.md",
    )


@pytest.mark.parametrize("kind", ("symlink", "directory"))
def test_document_gate_rejects_non_regular_root_agents_document(
    tmp_path: Path,
    kind: str,
) -> None:
    root = tmp_path / "src"
    root.mkdir()
    (root / "index.md").write_text("# Home\n", encoding="utf-8")
    agents = root / "AGENTS.md"
    if kind == "symlink":
        target = tmp_path / "authoring.md"
        target.write_text("# Authoring instructions\n", encoding="utf-8")
        try:
            os.symlink(target, agents)
        except OSError as error:
            pytest.skip(f"symlinks unavailable: {error}")
    else:
        agents.mkdir()

    with pytest.raises(ValueError, match="authoring instructions"):
        validate_markdown_corpus(root)


def test_document_gate_reports_invalid_orphan_fixture(tmp_path: Path) -> None:
    root = tmp_path / "src"
    root.mkdir()
    (root / "index.md").write_text("# Home\n", encoding="utf-8")
    (root / "orphan.md").write_text(
        "# Orphan\n\n[Missing](missing.md)\n", encoding="utf-8"
    )

    with pytest.raises(FileNotFoundError, match=r"orphan\.md:.*missing\.md"):
        validate_markdown_corpus(root)
