"""Version facts exposed by the packaged runtime."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as distribution_version

from . import DISTRIBUTION_NAME


def installed_distribution_version() -> str | None:
    try:
        return distribution_version(DISTRIBUTION_NAME)
    except PackageNotFoundError:
        return None


def runtime_version() -> str:
    """Report the CLI distribution identity."""

    return installed_distribution_version() or "source-tree"
