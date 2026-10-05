"""Read source-owned Corpus release metadata."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path


CORPUS_REPOSITORY = "https://github.com/xiaoland/svc"
CORPUS_VERSION_SETTING = ("tool", "svc", "corpus", "version")
_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")


def require_version(value: object) -> str:
    if not isinstance(value, str) or _VERSION.fullmatch(value) is None:
        raise ValueError(f"Corpus version must be stable x.y.z SemVer: {value!r}")
    return value


def read_corpus_version(pyproject: Path) -> str:
    try:
        document = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        value: object = document["tool"]["svc"]["corpus"]["version"]
    except (KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        raise ValueError(
            "pyproject.toml must define [tool.svc.corpus].version"
        ) from error
    return require_version(value)
