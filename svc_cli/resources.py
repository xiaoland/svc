"""Read-only access to the wheel corpus, with a source-tree development fallback."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Protocol

from .catalog import normalized_document_path


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


def read_catalog_bytes() -> bytes:
    packaged = _packaged_data_root()
    if packaged is not None:
        return packaged.joinpath("catalog.json").read_bytes()

    root = source_root()
    if not root.is_dir():
        raise FileNotFoundError("SVC source fallback is unavailable")
    from tools.build_catalog import build_catalog_bytes

    return build_catalog_bytes(root)


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


def read_config_migration_descriptor(from_schema: int, to_schema: int) -> bytes:
    """Read one CLI-owned configuration migration descriptor."""

    name = f"config-{from_schema}-{to_schema}.json"
    packaged = _packaged_data_root()
    if packaged is not None:
        resource = packaged.joinpath("migrations", name)
        if not resource.is_file():
            raise FileNotFoundError(
                f"Packaged config migration descriptor does not exist: {name}"
            )
        return resource.read_bytes()

    source = Path(__file__).resolve().parent / "data" / "migrations" / name
    if not source.is_file():
        raise FileNotFoundError(
            f"Source config migration descriptor does not exist: {name}"
        )
    return source.read_bytes()
