from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.build_catalog import build_projection


def format_scm_version(version: Any) -> str:
    """Keep source checkouts on their latest strict stable release projection."""
    return str(version.version)


def pdm_build_update_files(context: Any, files: dict[str, Path]) -> None:
    """Project the canonical corpus once into the wheel's read-only runtime data."""
    if context.target != "wheel":
        return
    output_dir = Path(context.build_dir) / "svc_cli" / "data"
    files.update(build_projection(Path(context.root), output_dir))
