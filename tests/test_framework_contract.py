from __future__ import annotations

from pathlib import Path

import pytest

from tools.build_monolith import validate_markdown_corpus


def test_document_gate_validates_reachable_and_orphan_documents(tmp_path: Path) -> None:
    root = tmp_path / "src"
    root.mkdir()
    (root / "index.md").write_text("# Home\n\n[Child](child.md)\n", encoding="utf-8")
    (root / "child.md").write_text("# Child\n", encoding="utf-8")
    (root / "orphan.md").write_text("# Orphan\n", encoding="utf-8")

    assert validate_markdown_corpus(root) == (
        root / "child.md",
        root / "index.md",
        root / "orphan.md",
    )


def test_document_gate_reports_invalid_orphan_fixture(tmp_path: Path) -> None:
    root = tmp_path / "src"
    root.mkdir()
    (root / "index.md").write_text("# Home\n", encoding="utf-8")
    (root / "orphan.md").write_text(
        "# Orphan\n\n[Missing](missing.md)\n", encoding="utf-8"
    )

    with pytest.raises(FileNotFoundError, match=r"orphan\.md:.*missing\.md"):
        validate_markdown_corpus(root)
