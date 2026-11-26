"""Translate the Python distribution version and preserve its artifact names."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from tools.corpus import require_version


CLI_EPOCH = "1!"


def cli_release_version(value: object) -> str:
    """Return the Semantic Version used by the Release PR and GitHub tags."""
    if not isinstance(value, str) or not value.startswith(CLI_EPOCH):
        raise ValueError(
            f"CLI distribution version must use epoch {CLI_EPOCH}: {value!r}"
        )
    return require_version(value.removeprefix(CLI_EPOCH))


def zip_distributions(destination: Path, files: Sequence[Path]) -> None:
    """Wrap Python artifacts so GitHub cannot rewrite their epoch filenames."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w") as archive:
        for file in sorted(files, key=lambda path: path.name):
            entry = ZipInfo(file.name)
            entry.compress_type = ZIP_DEFLATED
            archive.writestr(entry, file.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("files", type=Path, nargs="+")
    args = parser.parse_args()
    zip_distributions(args.destination, args.files)


if __name__ == "__main__":
    main()
