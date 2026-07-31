from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tools.build_monolith import MonolithBuilder


def test_depth_first_traversal_and_anchor_rewrite() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir) / "src"
        (root / "sections").mkdir(parents=True)
        (root / "assets").mkdir(parents=True)

        (root / "index.md").write_text(
            "# Home\n\n"
            "- [Alpha](sections/alpha.md)\n"
            "- [Beta](sections/beta.md)\n",
            encoding="utf-8",
        )
        (root / "sections" / "alpha.md").write_text(
            "# Alpha\n\n"
            "See [Shared](../assets/shared.md#details).\n",
            encoding="utf-8",
        )
        (root / "sections" / "beta.md").write_text(
            "# Beta\n\n"
            "See [Shared again](../assets/shared.md).\n",
            encoding="utf-8",
        )
        (root / "assets" / "shared.md").write_text(
            "# Shared\n\n"
            "## Details\n\n"
            "Common content.\n",
            encoding="utf-8",
        )

        builder = MonolithBuilder(root)
        content = builder.build(root / "index.md")

        assert [doc.relpath.as_posix() for doc in (builder.documents[path] for path in builder.order)] == [
            "index.md",
            "sections/alpha.md",
            "assets/shared.md",
            "sections/beta.md",
        ]
        assert "[Alpha](#sections-alpha-md__alpha)" in content
        assert "[Shared](#assets-shared-md__details)" in content
        assert content.count("Common content.") == 1


def test_reference_style_links_ignore_code_fences() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir) / "src"
        (root / "docs").mkdir(parents=True)

        (root / "index.md").write_text(
            "# Start\n\n"
            "[Child][child]\n\n"
            "```md\n"
            "[Ignored](docs/ignored.md)\n"
            "```\n\n"
            "[child]: docs/child.md#deep-dive\n",
            encoding="utf-8",
        )
        (root / "docs" / "child.md").write_text(
            "# Child\n\n"
            "## Deep Dive\n\n"
            "Done.\n",
            encoding="utf-8",
        )
        (root / "docs" / "ignored.md").write_text("# Ignored\n", encoding="utf-8")

        builder = MonolithBuilder(root)
        content = builder.build(root / "index.md")

        assert [doc.relpath.as_posix() for doc in (builder.documents[path] for path in builder.order)] == [
            "index.md",
            "docs/child.md",
        ]
        assert "[child]: #docs-child-md__deep-dive" in content
        assert "<!-- Source: docs/ignored.md -->" not in content


@pytest.mark.parametrize(
    ("document", "missing_path"),
    (
        ("# Home\n\n[Missing](sections/missing.md)\n", "sections/missing.md"),
        ("# Home\n\n[Missing][child]\n\n[child]: missing.md\n", "missing.md"),
    ),
    ids=("inline", "reference-style"),
)
def test_missing_local_markdown_target_fails(
    tmp_path: Path,
    document: str,
    missing_path: str,
) -> None:
    root = tmp_path / "src"
    root.mkdir()
    (root / "index.md").write_text(document, encoding="utf-8")

    with pytest.raises(FileNotFoundError, match=missing_path):
        MonolithBuilder(root).build(root / "index.md")


@pytest.mark.parametrize(
    ("document", "child"),
    (
        ("# Home\n\n[Missing fragment](child.md#absent)\n", True),
        ("# Home\n\n[Missing fragment](#absent)\n", False),
    ),
    ids=("cross-document", "same-document"),
)
def test_missing_markdown_fragment_fails(
    tmp_path: Path,
    document: str,
    child: bool,
) -> None:
    root = tmp_path / "src"
    root.mkdir()
    (root / "index.md").write_text(document, encoding="utf-8")
    if child:
        (root / "child.md").write_text("# Child\n", encoding="utf-8")

    with pytest.raises(ValueError, match="#absent"):
        MonolithBuilder(root).build(root / "index.md")


def test_undefined_reference_label_fails() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir) / "src"
        root.mkdir(parents=True)
        (root / "index.md").write_text(
            "# Home\n\n[Missing][undefined-id]\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="undefined-id"):
            MonolithBuilder(root).build(root / "index.md")


def test_local_markdown_target_cannot_escape_root() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir)
        root = workspace / "src"
        root.mkdir(parents=True)
        (workspace / "outside.md").write_text("# Outside\n", encoding="utf-8")
        (root / "index.md").write_text(
            "# Home\n\n[Outside](../outside.md)\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="escapes root"):
            MonolithBuilder(root).build(root / "index.md")


def test_percent_encoded_local_markdown_path_resolves() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir) / "src"
        root.mkdir(parents=True)
        (root / "index.md").write_text(
            "# Home\n\n[Child](my%20child.md)\n",
            encoding="utf-8",
        )
        (root / "my child.md").write_text("# Child\n", encoding="utf-8")

        content = MonolithBuilder(root).build(root / "index.md")

        assert "Generated by tools.build_monolith" in content
        assert "<!-- Source: my child.md -->" in content
