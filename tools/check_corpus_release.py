"""Validate the source-owned Corpus release contract without mutating it."""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import tarfile
import tomllib
from pathlib import Path

from tools.build_corpus_archive import validate_archive
from tools.check_skills import SKILL_NAMES, check as check_skills, skill_metadata
from tools.corpus import read_corpus_version, require_version


def _current_snapshot(corpus_root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(corpus_root).as_posix(): path.read_bytes()
        for path in corpus_root.rglob("*")
        if path.is_file() and path.name != "version.json"
    }


def _git_snapshot(root: Path, ref: str) -> dict[str, bytes]:
    archive = subprocess.run(
        ("git", "archive", "--format=tar", ref, "corpus"),
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
                snapshot[member.name.removeprefix("corpus/")] = source.read()
    return snapshot


def _version_from_old_pyproject(content: bytes) -> str | None:
    try:
        value = tomllib.loads(content.decode("utf-8"))
        return require_version(value["tool"]["svc"]["corpus"]["version"])
    except (
        KeyError,
        TypeError,
        UnicodeDecodeError,
        tomllib.TOMLDecodeError,
        ValueError,
    ):
        return None


def _version_at_ref(root: Path, ref: str) -> str:
    pyproject = subprocess.run(
        ("git", "show", f"{ref}:pyproject.toml"),
        cwd=root,
        check=False,
        capture_output=True,
    )
    if pyproject.returncode == 0:
        version = _version_from_old_pyproject(pyproject.stdout)
        if version is not None:
            return version
    legacy = subprocess.run(
        ("git", "show", f"{ref}:corpus/version.json"),
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout
    value = json.loads(legacy)
    if isinstance(value, dict) and isinstance(value.get("corpus_version"), str):
        return require_version(value["corpus_version"])
    raise ValueError(f"Cannot read Corpus version from {ref}")


def _version_key(version: str) -> tuple[int, int, int]:
    major, minor, patch = map(int, version.split("."))
    return major, minor, patch


def check(
    root: Path, compare_ref: str | None = None, archive: Path | None = None
) -> None:
    version_path = root / "corpus" / "version.json"
    if version_path.exists():
        raise ValueError("corpus/version.json is obsolete; use pyproject.toml")
    version = read_corpus_version(root / "pyproject.toml")
    check_skills(root / "corpus", root / "LICENSE", root / "cli" / "LICENSE")
    for name in sorted(SKILL_NAMES):
        metadata = skill_metadata(root / "corpus" / name / "SKILL.md")
        if metadata["metadata"] != version:
            raise ValueError(
                f"{name}: metadata.version {metadata['metadata']!r} does not match {version!r}"
            )
    if compare_ref is not None:
        old_version = _version_at_ref(root, compare_ref)
        changed = _git_snapshot(root, compare_ref) != _current_snapshot(root / "corpus")
        if changed != (_version_key(version) > _version_key(old_version)):
            raise ValueError(
                "Corpus source and pyproject.toml [tool.svc.corpus].version must advance together: "
                f"{old_version} -> {version}"
            )
    if archive is not None:
        validate_archive(root, archive)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare-ref")
    parser.add_argument("--archive", type=Path)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    check(
        args.root,
        args.compare_ref or os.environ.get("SVC_BASE_REF"),
        args.archive,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
