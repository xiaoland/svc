"""Validate the hand-authored Corpus release index and migration guides."""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import tarfile
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


def _current_snapshot(corpus_root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(corpus_root).as_posix(): path.read_bytes()
        for path in corpus_root.rglob("*")
        if path.is_file() and path.name != "version.json"
    }


def _git_snapshot(root: Path, ref: str, corpus_root: str) -> dict[str, bytes]:
    archive = subprocess.run(
        ("git", "archive", "--format=tar", ref, corpus_root),
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout
    snapshot: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        for member in stream.getmembers():
            if not member.isfile() or member.name.endswith("/version.json"):
                continue
            source = stream.extractfile(member)
            if source is not None:
                snapshot[member.name.removeprefix(f"{corpus_root}/")] = source.read()
    return snapshot


def check(root: Path, compare_ref: str | None = None) -> None:
    corpus_root = root / "corpus"
    index = parse_version_index((corpus_root / "version.json").read_bytes())
    for release in index.releases:
        for relative in release.migration.paths:
            if not (corpus_root / relative).is_file():
                raise ValueError(f"Corpus migration guide does not exist: {relative}")
    if compare_ref is None:
        return
    previous_root = "corpus"
    previous = subprocess.run(
        ("git", "show", f"{compare_ref}:{previous_root}/version.json"),
        cwd=root,
        check=False,
        capture_output=True,
    )
    if previous.returncode != 0:
        previous_root = "src"
        previous = subprocess.run(
            ("git", "show", f"{compare_ref}:{previous_root}/version.json"),
            cwd=root,
            check=True,
            capture_output=True,
        )
    old_version = _version(previous.stdout)
    changed = _git_snapshot(root, compare_ref, previous_root) != _current_snapshot(
        corpus_root
    )
    if changed != (old_version != index.corpus_version):
        raise ValueError(
            "Corpus source and corpus/version.json must advance together: "
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
