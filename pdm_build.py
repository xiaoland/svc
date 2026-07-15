from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.build_catalog import build_projection


def pdm_build_update_files(context: Any, files: dict[str, Path]) -> None:
    """Project the canonical corpus once into the wheel's read-only runtime data."""
    if context.target != "wheel":
        return
    root = Path(context.root)
    files.update(build_projection(root, root / "build" / "catalog"))
