"""Compare the built CLI distributions with the public PyPI version."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import tomllib
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen


def published_hashes(package: str, version: str) -> dict[str, str]:
    try:
        with urlopen(
            f"https://pypi.org/pypi/{package}/{quote(version, safe='')}/json",
            timeout=30,
        ) as response:
            files = json.load(response)["urls"]
    except HTTPError as error:
        if error.code != 404:
            raise
        return {}
    return {file["filename"]: file["digests"]["sha256"] for file in files}


def check(directory: Path, package: str, version: str, *, complete: bool) -> None:
    files = list(directory.iterdir())
    if (
        len(files) != 2
        or not any(path.name.endswith(".whl") for path in files)
        or not any(path.name.endswith(".tar.gz") for path in files)
    ):
        raise ValueError("expected exactly a wheel and a source distribution")
    expected = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files
    }
    attempts = 6 if complete else 1
    for attempt in range(attempts):
        published = published_hashes(package, version)
        if published.items() - expected.items():
            raise ValueError("PyPI contains different distributions for this version")
        if not complete or published == expected:
            return
        if attempt + 1 < attempts:
            time.sleep(5)
    raise ValueError("PyPI did not expose every verified distribution")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--complete", action="store_true")
    args = parser.parse_args()
    project = tomllib.loads(Path("cli/pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    check(args.directory, project["name"], project["version"], complete=args.complete)


if __name__ == "__main__":
    main()
