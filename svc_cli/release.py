"""Version facts exposed by the packaged runtime."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as distribution_version

from . import DISTRIBUTION_NAME
from .catalog import Catalog, parse_catalog
from .resources import read_catalog_bytes


def catalog() -> Catalog:
    return parse_catalog(read_catalog_bytes())


def installed_distribution_version() -> str | None:
    try:
        return distribution_version(DISTRIBUTION_NAME)
    except PackageNotFoundError:
        return None


def runtime_version() -> str:
    """Use package metadata when available, otherwise the source catalog during development."""

    return installed_distribution_version() or catalog().svc_version
