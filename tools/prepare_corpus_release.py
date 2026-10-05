"""Synchronize the six Skill release metadata fields from pyproject.toml."""

from __future__ import annotations

import argparse
from pathlib import Path

from tools.check_skills import SKILL_NAMES, check
from tools.corpus import read_corpus_version


def _sync(path: Path, version: str) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise ValueError(f"{path}: Skill frontmatter is missing")
    try:
        end = next(
            index
            for index, line in enumerate(lines[1:], 1)
            if line.rstrip("\r\n") == "---"
        )
    except StopIteration as error:
        raise ValueError(f"{path}: Skill frontmatter is unclosed") from error

    metadata = f'metadata: {{"version": "{version}"}}\n'
    for index in range(1, end):
        if lines[index].startswith("metadata: "):
            if lines[index] == metadata:
                return False
            lines[index] = metadata
            path.write_text("".join(lines), encoding="utf-8")
            return True
    lines.insert(end, metadata)
    path.write_text("".join(lines), encoding="utf-8")
    return True


def sync(root: Path) -> list[Path]:
    version = read_corpus_version(root / "pyproject.toml")
    changed = []
    license_path = root / "LICENSE"
    if not license_path.is_file():
        raise ValueError(f"Missing repository license: {license_path}")
    license_bytes = license_path.read_bytes()
    for name in sorted(SKILL_NAMES):
        path = root / "corpus" / name / "SKILL.md"
        if not path.is_file():
            raise ValueError(f"Missing Skill entry: {path}")
        if _sync(path, version):
            changed.append(path)
        skill_license = path.parent / "LICENSE"
        if not skill_license.is_file() or skill_license.read_bytes() != license_bytes:
            skill_license.write_bytes(license_bytes)
            changed.append(skill_license)
    cli_license = root / "cli" / "LICENSE"
    if cli_license.is_file() and cli_license.read_bytes() != license_bytes:
        cli_license.write_bytes(license_bytes)
        changed.append(cli_license)
    check(root / "corpus", license_path, cli_license)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    for path in sync(args.root):
        print(path.relative_to(args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
