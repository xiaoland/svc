"""Provider-neutral contracts for explicit local agent-thread evidence capture."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Mapping, Protocol


ARCHIVE_SCHEMA_VERSION = 1
INDEX_SCHEMA_VERSION = 1


def _archive_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or path.is_absolute()
        or "." in path.parts
        or ".." in path.parts
        or path.as_posix() != value
        or "\\" in value
    ):
        raise ValueError(f"Archive path must be normalized and relative: {value!r}")
    return value


@dataclass(frozen=True)
class ProviderContext:
    """Explicit, provider-owned local source location; never an implicit scan root."""

    home: Path | None = None


@dataclass(frozen=True)
class ThreadSelection:
    """One exact user-selected thread or native source artifact."""

    thread_id: str | None = None
    source: Path | None = None

    def __post_init__(self) -> None:
        if (self.thread_id is None) == (self.source is None):
            raise ValueError("Exactly one of thread_id or source is required")
        if self.thread_id is not None and not self.thread_id.strip():
            raise ValueError("thread_id must not be blank")


@dataclass(frozen=True)
class ThreadDescriptor:
    """Selection metadata deliberately excluding transcript and title content."""

    provider_id: str
    thread_id: str
    source_state: str
    created_at: str | None = None
    updated_at: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "provider_id": self.provider_id,
            "thread_id": self.thread_id,
            "source_state": self.source_state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class SourceArtifact:
    """One native source file copied as raw evidence into a provider namespace."""

    source_path: Path
    archive_path: str
    media_type: str

    def __post_init__(self) -> None:
        _archive_path(self.archive_path)


@dataclass(frozen=True)
class ResolvedThread:
    """A provider's exact local source resolution, before any archive mutation."""

    provider_id: str
    adapter_id: str
    source_format: str
    thread_id: str
    source_state: str
    artifact: SourceArtifact


@dataclass(frozen=True)
class TextOccurrence:
    """A message-derived value eligible for lexical task-packet discovery."""

    text: str = field(repr=False)
    source_line: int = 0
    record_type: str = "unknown"
    role: str = "unknown"
    field_path: str = ""

    def provenance(self) -> dict[str, object]:
        return {
            "source_line": self.source_line,
            "record_type": self.record_type,
            "role": self.role,
            "field_path": self.field_path,
        }


@dataclass(frozen=True)
class CaptureWarning:
    """A non-sensitive observation retained in the evidence manifest."""

    code: str
    details: Mapping[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "details": dict(self.details)}


@dataclass(frozen=True)
class SourceSnapshot:
    """Filesystem identity of the source that produced a captured raw artifact.

    It is intentionally not serialized into the portable archive: device and
    inode values are local implementation details.  The archive core uses it
    only to reject a replaced source at the pre-publication atomic-commit gate.
    Providers without a stable filesystem source may leave it absent.
    """

    device: int
    inode: int
    size: int
    mtime_ns: int


@dataclass(frozen=True)
class CaptureEvidence:
    """Derived, provider-neutral facts about an exact native artifact capture."""

    source_sha256: str
    source_bytes: int
    record_counts: Mapping[str, int]
    capabilities: Mapping[str, str]
    occurrences: tuple[TextOccurrence, ...]
    warnings: tuple[CaptureWarning, ...]
    source_snapshot: SourceSnapshot | None = None


class ThreadProvider(Protocol):
    """A static provider adapter; it writes only to sinks owned by the archive core."""

    provider_id: str

    def list_metadata(self, context: ProviderContext, limit: int) -> tuple[ThreadDescriptor, ...]: ...

    def resolve(self, context: ProviderContext, selection: ThreadSelection) -> ResolvedThread: ...

    def stream_capture(
        self,
        resolved: ResolvedThread,
        raw_output: BinaryIO,
        index_output: BinaryIO,
    ) -> CaptureEvidence: ...
