"""Validate the hand-authored Corpus release index and migration guides."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from svc_cli.catalog import parse_version_index


def _version(raw: bytes) -> str:
    value = json.loads(raw)
    if value.get("schema_version") == 1:
        releases = value.get("releases")
        if isinstance(releases, list) and releases and isinstance(releases[-1], dict):
            version = releases[-1].get("version")
            if isinstance(version, str):
                return version
    return parse_version_index(raw).corpus_version


def check(root: Path, compare_ref: str | None = None) -> None:
    index = parse_version_index((root / "src/version.json").read_bytes())
    for release in index.releases:
        for relative in release.migration.paths:
            if not (root / "src" / relative).is_file():
                raise ValueError(f"Corpus migration guide does not exist: {relative}")
    if compare_ref is None:
        return
    previous = subprocess.run(
        ("git", "show", f"{compare_ref}:src/version.json"),
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout
    old_version = _version(previous)
    changed = subprocess.run(
        (
            "git",
            "diff",
            "--quiet",
            compare_ref,
            "--",
            "src",
            ":(exclude)src/version.json",
        ),
        cwd=root,
        check=False,
    ).returncode
    if changed not in {0, 1}:
        raise ValueError("git diff failed while checking the Corpus release")
    if (changed == 1) != (old_version != index.corpus_version):
        raise ValueError(
            "Corpus source and src/version.json must advance together: "
            f"{old_version} -> {index.corpus_version}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare-ref")
    args = parser.parse_args()
    check(
        Path(__file__).resolve().parents[1],
        args.compare_ref or os.environ.get("SVC_BASE_REF"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
