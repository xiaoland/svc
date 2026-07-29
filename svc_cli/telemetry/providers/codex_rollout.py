"""Read-only adapter for Codex ``rollout-v1`` JSONL snapshots.

The adapter intentionally treats the source JSONL as the authority.  It does
not launch Codex, inspect editor caches, or attempt to interpret provider
payloads beyond the small amount of metadata needed for indexing.
"""

from __future__ import annotations

import errno
import json
import os
import shutil
import sqlite3
import stat
import tempfile
import unicodedata
from pathlib import Path
from dataclasses import replace
from typing import BinaryIO, Iterable, Mapping
from ...errors import SvcError
from ..agent_threads import (
    ArchiveState,
    MAX_FIRST_MESSAGE_CHARS,
    MAX_INTERACTIVE_ROWS,
    MAX_TITLE_CHARS,
    MAX_WORKSPACE_CHARS,
    NormalizationResult,
    NormalizedRecordSink,
    NormalizationStatus,
    ProviderContext,
    ResolvedThread,
    SensitiveInventoryListing,
    SensitiveInventoryQuery,
    SensitiveInventoryRow,
    SourceAvailability,
    SourceSnapshot,
    SourceStatus,
    ThreadInventoryItem,
    ThreadInventoryListing,
    ThreadInventoryQuery,
    ThreadSelection,
)
from .codex_trajectory import CodexTrajectoryNormalizer, DEFAULT_BOUNDS


MAX_INDEX_RECORD_BYTES = 4 * 1024 * 1024
MAX_THREAD_ID_CHARS = 512
MAX_ROLLOUT_PATH_CHARS = 4096
_MAX_SQLITE_INTEGER = 9_223_372_036_854_775_807
_MAX_RECENCY_SECONDS = _MAX_SQLITE_INTEGER // 1000
_SOURCE_FORMAT = "rollout-v1"
_ADAPTER_ID = "codex-rollout-v1"


def _is_link_or_reparse_point(info: os.stat_result) -> bool:
    """Treat Windows reparse points as links, not regular source files."""
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & reparse)


def _error(code: str, message: str, **details: object) -> SvcError:
    return SvcError(code, message, details)


def _home(context: ProviderContext) -> Path:
    if context.home is not None:
        return Path(context.home).expanduser()
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def _lstat_regular(path: Path, *, what: str) -> os.stat_result:
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise _error("thread-source-not-found", f"Codex {what} does not exist.", path=str(path)) from exc
    except (OSError, ValueError) as exc:
        raise _error("thread-source-unreadable", f"Codex {what} cannot be inspected.", path=str(path), reason=str(exc)) from exc
    if _is_link_or_reparse_point(info):
        raise _error("thread-source-unsafe", f"Codex {what} must not be a symlink.", path=str(path))
    if not stat.S_ISREG(info.st_mode):
        raise _error("thread-source-unsafe", f"Codex {what} must be a regular file.", path=str(path))
    return info


def _source_snapshot(info: os.stat_result) -> SourceSnapshot:
    return SourceSnapshot(
        device=info.st_dev,
        inode=info.st_ino,
        size=info.st_size,
        mtime_ns=info.st_mtime_ns,
    )


def _open_source(path: Path) -> tuple[BinaryIO, os.stat_result]:
    before = _lstat_regular(path, what="rollout source")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise _error("thread-source-unreadable", "Codex rollout source cannot be opened.", path=str(path), reason=str(exc)) from exc
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise _error("thread-source-unsafe", "Codex rollout source was replaced while opening.", path=str(path))
        return os.fdopen(fd, "rb"), opened
    except Exception:
        os.close(fd)
        raise


def _readline(stream: BinaryIO, limit: int, path: Path) -> bytes:
    """Translate a native-source read fault into a provider diagnostic."""
    try:
        return stream.readline(limit)
    except OSError as exc:
        raise _error(
            "thread-source-unreadable",
            "Codex rollout source cannot be read.",
            path=str(path),
            reason=str(exc),
        ) from exc


def _state_signature(info: os.stat_result) -> tuple[int, int, int, int]:
    """Stable SQLite snapshot identity across the supported host filesystems.

    Windows may update ``ctime_ns`` merely while a database is inspected, so
    it cannot be a read-only snapshot precondition.  Device/inode/size/mtime
    are rechecked both around descriptor-bound copies and around all sidecars.
    The exported rollout itself uses the stricter source identity contract.
    """
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _resolve_path(home: Path, value: object) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise _error("thread-source-incompatible", "State database has no usable rollout path.")
    try:
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = home / candidate
        # Keep the state-database path lexical.  Resolving here would follow a
        # symlink/reparse component before the no-follow open in
        # ``_open_source`` and would turn an unsafe selection into a trusted
        # target.  Every component is lstat-checked before returning.
        candidate = Path(os.path.abspath(candidate))
        home_lexical = Path(os.path.abspath(home.expanduser()))
        if not candidate.is_relative_to(home_lexical):
            raise _error("thread-source-unsafe", "State database rollout path escapes CODEX_HOME.", path=str(candidate), home=str(home))
        relative = candidate.relative_to(home_lexical)
        current = home_lexical
        for component in relative.parts:
            current = current / component
            info = current.lstat()
            if _is_link_or_reparse_point(info):
                raise _error("thread-source-unsafe", "Codex rollout source path contains a symlink or reparse point.")
    except (OSError, RuntimeError, ValueError) as exc:
        raise _error("thread-source-unsafe", "State database rollout path cannot be safely resolved.", path=value, reason=str(exc)) from exc
    return candidate


def _columns(connection: sqlite3.Connection) -> list[str]:
    try:
        rows = connection.execute("PRAGMA table_info(threads)").fetchall()
    except sqlite3.DatabaseError as exc:
        raise _error("thread-source-incompatible", "Codex state database has an unreadable threads table.", reason=str(exc)) from exc
    return [str(row[1]) for row in rows]


def _pick(columns: Iterable[str], choices: tuple[str, ...]) -> str | None:
    by_lower = {column.lower(): column for column in columns}
    for choice in choices:
        if choice.lower() in by_lower:
            return by_lower[choice.lower()]
    return None


class _SnapshotConnection:
    def __init__(self, connection: sqlite3.Connection, directory: str) -> None:
        self._connection = connection
        self._directory = directory

    def execute(self, *args: object, **kwargs: object):
        return self._connection.execute(*args, **kwargs)

    def close(self) -> None:
        try:
            self._connection.close()
        finally:
            shutil.rmtree(self._directory, ignore_errors=True)


def _copy_snapshot_member(
    source: Path,
    destination: Path,
    expected: tuple[int, int, int, int],
) -> bool:
    """Copy one member through a descriptor bound to the preflight inode."""
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(source, flags)
    try:
        opened = os.fstat(fd)
        identity = _state_signature(opened)
        if identity != expected or _is_link_or_reparse_point(opened) or not stat.S_ISREG(opened.st_mode):
            return False
        with os.fdopen(fd, "rb") as source_stream:
            fd = -1
            with destination.open("xb") as destination_stream:
                copied = 0
                while True:
                    chunk = source_stream.read(1024 * 1024)
                    if not chunk:
                        break
                    destination_stream.write(chunk)
                    copied += len(chunk)
            final = os.fstat(source_stream.fileno())
        final_identity = _state_signature(final)
        return copied == expected[2] and final_identity == expected
    finally:
        if fd >= 0:
            os.close(fd)


def _state_snapshot(path: Path) -> tuple[Path, str]:
    _lstat_regular(path, what="state database")
    sidecars = (Path(f"{path}-wal"), Path(f"{path}-shm"), Path(f"{path}-journal"))
    for attempt in range(3):
        before: dict[Path, tuple[int, int, int, int] | None] = {}
        for candidate in (path, *sidecars):
            try:
                info = candidate.lstat()
            except FileNotFoundError:
                before[candidate] = None
                continue
            if _is_link_or_reparse_point(info) or not stat.S_ISREG(info.st_mode):
                raise _error("thread-source-unsafe", "Codex state sidecar must be a regular non-symlink file.", path=str(candidate))
            before[candidate] = _state_signature(info)
        directory = tempfile.mkdtemp(prefix="svc-codex-state-")
        snapshot = Path(directory) / path.name
        try:
            stable = True
            for candidate in (path, *sidecars):
                if before[candidate] is not None:
                    if not _copy_snapshot_member(candidate, Path(directory) / candidate.name, before[candidate]):
                        stable = False
                        break
            if not stable:
                shutil.rmtree(directory, ignore_errors=True)
                continue
            after: dict[Path, tuple[int, int, int, int] | None] = {}
            for candidate in (path, *sidecars):
                try:
                    info = candidate.lstat()
                except FileNotFoundError:
                    after[candidate] = None
                    continue
                if _is_link_or_reparse_point(info) or not stat.S_ISREG(info.st_mode):
                    stable = False
                    break
                after[candidate] = _state_signature(info)
            if not stable:
                shutil.rmtree(directory, ignore_errors=True)
                continue
            if before == after:
                return snapshot, directory
        except OSError as exc:
            shutil.rmtree(directory, ignore_errors=True)
            if attempt == 2:
                raise _error("thread-source-mutated", "Codex state database could not be snapshotted safely.", path=str(path), reason=str(exc)) from exc
            continue
        shutil.rmtree(directory, ignore_errors=True)
    raise _error("thread-source-mutated", "Codex state database changed while taking a read-only snapshot.", path=str(path))


def _state_connection(path: Path) -> _SnapshotConnection:
    snapshot, directory = _state_snapshot(path)
    connection: sqlite3.Connection | None = None
    handed_off = False
    try:
        connection = sqlite3.connect(snapshot)
        connection.execute("PRAGMA query_only=ON")
        table = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='threads'").fetchone()
        if table is None:
            raise _error("thread-source-incompatible", "Codex state database has no compatible threads table.", path=str(path))
        snapshot_connection = _SnapshotConnection(connection, directory)
        handed_off = True
        return snapshot_connection
    except SvcError:
        raise
    except sqlite3.DatabaseError as exc:
        raise _error("thread-source-incompatible", "Codex state database is not a readable SQLite database.", path=str(path), reason=str(exc)) from exc
    finally:
        if not handed_off:
            try:
                if connection is not None:
                    connection.close()
            finally:
                shutil.rmtree(directory, ignore_errors=True)


def _archive_state(value: object) -> ArchiveState:
    """Map only the exact Codex lifecycle authority."""
    if isinstance(value, int) and not isinstance(value, bool):
        if value == 0:
            return ArchiveState.ACTIVE
        if value == 1:
            return ArchiveState.ARCHIVED
    return ArchiveState.UNKNOWN


def _forbidden_inventory_text(value: str) -> bool:
    forbidden_categories = {"Cc", "Cf", "Cs", "Zl", "Zp"}
    return any(unicodedata.category(character) in forbidden_categories for character in value)


def _bounded_sqlite_text(value: object, *, sqlite_type: object, max_chars: int) -> str | None:
    """Decode one SQL-bounded text prefix without replacement or normalization."""
    if sqlite_type != "text":
        return None
    if isinstance(value, bytes):
        try:
            decoded = value.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return None
    elif isinstance(value, str):
        decoded = value
    else:
        return None
    if len(decoded) > max_chars:
        return None
    try:
        decoded.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        return None
    return decoded


def _safe_thread_id(sqlite_type: object, prefix: object, has_nul: object) -> str | None:
    thread_id = _bounded_sqlite_text(prefix, sqlite_type=sqlite_type, max_chars=MAX_THREAD_ID_CHARS)
    if (
        thread_id is None
        or not thread_id
        or bool(has_nul)
        or thread_id[0].isspace()
        or thread_id[-1].isspace()
        or _forbidden_inventory_text(thread_id)
    ):
        return None
    return thread_id


def _inventory_failure(error: OSError) -> SourceAvailability | None:
    """Classify a path-inspection failure without retaining its sensitive value."""
    if error.errno in {errno.ENOENT, errno.ENOTDIR}:
        return SourceAvailability.MISSING
    if error.errno in {errno.ELOOP, errno.ENAMETOOLONG}:
        return None
    if error.errno in {errno.EACCES, errno.EPERM, errno.EBUSY, errno.ETXTBSY}:
        return SourceAvailability.UNAVAILABLE
    if getattr(error, "winerror", None) in {5, 32, 33}:
        return SourceAvailability.UNAVAILABLE
    return SourceAvailability.UNAVAILABLE


def _inventory_source_availability(
    home: Path,
    sqlite_type: object,
    prefix: object,
    has_nul: object,
) -> SourceAvailability | None:
    """Inspect a SQL-bounded rollout path without following links or reading it."""
    if sqlite_type == "null":
        return SourceAvailability.UNAVAILABLE
    value = _bounded_sqlite_text(prefix, sqlite_type=sqlite_type, max_chars=MAX_ROLLOUT_PATH_CHARS)
    if value is None or bool(has_nul):
        return None
    if not value.strip():
        return SourceAvailability.UNAVAILABLE
    if _forbidden_inventory_text(value):
        return None

    try:
        os.fsencode(value)
        home_root = home.expanduser().resolve(strict=True)
        raw_candidate = Path(value)
        if not raw_candidate.is_absolute():
            raw_candidate = home_root / raw_candidate
        candidate = Path(os.path.abspath(os.fspath(raw_candidate)))
        if os.path.commonpath((os.fspath(home_root), os.fspath(candidate))) != os.fspath(home_root):
            return None
        relative = candidate.relative_to(home_root)
    except (OSError, RuntimeError, UnicodeError, ValueError):
        return None

    current = home_root
    before: os.stat_result | None = None
    for index, component in enumerate(relative.parts):
        current /= component
        try:
            inspected = current.lstat()
        except OSError as error:
            return _inventory_failure(error)
        if _is_link_or_reparse_point(inspected):
            return None
        final = index == len(relative.parts) - 1
        if final:
            if not stat.S_ISREG(inspected.st_mode):
                return None
            before = inspected
        elif not stat.S_ISDIR(inspected.st_mode):
            return None

    if before is None:
        return None

    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = -1
    try:
        fd = os.open(candidate, flags)
        opened = os.fstat(fd)
        if (
            _is_link_or_reparse_point(opened)
            or not stat.S_ISREG(opened.st_mode)
            or (opened.st_dev, opened.st_ino, stat.S_IFMT(opened.st_mode))
            != (before.st_dev, before.st_ino, stat.S_IFMT(before.st_mode))
        ):
            return None
        os.read(fd, 0)
        return SourceAvailability.AVAILABLE
    except OSError as error:
        return _inventory_failure(error)
    finally:
        if fd >= 0:
            os.close(fd)


def _metadata_rows(home: Path, query: ThreadInventoryQuery) -> ThreadInventoryListing:
    database = home / "state_5.sqlite"
    connection = _state_connection(database)
    try:
        columns = _columns(connection)
        if "id" not in columns or "rollout_path" not in columns:
            raise _error("thread-source-incompatible", "Codex threads table does not expose exact ID and rollout path columns.", columns=columns)

        archive_value = (
            """CASE
                WHEN typeof("archived") = 'integer' AND "archived" IN (0, 1)
                THEN "archived"
                ELSE NULL
            END"""
            if "archived" in columns
            else "NULL"
        )
        archive_state = (
            """CASE
                WHEN typeof("archived") = 'integer' AND "archived" = 0 THEN 'active'
                WHEN typeof("archived") = 'integer' AND "archived" = 1 THEN 'archived'
                ELSE 'unknown'
            END"""
            if "archived" in columns
            else "'unknown'"
        )

        def non_negative_integer(column: str) -> str:
            if column not in columns:
                return "NULL"
            return f"""CASE
                WHEN typeof("{column}") = 'integer' AND "{column}" >= 0
                THEN "{column}"
                ELSE NULL
            END"""

        recency_candidates: list[str] = []
        for column in ("recency_at_ms", "updated_at_ms"):
            if column in columns:
                recency_candidates.append(
                    f"""WHEN typeof("{column}") = 'integer'
                        AND "{column}" BETWEEN 0 AND {_MAX_SQLITE_INTEGER}
                    THEN "{column}" """
                )
        if "updated_at" in columns:
            recency_candidates.append(
                f"""WHEN typeof("updated_at") = 'integer'
                    AND "updated_at" BETWEEN 0 AND {_MAX_RECENCY_SECONDS}
                THEN "updated_at" * 1000 """
            )
        recency = "CASE " + " ".join(recency_candidates) + " ELSE NULL END" if recency_candidates else "NULL"

        sql = f"""
            WITH inventory AS (
                SELECT
                    typeof("id") AS id_type,
                    CASE WHEN typeof("id") = 'text'
                        THEN CAST(substr("id", 1, {MAX_THREAD_ID_CHARS + 1}) AS BLOB)
                        ELSE NULL
                    END AS id_prefix,
                    CASE WHEN typeof("id") = 'text'
                        THEN instr("id", char(0)) > 0
                        ELSE 0
                    END AS id_has_nul,
                    typeof("rollout_path") AS path_type,
                    CASE WHEN typeof("rollout_path") = 'text'
                        THEN CAST(substr("rollout_path", 1, {MAX_ROLLOUT_PATH_CHARS + 1}) AS BLOB)
                        ELSE NULL
                    END AS path_prefix,
                    CASE WHEN typeof("rollout_path") = 'text'
                        THEN instr("rollout_path", char(0)) > 0
                        ELSE 0
                    END AS path_has_nul,
                    {archive_value} AS archive_value,
                    {archive_state} AS archive_state,
                    {non_negative_integer("created_at")} AS created_at,
                    {non_negative_integer("updated_at")} AS updated_at,
                    {recency} AS recency,
                    COUNT(*) OVER (
                        PARTITION BY typeof("id"), CAST("id" AS BLOB)
                    ) AS duplicate_count
                FROM threads
            )
            SELECT
                id_type, id_prefix, id_has_nul,
                path_type, path_prefix, path_has_nul,
                archive_value, created_at, updated_at, duplicate_count
            FROM inventory
            WHERE ? = 'all' OR archive_state = ?
            ORDER BY recency IS NULL ASC, recency DESC, id_prefix ASC
        """
        archive_filter = query.archive_state.value
        rows = connection.execute(sql, (archive_filter, archive_filter))
        result: list[ThreadInventoryItem] = []
        omitted_sources = 0
        for row in rows:
            (
                id_type,
                id_prefix,
                id_has_nul,
                path_type,
                path_prefix,
                path_has_nul,
                raw_archive_value,
                created_at,
                updated_at,
                duplicate_count,
            ) = row
            thread_id = _safe_thread_id(id_type, id_prefix, id_has_nul)
            if thread_id is None or duplicate_count != 1:
                omitted_sources += 1
                continue
            availability = _inventory_source_availability(
                home,
                path_type,
                path_prefix,
                path_has_nul,
            )
            if availability is None:
                omitted_sources += 1
                continue
            # Inspect every ordered row so the degradation count is complete,
            # while the query limit caps only safe returned inventory items.
            if len(result) < query.limit:
                result.append(ThreadInventoryItem(
                    provider_id="codex",
                    thread_id=thread_id,
                    archive_state=_archive_state(raw_archive_value),
                    source_availability=availability,
                    created_at=None if created_at is None else str(created_at),
                    updated_at=None if updated_at is None else str(updated_at),
                ))
        return ThreadInventoryListing(tuple(result), omitted_sources)
    except SvcError:
        raise
    except sqlite3.DatabaseError as exc:
        raise _error("thread-source-incompatible", "Codex state database metadata cannot be read.", path=str(database), reason=str(exc)) from exc
    finally:
        connection.close()


def _sensitive_text_projection(
    columns: Iterable[str],
    column: str,
    maximum_code_points: int,
) -> tuple[str, str, str]:
    """Return type, bounded UTF-8 bytes, and byte-overflow SQL expressions.

    The normal branch uses SQLite text ``substr`` and therefore materializes
    at most ``maximum + 1`` code points.  SQLite text functions stop at an
    embedded NUL, so that exceptional branch retains at most the same number
    of raw UTF-8 bytes; the mapper either decodes that bounded prefix exactly
    or treats the optional recognition value as unavailable.
    """

    if column not in columns:
        return "'null'", "NULL", "0"
    prefix_limit = maximum_code_points + 1
    quoted = column.replace('"', '""')
    sqlite_type = f'typeof("{quoted}")'
    prefix = (
        f"""CASE WHEN {sqlite_type} = 'text'
                AND instr("{quoted}", char(0)) = 0
            THEN CAST(
                substr("{quoted}", 1, {prefix_limit})
                AS BLOB
            )
            WHEN {sqlite_type} = 'text'
            THEN substr(
                CAST("{quoted}" AS BLOB),
                1,
                {prefix_limit}
            )
            ELSE NULL END"""
    )
    overflow = (
        f"""CASE WHEN {sqlite_type} = 'text'
                AND instr("{quoted}", char(0)) = 0
            THEN length("{quoted}") > {prefix_limit}
            WHEN {sqlite_type} = 'text'
            THEN length(CAST("{quoted}" AS BLOB)) > {prefix_limit}
            ELSE 0 END"""
    )
    return sqlite_type, prefix, overflow


def _decode_sensitive_prefix(
    sqlite_type: object,
    prefix: object,
    byte_overflow: object,
    *,
    maximum_code_points: int,
    discard_when_truncated: bool,
) -> tuple[str | None, bool]:
    """Decode one SQL-bounded optional value without replacement decoding."""

    if sqlite_type != "text":
        return None, False
    if not isinstance(prefix, (bytes, bytearray, memoryview)):
        return None, False
    raw = bytes(prefix)
    overflow = byte_overflow == 1
    candidates = (raw,) if not overflow else tuple(
        raw[: len(raw) - trailing] if trailing else raw
        for trailing in range(4)
        if trailing <= len(raw)
    )
    decoded: str | None = None
    for candidate in candidates:
        try:
            decoded = candidate.decode("utf-8", errors="strict")
            break
        except UnicodeDecodeError as error:
            if (
                not overflow
                or error.end != len(candidate)
                or error.start < max(0, len(candidate) - 4)
            ):
                return None, False
    if decoded is None:
        return None, False
    truncated = overflow or len(decoded) > maximum_code_points
    if truncated:
        if discard_when_truncated:
            return None, True
        return decoded[:maximum_code_points], True
    return decoded, False


def _sensitive_metadata_rows(
    home: Path,
    query: SensitiveInventoryQuery,
) -> SensitiveInventoryListing:
    """Materialize only the separately bounded, explicitly sensitive view."""

    database = home / "state_5.sqlite"
    connection = _state_connection(database)
    try:
        columns = _columns(connection)
        if "id" not in columns or "rollout_path" not in columns:
            raise _error(
                "thread-source-incompatible",
                "Codex threads table does not expose exact ID and rollout "
                "path columns.",
                columns=columns,
            )

        archive_value = (
            """CASE
                WHEN typeof("archived") = 'integer'
                    AND "archived" IN (0, 1)
                THEN "archived"
                ELSE NULL
            END"""
            if "archived" in columns
            else "NULL"
        )
        archive_state = (
            """CASE
                WHEN typeof("archived") = 'integer'
                    AND "archived" = 0 THEN 'active'
                WHEN typeof("archived") = 'integer'
                    AND "archived" = 1 THEN 'archived'
                ELSE 'unknown'
            END"""
            if "archived" in columns
            else "'unknown'"
        )

        def non_negative_integer(column: str) -> str:
            if column not in columns:
                return "NULL"
            return f"""CASE
                WHEN typeof("{column}") = 'integer' AND "{column}" >= 0
                THEN "{column}"
                ELSE NULL
            END"""

        recency_candidates: list[str] = []
        for column in ("recency_at_ms", "updated_at_ms"):
            if column in columns:
                recency_candidates.append(
                    f"""WHEN typeof("{column}") = 'integer'
                        AND "{column}" BETWEEN 0 AND {_MAX_SQLITE_INTEGER}
                    THEN "{column}" """
                )
        if "updated_at" in columns:
            recency_candidates.append(
                f"""WHEN typeof("updated_at") = 'integer'
                    AND "updated_at" BETWEEN 0
                        AND {_MAX_RECENCY_SECONDS}
                    THEN "updated_at" * 1000 """
            )
        recency = (
            "CASE "
            + " ".join(recency_candidates)
            + " ELSE NULL END"
            if recency_candidates
            else "NULL"
        )

        cwd_type, cwd_prefix, cwd_overflow = _sensitive_text_projection(
            columns,
            "cwd",
            MAX_WORKSPACE_CHARS,
        )
        title_type, title_prefix, title_overflow = (
            _sensitive_text_projection(
                columns,
                "title",
                MAX_TITLE_CHARS,
            )
        )
        message_type, message_prefix, message_overflow = (
            _sensitive_text_projection(
                columns,
                "first_user_message",
                MAX_FIRST_MESSAGE_CHARS,
            )
        )

        sql = f"""
            WITH inventory AS (
                SELECT
                    typeof("id") AS id_type,
                    CASE WHEN typeof("id") = 'text'
                        THEN CAST(
                            substr("id", 1, {MAX_THREAD_ID_CHARS + 1})
                            AS BLOB
                        )
                        ELSE NULL
                    END AS id_prefix,
                    CASE WHEN typeof("id") = 'text'
                        THEN instr("id", char(0)) > 0
                        ELSE 0
                    END AS id_has_nul,
                    typeof("rollout_path") AS path_type,
                    CASE WHEN typeof("rollout_path") = 'text'
                        THEN CAST(
                            substr(
                                "rollout_path",
                                1,
                                {MAX_ROLLOUT_PATH_CHARS + 1}
                            ) AS BLOB
                        )
                        ELSE NULL
                    END AS path_prefix,
                    CASE WHEN typeof("rollout_path") = 'text'
                        THEN instr("rollout_path", char(0)) > 0
                        ELSE 0
                    END AS path_has_nul,
                    {archive_value} AS archive_value,
                    {archive_state} AS archive_state,
                    {non_negative_integer("created_at")} AS created_at,
                    {non_negative_integer("updated_at")} AS updated_at,
                    {recency} AS recency,
                    {cwd_type} AS cwd_type,
                    {cwd_prefix} AS cwd_prefix,
                    {cwd_overflow} AS cwd_overflow,
                    {title_type} AS title_type,
                    {title_prefix} AS title_prefix,
                    {title_overflow} AS title_overflow,
                    {message_type} AS message_type,
                    {message_prefix} AS message_prefix,
                    {message_overflow} AS message_overflow,
                    COUNT(*) OVER (
                        PARTITION BY typeof("id"), CAST("id" AS BLOB)
                    ) AS duplicate_count
                FROM threads
            )
            SELECT
                id_type, id_prefix, id_has_nul,
                path_type, path_prefix, path_has_nul,
                archive_value, created_at, updated_at, recency,
                cwd_type, cwd_prefix, cwd_overflow,
                title_type, title_prefix, title_overflow,
                message_type, message_prefix, message_overflow,
                duplicate_count
            FROM inventory
            WHERE ? = 'all' OR archive_state = ?
            ORDER BY
                recency IS NULL ASC,
                recency DESC,
                id_prefix ASC
        """
        archive_filter = query.archive_state.value
        rows = connection.execute(
            sql,
            (archive_filter, archive_filter),
        )
        result: list[SensitiveInventoryRow] = []
        omitted_sources = 0
        inventory_truncated = False
        for row in rows:
            (
                id_type,
                id_prefix,
                id_has_nul,
                path_type,
                path_prefix,
                path_has_nul,
                raw_archive_value,
                created_at,
                updated_at,
                recency_at_ms,
                cwd_type_value,
                cwd_prefix_value,
                cwd_overflow_value,
                title_type_value,
                title_prefix_value,
                title_overflow_value,
                message_type_value,
                message_prefix_value,
                message_overflow_value,
                duplicate_count,
            ) = row
            thread_id = _safe_thread_id(
                id_type,
                id_prefix,
                id_has_nul,
            )
            if thread_id is None or duplicate_count != 1:
                omitted_sources += 1
                continue
            availability = _inventory_source_availability(
                home,
                path_type,
                path_prefix,
                path_has_nul,
            )
            if availability is None:
                omitted_sources += 1
                continue

            if len(result) >= query.limit:
                inventory_truncated = True
                break

            workspace, workspace_truncated = _decode_sensitive_prefix(
                cwd_type_value,
                cwd_prefix_value,
                cwd_overflow_value,
                maximum_code_points=MAX_WORKSPACE_CHARS,
                discard_when_truncated=True,
            )
            title, title_truncated = _decode_sensitive_prefix(
                title_type_value,
                title_prefix_value,
                title_overflow_value,
                maximum_code_points=MAX_TITLE_CHARS,
                discard_when_truncated=False,
            )
            first_message, first_message_truncated = (
                _decode_sensitive_prefix(
                    message_type_value,
                    message_prefix_value,
                    message_overflow_value,
                    maximum_code_points=MAX_FIRST_MESSAGE_CHARS,
                    discard_when_truncated=False,
                )
            )
            result.append(
                SensitiveInventoryRow(
                    provider_id="codex",
                    thread_id=thread_id,
                    archive_state=_archive_state(raw_archive_value),
                    source_availability=availability,
                    workspace=workspace,
                    title=title,
                    first_user_message=first_message,
                    workspace_truncated=workspace_truncated,
                    title_truncated=title_truncated,
                    first_user_message_truncated=(
                        first_message_truncated
                    ),
                    created_at=(
                        None
                        if created_at is None
                        else str(created_at)
                    ),
                    updated_at=(
                        None
                        if updated_at is None
                        else str(updated_at)
                    ),
                    recency_at_ms=recency_at_ms,
                )
            )
        return SensitiveInventoryListing(
            tuple(result),
            inventory_truncated=inventory_truncated,
            omitted_sources=omitted_sources,
        )
    except SvcError:
        raise
    except sqlite3.DatabaseError as exc:
        raise _error(
            "thread-source-incompatible",
            "Codex state database sensitive metadata cannot be read.",
            path=str(database),
            reason=str(exc),
        ) from exc
    finally:
        connection.close()


def _extract_thread_id(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("thread_id", "threadId", "session_id", "sessionId", "id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _is_envelope(value: object) -> bool:
    return isinstance(value, dict) and isinstance(value.get("type"), str) and "payload" in value and "timestamp" in value


def _signature(path: Path) -> str:
    stream, _ = _open_source(path)
    found_id: str | None = None
    try:
        while True:
            line = _readline(stream, MAX_INDEX_RECORD_BYTES + 1, path)
            if not line:
                break
            if len(line) > MAX_INDEX_RECORD_BYTES:
                while not line.endswith(b"\n"):
                    line = _readline(stream, MAX_INDEX_RECORD_BYTES + 1, path)
                    if not line:
                        break
                continue
            try:
                value = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not _is_envelope(value):
                continue
            if value.get("type") == "session_meta":
                candidate = _extract_thread_id(value.get("payload"))
                if candidate:
                    if found_id is not None and candidate != found_id:
                        raise _error(
                            "thread-source-incompatible",
                            "Source contains conflicting session metadata thread IDs.",
                            path=str(path),
                            thread_ids=(found_id, candidate),
                        )
                    found_id = candidate
    finally:
        stream.close()
    if found_id:
        return found_id
    raise _error("thread-source-incompatible", "Source is not a compatible rollout-v1 JSONL snapshot.", path=str(path))


class CodexRolloutProvider:
    """Static ``codex-rollout-v1`` provider implementation."""

    provider_id = "codex"

    def list_inventory(
        self,
        context: ProviderContext,
        query: ThreadInventoryQuery,
    ) -> ThreadInventoryListing:
        if not isinstance(query, ThreadInventoryQuery):
            raise _error("invalid-inventory-query", "Thread inventory query is invalid.")
        home = _home(context)
        return _metadata_rows(home, query)

    def list_sensitive_inventory(
        self,
        context: ProviderContext,
        query: SensitiveInventoryQuery,
    ) -> SensitiveInventoryListing:
        if not isinstance(query, SensitiveInventoryQuery):
            raise _error(
                "invalid-inventory-query",
                "Sensitive thread inventory query is invalid.",
            )
        return _sensitive_metadata_rows(_home(context), query)

    def resolve(self, context: ProviderContext, selection: ThreadSelection) -> ResolvedThread:
        home = _home(context)
        if selection.source is not None:
            source = Path(selection.source).expanduser()
            thread_id = _signature(source)
        else:
            assert selection.thread_id is not None
            connection = _state_connection(home / "state_5.sqlite")
            try:
                columns = _columns(connection)
                id_column = _pick(columns, ("thread_id", "threadId", "id", "uuid"))
                source_column = _pick(columns, ("rollout_path", "rolloutPath", "source_path", "sourcePath", "rollout", "path"))
                state_column = _pick(columns, ("source_state", "sourceState", "state", "status", "archived"))
                if id_column is None or source_column is None:
                    raise _error("thread-source-incompatible", "Codex threads table does not expose exact ID and rollout path columns.", columns=columns)
                query = f'SELECT "{id_column.replace(chr(34), chr(34) * 2)}", "{source_column.replace(chr(34), chr(34) * 2)}"' + (f', "{state_column.replace(chr(34), chr(34) * 2)}"' if state_column else '') + f' FROM threads WHERE "{id_column.replace(chr(34), chr(34) * 2)}" = ? LIMIT 1'
                row = connection.execute(query, (selection.thread_id,)).fetchone()
                if row is None:
                    raise _error("thread-not-found", "No exact Codex thread ID is present in the state database.", thread_id=selection.thread_id)
                source = _resolve_path(home, row[1])
                state_value = row[2] if state_column else None
            except SvcError:
                raise
            except sqlite3.DatabaseError as exc:
                raise _error("thread-source-incompatible", "Codex state database cannot resolve the selected thread.", thread_id=selection.thread_id, reason=str(exc)) from exc
            finally:
                connection.close()
            discovered_id = _signature(source)
            if discovered_id != selection.thread_id:
                raise _error("thread-source-incompatible", "Rollout source identity does not match the selected thread ID.", thread_id=selection.thread_id)
            thread_id = selection.thread_id
        _lstat_regular(source, what="rollout source")
        return ResolvedThread(
            provider_id=self.provider_id,
            adapter_id=_ADAPTER_ID,
            source_format=_SOURCE_FORMAT,
            thread_id=thread_id,
            source_path=source,
        )

    def stream_normalize(
        self,
        resolved: ResolvedThread,
        sink: NormalizedRecordSink,
        bounds: Mapping[str, int] | None = None,
    ) -> NormalizationResult:
        """Normalize one descriptor-bound rollout through a core-owned sink."""
        if resolved.provider_id != self.provider_id or resolved.source_format != _SOURCE_FORMAT:
            raise _error("thread-source-incompatible", "Resolved source does not belong to codex-rollout-v1.")
        source = Path(resolved.source_path)
        stream, initial_info = _open_source(source)
        initial = _source_snapshot(initial_info)
        final: SourceSnapshot | None = None
        try:
            result = CodexTrajectoryNormalizer().normalize(
                stream,
                resolved,
                sink,
                bounds or DEFAULT_BOUNDS,
                initial,
            )
            final = _source_snapshot(os.fstat(stream.fileno()))
        except OSError as error:
            raise _error("thread-source-unreadable", "Codex rollout source cannot be read.") from error
        finally:
            stream.close()
        try:
            post_info = _lstat_regular(source, what="rollout source")
            post = _source_snapshot(post_info)
        except SvcError as error:
            lossiness = {name: dict(values) for name, values in result.lossiness.items()}
            lossiness["partial_reasons"]["source_displaced"] += 1
            result = replace(
                result,
                source_status=SourceStatus.DISPLACED,
                result_status=NormalizationStatus.PARTIAL,
                source_snapshot=initial,
                final_snapshot=final,
                lossiness=lossiness,
            )
            return replace(result, diagnostics=tuple(result.diagnostics) + ({"code": "source-displaced-during-collection", "severity": "warning", "action": "partial", "count": 1, "record_ref": None, "source_ref": None, "details": {"source_status": "displaced"}},))
        assert final is not None
        status = SourceStatus.STABLE
        partial_reason: str | None = None
        if post != final or post.device != initial.device or post.inode != initial.inode:
            status = SourceStatus.DISPLACED
            partial_reason = "source_displaced"
        elif final.size < initial.size or (final.size == initial.size and final.mtime_ns != initial.mtime_ns):
            status = SourceStatus.CHANGED
            partial_reason = "source_changed"
        elif final.size > initial.size:
            status = SourceStatus.GREW
            partial_reason = "source_grew"
        if partial_reason is not None:
            lossiness = {name: dict(values) for name, values in result.lossiness.items()}
            lossiness["partial_reasons"][partial_reason] += 1
            result = replace(result, lossiness=lossiness, diagnostics=tuple(result.diagnostics) + ({"code": f"source-{status.value}-during-collection", "severity": "warning", "action": "partial", "count": 1, "record_ref": None, "source_ref": None, "details": {"source_status": status.value}},))
            result = replace(result, result_status=NormalizationStatus.PARTIAL)
        return replace(result, source_status=status, source_snapshot=initial, final_snapshot=final)

__all__ = ["CodexRolloutProvider"]
