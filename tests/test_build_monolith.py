from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.build_monolith import MonolithBuilder


class BuildMonolithTests(unittest.TestCase):
    def test_depth_first_traversal_and_anchor_rewrite(self) -> None:
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

            self.assertEqual(
                [doc.relpath.as_posix() for doc in (builder.documents[path] for path in builder.order)],
                ["index.md", "sections/alpha.md", "assets/shared.md", "sections/beta.md"],
            )
            self.assertIn("[Alpha](#sections-alpha-md__alpha)", content)
            self.assertIn("[Shared](#assets-shared-md__details)", content)
            self.assertEqual(content.count("Common content."), 1)

    def test_reference_style_links_ignore_code_fences(self) -> None:
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

            self.assertEqual(
                [doc.relpath.as_posix() for doc in (builder.documents[path] for path in builder.order)],
                ["index.md", "docs/child.md"],
            )
            self.assertIn("[child]: #docs-child-md__deep-dive", content)
            self.assertNotIn("<!-- Source: docs/ignored.md -->", content)

    def test_missing_local_markdown_target_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "src"
            root.mkdir(parents=True)
            (root / "index.md").write_text(
                "# Home\n\n[Missing](sections/missing.md)\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(FileNotFoundError, "sections/missing.md"):
                MonolithBuilder(root).build(root / "index.md")

    def test_missing_local_markdown_fragment_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "src"
            root.mkdir(parents=True)
            (root / "index.md").write_text(
                "# Home\n\n[Missing fragment](child.md#absent)\n",
                encoding="utf-8",
            )
            (root / "child.md").write_text("# Child\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "#absent"):
                MonolithBuilder(root).build(root / "index.md")

    def test_same_document_missing_fragment_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "src"
            root.mkdir(parents=True)
            (root / "index.md").write_text(
                "# Home\n\n[Missing fragment](#absent)\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "#absent"):
                MonolithBuilder(root).build(root / "index.md")

    def test_reference_style_missing_target_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "src"
            root.mkdir(parents=True)
            (root / "index.md").write_text(
                "# Home\n\n[Missing][child]\n\n[child]: missing.md\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(FileNotFoundError, "missing.md"):
                MonolithBuilder(root).build(root / "index.md")

    def test_undefined_reference_label_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "src"
            root.mkdir(parents=True)
            (root / "index.md").write_text(
                "# Home\n\n[Missing][undefined-id]\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "undefined-id"):
                MonolithBuilder(root).build(root / "index.md")

    def test_local_markdown_target_cannot_escape_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            root = workspace / "src"
            root.mkdir(parents=True)
            (workspace / "outside.md").write_text("# Outside\n", encoding="utf-8")
            (root / "index.md").write_text(
                "# Home\n\n[Outside](../outside.md)\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "escapes root"):
                MonolithBuilder(root).build(root / "index.md")

    def test_percent_encoded_local_markdown_path_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "src"
            root.mkdir(parents=True)
            (root / "index.md").write_text(
                "# Home\n\n[Child](my%20child.md)\n",
                encoding="utf-8",
            )
            (root / "my child.md").write_text("# Child\n", encoding="utf-8")

            content = MonolithBuilder(root).build(root / "index.md")

            self.assertIn("Generated by tools.build_monolith", content)
            self.assertIn("<!-- Source: my child.md -->", content)


if __name__ == "__main__":
    unittest.main()
