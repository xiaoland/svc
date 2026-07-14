from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def pdm_build_update_files(context: Any, files: dict[str, Path]) -> None:
    """Project canonical SVC artifacts into the wheel without source duplication."""
    if context.target != "wheel":
        return

    root = Path(context.root)
    manifest_path = root / "src" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files["svc_cli/data/manifest.json"] = manifest_path

    for artifact in manifest["artifacts"]:
        source = artifact.get("source")
        if source:
            files[f"svc_cli/data/{source}"] = root / "src" / source
