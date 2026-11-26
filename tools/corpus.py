"""Read source-owned Corpus release metadata."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path


CORPUS_REPOSITORY = "https://github.com/xiaoland/svc"
CORPUS_TAG_PREFIX = "skills-v"
LEGACY_CORPUS_TAG_PREFIX = "corpus-v"
_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")


@dataclass(frozen=True)
class CorpusRelease:
    version: str
    tag_prefix: str

    @property
    def tag(self) -> str:
        return self.tag_prefix + self.version


def require_version(value: object) -> str:
    if not isinstance(value, str) or _VERSION.fullmatch(value) is None:
        raise ValueError(f"Corpus version must be stable x.y.z SemVer: {value!r}")
    return value


def parse_corpus_release(text: str, *, allow_legacy: bool = False) -> CorpusRelease:
    try:
        settings = tomllib.loads(text)["tool"]["svc"]["corpus"]
        version = require_version(settings["version"])
        prefix = settings.get(
            "tag-prefix", LEGACY_CORPUS_TAG_PREFIX if allow_legacy else None
        )
    except (KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        raise ValueError(
            "pyproject.toml must define [tool.svc.corpus].version"
        ) from error
    if prefix != CORPUS_TAG_PREFIX and not (
        allow_legacy and prefix == LEGACY_CORPUS_TAG_PREFIX
    ):
        raise ValueError(
            f'pyproject.toml must define [tool.svc.corpus].tag-prefix = "{CORPUS_TAG_PREFIX}"'
        )
    return CorpusRelease(version, prefix)


def read_corpus_release(pyproject: Path) -> CorpusRelease:
    return parse_corpus_release(pyproject.read_text(encoding="utf-8"))


def read_corpus_version(pyproject: Path) -> str:
    return read_corpus_release(pyproject).version
