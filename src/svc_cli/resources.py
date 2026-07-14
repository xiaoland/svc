from __future__ import annotations

from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Protocol


class Resource(Protocol):
    def is_file(self) -> bool: ...
    def joinpath(self, *descendants: str): ...
    def read_bytes(self) -> bytes: ...


def resource_root() -> Resource:
    packaged = files("svc_cli").joinpath("data")
    if packaged.joinpath("manifest.json").is_file():
        return packaged
    return Path(__file__).resolve().parents[1]


def read_resource(relative: str) -> bytes:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Resource path must stay inside the release: {relative}")
    resource = resource_root().joinpath(*path.parts)
    if not resource.is_file():
        raise FileNotFoundError(f"Release resource does not exist: {relative}")
    return resource.read_bytes()
