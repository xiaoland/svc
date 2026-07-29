"""Read-only access to the wheel corpus, with a source-tree development fallback."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as distribution_version
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Protocol

from . import DISTRIBUTION_NAME
from .catalog import normalized_document_path


SOURCE_VERSION_FALLBACK = "0.0.0"


class Resource(Protocol):
    def is_file(self) -> bool: ...

    def joinpath(self, *descendants: str): ...

    def read_bytes(self) -> bytes: ...


def source_root() -> Path:
    return Path(__file__).resolve().parents[1] / "src"


def _packaged_data_root() -> Resource | None:
    packaged = files("svc_cli").joinpath("data")
    if packaged.joinpath("catalog.json").is_file():
        return packaged
    return None


def resource_mode() -> str:
    return "wheel" if _packaged_data_root() is not None else "source"


def source_distribution_version() -> str:
    try:
        return distribution_version(DISTRIBUTION_NAME)
    except PackageNotFoundError:
        return SOURCE_VERSION_FALLBACK


def read_catalog_bytes() -> bytes:
    packaged = _packaged_data_root()
    if packaged is not None:
        return packaged.joinpath("catalog.json").read_bytes()

    root = source_root()
    if not root.is_dir():
        raise FileNotFoundError("SVC source fallback is unavailable")
    from tools.build_catalog import build_catalog_bytes

    return build_catalog_bytes(root, source_distribution_version())


def read_document(path: str) -> bytes:
    normalized = normalized_document_path(path)
    packaged = _packaged_data_root()
    if packaged is not None:
        resource = packaged.joinpath("corpus", *PurePosixPath(normalized).parts)
        if not resource.is_file():
            raise FileNotFoundError(
                f"Packaged SVC document does not exist: {normalized}"
            )
        return resource.read_bytes()

    source = source_root() / PurePosixPath(normalized)
    if not source.is_file():
        raise FileNotFoundError(f"SVC source document does not exist: {normalized}")
    return source.read_bytes()
