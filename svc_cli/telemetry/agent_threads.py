"""Provider-neutral contracts for local agent-thread inventory and collection.

The trajectory side deliberately exposes a sink-oriented normalisation seam.
Providers translate one bounded native source into canonical records while the
bundle core owns canonical JSONL, manifests, and publication.  No provider
record is accumulated in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Callable, Iterable, Mapping, Protocol
import unicodedata


MAX_INTERACTIVE_ROWS = 5_000
MAX_WORKSPACE_CHARS = 4_096
MAX_TITLE_CHARS = 160
MAX_FIRST_MESSAGE_CHARS = 512
MAX_THREAD_ID_CHARS = 512
_SIGNED_64_MAX = 9_223_372_036_854_775_807
_CONTROL_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})


class ArchiveState(StrEnum):
    """Provider-reported lifecycle for one thread."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    UNKNOWN = "unknown"


class ArchiveFilter(StrEnum):
    """Safe inventory lifecycle filter; ``all`` is not a lifecycle state."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    ALL = "all"


class SourceAvailability(StrEnum):
    """Whether the provider's local source can currently be collected."""

    AVAILABLE = "available"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class SourceStatus(StrEnum):
    """Descriptor-bound source status reported by a normalizer."""

    STABLE = "stable"
    GREW = "grew"
    CHANGED = "changed"
    DISPLACED = "displaced"


class NormalizationStatus(StrEnum):
    """Whether a structurally valid normalized trajectory is complete."""

    READY = "ready"
    PARTIAL = "partial"


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
class ThreadInventoryQuery:
    """Provider-neutral bounded query for safe thread inventory."""

    archive_state: ArchiveFilter = ArchiveFilter.ALL
    limit: int = 20

    def __post_init__(self) -> None:
        if not isinstance(self.archive_state, ArchiveFilter):
            try:
                object.__setattr__(self, "archive_state", ArchiveFilter(self.archive_state))
            except (TypeError, ValueError) as error:
                raise ValueError("archive_state must be active, archived, or all") from error
        if isinstance(self.limit, bool) or not isinstance(self.limit, int) or not 1 <= self.limit <= 100:
            raise ValueError("limit must be an integer between 1 and 100")


@dataclass(frozen=True)
class ThreadInventoryItem:
    """Provider-neutral inventory facts before the released safe projection."""

    provider_id: str
    thread_id: str
    archive_state: ArchiveState
    source_availability: SourceAvailability
    created_at: str | None = None
    updated_at: str | None = None

    def as_descriptor(self) -> ThreadDescriptor:
        """Project independent facts into the released schema-v1 descriptor."""
        try:
            availability = SourceAvailability(self.source_availability)
        except (TypeError, ValueError):
            availability = SourceAvailability.UNKNOWN
        if availability is SourceAvailability.AVAILABLE:
            try:
                source_state = ArchiveState(self.archive_state).value
            except (TypeError, ValueError):
                source_state = ArchiveState.UNKNOWN.value
        else:
            source_state = availability.value
        return ThreadDescriptor(
            provider_id=self.provider_id,
            thread_id=self.thread_id,
            source_state=source_state,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


@dataclass(frozen=True)
class ThreadInventoryListing:
    """Bounded inventory items plus a redacted count of omitted rows."""

    items: tuple[ThreadInventoryItem, ...]
    omitted_sources: int = 0


def _has_forbidden_control(value: str) -> bool:
    return any(
        unicodedata.category(character) in _CONTROL_CATEGORIES
        for character in value
    )


def _validate_utf8(value: str, *, field_name: str) -> None:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(
            f"{field_name} must be representable UTF-8 text"
        ) from error


@dataclass(frozen=True, slots=True)
class ThreadRef:
    """Stable provider/thread identity for sensitive in-process selection."""

    provider_id: str
    thread_id: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.provider_id, str)
            or not self.provider_id.strip()
            or _has_forbidden_control(self.provider_id)
        ):
            raise ValueError(
                "provider_id must be non-blank, control-free text"
            )
        _validate_utf8(self.provider_id, field_name="provider_id")
        if (
            not isinstance(self.thread_id, str)
            or not 1 <= len(self.thread_id) <= MAX_THREAD_ID_CHARS
            or self.thread_id != self.thread_id.strip()
            or _has_forbidden_control(self.thread_id)
        ):
            raise ValueError(
                "thread_id must be bounded, trimmed, and control-free"
            )
        _validate_utf8(self.thread_id, field_name="thread_id")


@dataclass(frozen=True, slots=True)
class SensitiveInventoryRow:
    """One provider-bounded row for the explicitly sensitive navigator."""

    provider_id: str
    thread_id: str
    archive_state: ArchiveState | str
    source_availability: SourceAvailability | str
    workspace: str | None = field(default=None, repr=False)
    title: str | None = field(default=None, repr=False)
    first_user_message: str | None = field(default=None, repr=False)
    workspace_truncated: bool = False
    title_truncated: bool = False
    first_user_message_truncated: bool = False
    created_at: str | None = field(default=None, repr=False)
    updated_at: str | None = field(default=None, repr=False)
    recency_at_ms: int | None = field(default=None, repr=False)
    source_warning_code: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        reference = ThreadRef(self.provider_id, self.thread_id)
        object.__setattr__(self, "provider_id", reference.provider_id)
        object.__setattr__(self, "thread_id", reference.thread_id)
        try:
            archive_state = ArchiveState(self.archive_state)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "archive_state must be active, archived, or unknown"
            ) from error
        try:
            availability = SourceAvailability(self.source_availability)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "source_availability must be a known enum value"
            ) from error
        object.__setattr__(self, "archive_state", archive_state)
        object.__setattr__(self, "source_availability", availability)

        workspace = self.workspace
        if workspace is not None:
            if not isinstance(workspace, str):
                raise ValueError("workspace must be text or null")
            _validate_utf8(workspace, field_name="workspace")
            if len(workspace) > MAX_WORKSPACE_CHARS:
                raise ValueError(
                    "workspace exceeds its provider-enforced bound"
                )
            if _has_forbidden_control(workspace):
                workspace = None
        if self.workspace_truncated:
            if workspace is not None:
                raise ValueError(
                    "workspace_truncated requires a null workspace value"
                )
        object.__setattr__(self, "workspace", workspace or None)

        for field_name, maximum in (
            ("title", MAX_TITLE_CHARS),
            ("first_user_message", MAX_FIRST_MESSAGE_CHARS),
        ):
            value = getattr(self, field_name)
            if value is None:
                continue
            if not isinstance(value, str):
                raise ValueError(f"{field_name} must be text or null")
            _validate_utf8(value, field_name=field_name)
            if len(value) > maximum:
                raise ValueError(
                    f"{field_name} exceeds its provider-enforced bound"
                )

        if self.recency_at_ms is not None and (
            isinstance(self.recency_at_ms, bool)
            or not isinstance(self.recency_at_ms, int)
            or self.recency_at_ms < 0
            or self.recency_at_ms > _SIGNED_64_MAX
        ):
            object.__setattr__(self, "recency_at_ms", None)

    @property
    def selection(self) -> ThreadRef:
        return ThreadRef(self.provider_id, self.thread_id)

    @property
    def analyzable(self) -> bool:
        return self.source_availability is SourceAvailability.AVAILABLE

    def __repr__(self) -> str:
        return (
            "SensitiveInventoryRow("
            f"provider_id={self.provider_id!r}, "
            f"thread_id={self.thread_id!r}, "
            f"archive_state={str(self.archive_state)!r}, "
            f"source_availability={str(self.source_availability)!r}, "
            f"workspace_truncated={self.workspace_truncated}, "
            f"title_truncated={self.title_truncated}, "
            "first_user_message_truncated="
            f"{self.first_user_message_truncated})"
        )


@dataclass(frozen=True, slots=True)
class SensitiveInventoryQuery:
    """Bounded interactive query; active is the deliberate default."""

    archive_state: ArchiveFilter | str = ArchiveFilter.ACTIVE
    limit: int = MAX_INTERACTIVE_ROWS

    def __post_init__(self) -> None:
        try:
            archive_state = ArchiveFilter(self.archive_state)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "archive_state must be active, archived, or all"
            ) from error
        object.__setattr__(self, "archive_state", archive_state)
        if (
            isinstance(self.limit, bool)
            or not isinstance(self.limit, int)
            or not 1 <= self.limit <= MAX_INTERACTIVE_ROWS
        ):
            raise ValueError(
                f"limit must be an integer between 1 and "
                f"{MAX_INTERACTIVE_ROWS}"
            )

    @property
    def archive_filter(self) -> ArchiveFilter:
        return ArchiveFilter(self.archive_state)


def _sensitive_row_order(
    row: SensitiveInventoryRow,
) -> tuple[bool, int, bytes, bytes]:
    recency_at_ms = row.recency_at_ms
    missing = recency_at_ms is None
    recency = 0 if recency_at_ms is None else -recency_at_ms
    return (
        missing,
        recency,
        row.thread_id.encode("utf-8"),
        row.provider_id.encode("utf-8"),
    )


@dataclass(frozen=True, slots=True)
class SensitiveInventoryListing:
    """A bounded listing plus an honest non-counting truncation signal."""

    items: tuple[SensitiveInventoryRow, ...]
    inventory_truncated: bool = False
    omitted_sources: int = 0

    def __post_init__(self) -> None:
        items = tuple(self.items)
        if len(items) > MAX_INTERACTIVE_ROWS:
            raise ValueError(
                f"listing cannot retain more than {MAX_INTERACTIVE_ROWS} rows"
            )
        if (
            isinstance(self.omitted_sources, bool)
            or not isinstance(self.omitted_sources, int)
            or self.omitted_sources < 0
        ):
            raise ValueError(
                "omitted_sources must be a non-negative integer"
            )
        object.__setattr__(self, "items", items)

    @classmethod
    def from_rows(
        cls,
        rows: Iterable[SensitiveInventoryRow],
        *,
        archive_state: ArchiveFilter | str = ArchiveFilter.ACTIVE,
        limit: int = MAX_INTERACTIVE_ROWS,
        omitted_sources: int = 0,
    ) -> "SensitiveInventoryListing":
        query = SensitiveInventoryQuery(
            archive_state=archive_state,
            limit=limit,
        )
        retained: list[SensitiveInventoryRow] = []
        truncated = False
        for row in rows:
            if not isinstance(row, SensitiveInventoryRow):
                raise TypeError(
                    "rows must contain SensitiveInventoryRow values"
                )
            if (
                query.archive_filter is not ArchiveFilter.ALL
                and ArchiveState(row.archive_state).value
                != query.archive_filter.value
            ):
                continue
            if len(retained) >= query.limit:
                truncated = True
                continue
            retained.append(row)
        retained.sort(key=_sensitive_row_order)
        return cls(
            tuple(retained),
            inventory_truncated=truncated,
            omitted_sources=omitted_sources,
        )


@dataclass(frozen=True)
class ResolvedThread:
    """A descriptor-bound local source selected for normalisation.

    ``source_path`` is process-local authority only.  It is never copied into
    a bundle or exposed through a service payload.  ``thread_id`` remains the
    provider's native selection identity; the normalizer derives the opaque
    schema-v2 ``thread_ref``.
    """

    provider_id: str
    adapter_id: str
    source_format: str
    thread_id: str
    source_path: Path = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source_path, Path):
            object.__setattr__(self, "source_path", Path(self.source_path))
        if not self.thread_id.strip():
            raise ValueError("thread_id must not be blank")


NormalizedRecordSink = Callable[[Mapping[str, object]], bool]


@dataclass(frozen=True)
class NormalizationResult:
    """Bounded provider facts returned after streaming normalized records.

    ``counts``, ``lossiness``, and ``diagnostics`` are manifest-facing values;
    the bundle core validates and serializes them.  The provider does not
    retain the emitted records.  Snapshots are local publication evidence and
    are intentionally not portable manifest fields.
    """

    provider_id: str
    adapter_id: str
    source_format: str
    thread_ref: str
    workspace: Mapping[str, object]
    source_status: SourceStatus | str
    result_status: NormalizationStatus | str
    capabilities: Mapping[str, str]
    counts: Mapping[str, object]
    lossiness: Mapping[str, object]
    diagnostics: tuple[Mapping[str, object], ...] = ()
    source_snapshot: "SourceSnapshot | None" = None
    final_snapshot: "SourceSnapshot | None" = None

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "source_status", SourceStatus(self.source_status))
            object.__setattr__(self, "result_status", NormalizationStatus(self.result_status))
        except (TypeError, ValueError) as error:
            raise ValueError("invalid normalization status") from error
        if not isinstance(self.thread_ref, str) or not self.thread_ref.startswith("thread_"):
            raise ValueError("thread_ref must be an opaque thread reference")


@dataclass(frozen=True)
class SourceSnapshot:
    """Filesystem identity of a descriptor-bound source snapshot.

    It is intentionally not serialized into the portable archive: device and
    inode values are local implementation details.  The archive core uses it
    only to reject a replaced source at the pre-publication atomic-commit gate.
    Providers without a stable filesystem source may leave it absent.
    """

    device: int
    inode: int
    size: int
    mtime_ns: int


class ThreadProvider(Protocol):
    """A static provider adapter for safe inventory and trajectory collection."""

    provider_id: str

    def list_inventory(self, context: ProviderContext, query: ThreadInventoryQuery) -> ThreadInventoryListing: ...

    def resolve(self, context: ProviderContext, selection: ThreadSelection) -> ResolvedThread: ...

    def stream_normalize(
        self,
        resolved: ResolvedThread,
        sink: NormalizedRecordSink,
        bounds: Mapping[str, int],
    ) -> NormalizationResult: ...


class SensitiveInventoryProvider(Protocol):
    """The separately invoked recognition-bearing inventory capability."""

    provider_id: str

    def list_sensitive_inventory(
        self,
        context: ProviderContext,
        query: SensitiveInventoryQuery,
    ) -> SensitiveInventoryListing: ...
