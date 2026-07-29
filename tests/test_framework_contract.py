from __future__ import annotations

from pathlib import Path

import pytest

from tools.build_monolith import MonolithBuilder


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"


def canonical_markdown_files() -> list[Path]:
    return sorted(path for path in SOURCE.rglob("*.md") if path.is_file())


@pytest.mark.parametrize("path", canonical_markdown_files(), ids=lambda path: path.relative_to(SOURCE).as_posix())
def test_all_canonical_markdown_links_resolve(path: Path) -> None:
    MonolithBuilder(SOURCE).build(path)
