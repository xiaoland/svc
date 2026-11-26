"""Extract and validate one prepared Towncrier release section."""

from __future__ import annotations

import argparse
from datetime import date
import re
from pathlib import Path


HEADING = re.compile(r"^## \[([^]]+)](?: - .+)?$")


def release_section(changelog: str, version: str) -> str:
    lines = changelog.splitlines()
    releases = [index for index, line in enumerate(lines) if HEADING.match(line)]
    if not releases:
        raise ValueError("changelog has no release section")
    first = releases[0]
    match = HEADING.match(lines[first])
    if match is None or match.group(1) != version:
        actual = match.group(1) if match is not None else "missing"
        raise ValueError(f"latest changelog version is {actual}, expected {version}")
    end = releases[1] if len(releases) > 1 else len(lines)
    return "\n".join(lines[first:end]).rstrip() + "\n"


def publication_date(section: str) -> date | None:
    header = section.splitlines()[0]
    match = re.fullmatch(r"## \[[^]]+] - (\d{4}-\d{2}-\d{2})", header)
    return date.fromisoformat(match[1]) if match else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("changelog", type=Path)
    parser.add_argument("version")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--output", type=Path)
    output.add_argument("--date-only", action="store_true")
    args = parser.parse_args()
    text = args.changelog.read_text(encoding="utf-8")
    try:
        notes = release_section(text, args.version)
    except ValueError:
        if args.date_only:
            return 0  # A development version may only have Towncrier fragments.
        raise
    if args.date_only:
        print(publication_date(notes) or "")
    elif args.output is None:
        print(notes, end="")
    else:
        args.output.write_text(notes, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
