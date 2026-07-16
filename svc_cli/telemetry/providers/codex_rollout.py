"""Read-only adapter for Codex ``rollout-v1`` JSONL snapshots.

The adapter intentionally treats the source JSONL as the authority.  It does
not launch Codex, inspect editor caches, or attempt to interpret provider
payloads beyond the small amount of metadata needed for indexing.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import tempfile
from pathlib import Path
from typing import BinaryIO, Iterable
from ...errors import SvcError
from ..agent_threads import (
    CaptureEvidence,
    CaptureWarning,
    ProviderContext,
    ResolvedThread,
    SourceArtifact,
    SourceSnapshot,
    TextOccurrence,
    ThreadDescriptor,
    ThreadSelection,
)


MAX_INDEX_RECORD_BYTES = 4 * 1024 * 1024
MAX_CAPTURE_WARNINGS = 256
MAX_OCCURRENCES = 2048
MAX_TASK_CANDIDATE_CHARS = 4096
_SOURCE_FORMAT = "rollout-v1"
_ADAPTER_ID = "codex-rollout-v1"
_ARCHIVE_PATH = "rollout.jsonl"
_TASK_PATH_RE = re.compile(r'(?<![\w./-])/?tasks/[^\s\x00<>"\'`\[\]{}()\\]+', re.UNICODE)
_TRAILING_PUNCTUATION = ".,;:!?)]}>\"'。！？；：）】》」』、"


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
    except OSError as exc:
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


def _source_state(path: Path, value: object | None = None) -> str:
    if isinstance(value, bool):
        return "archived" if value else "active"
    if isinstance(value, int) and value in (0, 1):
        return "archived" if value else "active"
    if isinstance(value, str) and value.strip():
        lowered = value.strip().lower()
        if lowered in {"active", "archived", "missing"}:
            return lowered
    parts = {part.lower() for part in path.parts}
    return "archived" if any("archiv" in part for part in parts) else "active"


def _resolve_path(home: Path, value: object) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise _error("thread-source-incompatible", "State database has no usable rollout path.")
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = home / candidate
    try:
        candidate_resolved = candidate.resolve()
        home_resolved = home.expanduser().resolve()
        if not candidate_resolved.is_relative_to(home_resolved):
            raise _error("thread-source-unsafe", "State database rollout path escapes CODEX_HOME.", path=str(candidate), home=str(home))
    except (OSError, RuntimeError) as exc:
        raise _error("thread-source-unsafe", "State database rollout path cannot be safely resolved.", path=str(candidate), reason=str(exc)) from exc
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
    try:
        connection = sqlite3.connect(snapshot)
        connection.execute("PRAGMA query_only=ON")
        table = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='threads'").fetchone()
        if table is None:
            connection.close()
            shutil.rmtree(directory, ignore_errors=True)
            raise _error("thread-source-incompatible", "Codex state database has no compatible threads table.", path=str(path))
        return _SnapshotConnection(connection, directory)
    except SvcError:
        raise
    except sqlite3.DatabaseError as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise _error("thread-source-incompatible", "Codex state database is not a readable SQLite database.", path=str(path), reason=str(exc)) from exc


def _metadata_rows(home: Path, limit: int) -> tuple[ThreadDescriptor, ...]:
    database = home / "state_5.sqlite"
    connection = _state_connection(database)
    try:
        columns = _columns(connection)
        id_column = _pick(columns, ("thread_id", "threadId", "id", "uuid"))
        source_column = _pick(columns, ("rollout_path", "rolloutPath", "source_path", "sourcePath", "rollout", "path"))
        if id_column is None or source_column is None:
            raise _error("thread-source-incompatible", "Codex threads table does not expose exact ID and rollout path columns.", columns=columns)
        created_column = _pick(columns, ("created_at", "createdAt", "created"))
        updated_column = _pick(columns, ("updated_at", "updatedAt", "updated"))
        state_column = _pick(columns, ("source_state", "sourceState", "state", "status", "archived"))
        selected = [id_column, source_column]
        for column in (created_column, updated_column, state_column):
            if column is not None:
                selected.append(column)
        projection = ", ".join('"' + column.replace('"', '""') + '"' for column in selected)
        order = ('"' + updated_column.replace('"', '""') + '" DESC') if updated_column else 'rowid DESC'
        rows = connection.execute(f"SELECT {projection} FROM threads ORDER BY {order} LIMIT ?", (limit,)).fetchall()
        result: list[ThreadDescriptor] = []
        for row in rows:
            values = dict(zip(selected, row))
            thread_id = values.get(id_column)
            if not isinstance(thread_id, str) or not thread_id.strip():
                continue
            source = _resolve_path(home, values.get(source_column))
            try:
                _lstat_regular(source, what="rollout source")
            except SvcError as error:
                if error.code != "thread-source-not-found":
                    raise
                source_state = "missing"
            else:
                source_state = _source_state(source, values.get(state_column) if state_column else None)
            result.append(ThreadDescriptor(
                provider_id="codex",
                thread_id=thread_id,
                source_state=source_state,
                created_at=None if values.get(created_column) is None else str(values.get(created_column)),
                updated_at=None if values.get(updated_column) is None else str(values.get(updated_column)),
            ))
        return tuple(result)
    except SvcError:
        raise
    except sqlite3.DatabaseError as exc:
        raise _error("thread-source-incompatible", "Codex state database metadata cannot be read.", path=str(database), reason=str(exc)) from exc
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


def _role_and_base(payload: object) -> tuple[str | None, dict[str, object] | None, str]:
    if not isinstance(payload, dict):
        return None, None, "payload"
    role = payload.get("role")
    if isinstance(role, str):
        return role.lower(), payload, "payload"
    for key in ("message", "item"):
        nested = payload.get(key)
        if isinstance(nested, dict) and isinstance(nested.get("role"), str):
            return str(nested["role"]).lower(), nested, f"payload.{key}"
    marker = str(payload.get("type", "")).lower()
    if marker.startswith("user_"):
        return "user", payload, "payload"
    if marker.startswith(("assistant_", "agent_")):
        return "assistant", payload, "payload"
    return None, None, "payload"


def _walk_text(value: object, path: str) -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        if value:
            yield value, path
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_text(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        if isinstance(value.get("text"), str):
            yield value["text"], f"{path}.text"
        elif isinstance(value.get("value"), str) and str(value.get("type", "")).lower() in {"text", "input_text", "output_text"}:
            yield value["value"], f"{path}.value"
        elif "content" in value:
            yield from _walk_text(value["content"], f"{path}.content")


def _occurrences(
    payload: object, role: str | None, base: str, line_no: int, record_type: str
) -> tuple[list[TextOccurrence], tuple[tuple[int, str], ...]]:
    if role not in {"user", "assistant"} or not isinstance(payload, dict):
        return [], ()
    if "content" in payload:
        values = payload["content"]
        values_path = f"{base}.content"
    elif "text" in payload:
        values = payload["text"]
        values_path = f"{base}.text"
    elif isinstance(payload.get("message"), str):
        values = payload["message"]
        values_path = f"{base}.message"
    else:
        return [], ()
    occurrences: list[TextOccurrence] = []
    oversized: list[tuple[int, str]] = []
    for text, suffix in _walk_text(values, values_path):
        for match in _TASK_PATH_RE.finditer(text):
            candidate = match.group(0).rstrip(_TRAILING_PUNCTUATION)
            if not candidate:
                continue
            if len(candidate) > MAX_TASK_CANDIDATE_CHARS:
                oversized.append((len(candidate), suffix))
                continue
            occurrences.append(TextOccurrence(text=candidate, source_line=line_no, record_type=record_type, role=role, field_path=suffix))
    return occurrences, tuple(oversized)


def _classify(record_type: str, payload: object) -> str | None:
    lowered = record_type.lower()
    inner = ""
    if isinstance(payload, dict) and isinstance(payload.get("type"), str):
        inner = str(payload["type"]).lower()
    combined = f"{lowered}:{inner}"
    if "reason" in combined:
        return "reasoning"
    if any(token in combined for token in ("tool", "function_call", "functioncall", "function_output", "custom_tool")):
        return "tool_calls"
    role, _, _ = _role_and_base(payload)
    if "message" in combined or role in {"user", "assistant", "system", "developer"}:
        return "messages"
    if "attachment" in combined or (isinstance(payload, dict) and "attachments" in payload):
        return "attachments"
    return None


def _reasoning_opaque(payload: object) -> bool:
    if isinstance(payload, dict):
        if any(key.lower() in {"encrypted", "encrypted_content", "encrypted_reasoning", "ciphertext", "opaque"} for key in payload):
            return True
        return any(_reasoning_opaque(value) for value in payload.values())
    if isinstance(payload, list):
        return any(_reasoning_opaque(value) for value in payload)
    return False


class CodexRolloutProvider:
    """Static ``codex-rollout-v1`` provider implementation."""

    provider_id = "codex"

    def list_metadata(self, context: ProviderContext, limit: int) -> tuple[ThreadDescriptor, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise _error("invalid-limit", "Thread metadata limit must be a positive integer.", limit=limit)
        home = _home(context)
        return _metadata_rows(home, limit)

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
            source_state=_source_state(source, locals().get("state_value")),
            artifact=SourceArtifact(source_path=source, archive_path=_ARCHIVE_PATH, media_type="application/x-ndjson"),
        )

    def stream_capture(self, resolved: ResolvedThread, raw_output: BinaryIO, index_output: BinaryIO) -> CaptureEvidence:
        if resolved.provider_id != self.provider_id or resolved.source_format != _SOURCE_FORMAT:
            raise _error("thread-source-incompatible", "Resolved source does not belong to codex-rollout-v1.")
        source = Path(resolved.artifact.source_path)
        stream, initial = _open_source(source)
        digest = hashlib.sha256()
        source_bytes = 0
        counts: dict[str, int] = {}
        warnings: list[CaptureWarning] = []
        suppressed_warnings = 0
        occurrences: list[TextOccurrence] = []
        suppressed_occurrences = 0
        capabilities: dict[str, str] = {"messages": "absent", "reasoning": "absent", "tool_calls": "absent", "attachments": "absent"}
        last_nonempty: tuple[str, int] | None = None
        session_id: str | None = None
        too_large_unterminated = False
        index_output.write(("{\"schema_version\":1,\"source_format\":\"%s\",\"thread_id\":%s,\"records\":[" % (_SOURCE_FORMAT, json.dumps(resolved.thread_id, ensure_ascii=False))).encode("utf-8"))
        first_index_record = True

        def add_index_record(record: dict[str, object]) -> None:
            nonlocal first_index_record
            if not first_index_record:
                index_output.write(b",")
            index_output.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            first_index_record = False

        def add_warning(warning: CaptureWarning) -> None:
            nonlocal suppressed_warnings
            if len(warnings) < MAX_CAPTURE_WARNINGS:
                warnings.append(warning)
            else:
                suppressed_warnings += 1

        def retain_occurrences(values: list[TextOccurrence]) -> None:
            nonlocal suppressed_occurrences
            available = max(0, MAX_OCCURRENCES - len(occurrences))
            occurrences.extend(values[:available])
            suppressed_occurrences += max(0, len(values) - available)

        try:
            line_no = 0
            while True:
                first = _readline(stream, MAX_INDEX_RECORD_BYTES + 1, source)
                if not first:
                    break
                line_no += 1
                raw_output.write(first)
                digest.update(first)
                source_bytes += len(first)
                line_digest = hashlib.sha256(first)
                too_large = len(first) > MAX_INDEX_RECORD_BYTES
                if too_large:
                    total = len(first)
                    chunk = first
                    while not chunk.endswith(b"\n"):
                        chunk = _readline(stream, MAX_INDEX_RECORD_BYTES + 1, source)
                        if not chunk:
                            break
                        raw_output.write(chunk)
                        digest.update(chunk)
                        line_digest.update(chunk)
                        source_bytes += len(chunk)
                        total += len(chunk)
                    if not chunk:
                        too_large_unterminated = True
                    add_warning(CaptureWarning("record-too-large", {"line": line_no, "bytes": total, "analysis_unavailable": "task-references-and-index"}))
                    add_index_record({"line": line_no, "bytes": total, "sha256": line_digest.hexdigest(), "type": "oversize"})
                    last_nonempty = ("oversize", line_no)
                    continue
                stripped = first.rstrip(b"\r\n")
                if not stripped.strip():
                    add_index_record({"line": line_no, "bytes": len(first), "sha256": hashlib.sha256(first).hexdigest(), "type": "blank"})
                    continue
                try:
                    decoded = stripped.decode("utf-8")
                    value = json.loads(decoded)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    add_warning(CaptureWarning("malformed-record", {"line": line_no, "reason": type(exc).__name__}))
                    add_index_record({"line": line_no, "bytes": len(first), "sha256": hashlib.sha256(first).hexdigest(), "type": "malformed"})
                    counts["malformed"] = counts.get("malformed", 0) + 1
                    last_nonempty = ("malformed", line_no)
                    continue
                if not _is_envelope(value):
                    add_warning(CaptureWarning("malformed-record", {"line": line_no, "reason": "envelope"}))
                    add_index_record({"line": line_no, "bytes": len(first), "sha256": hashlib.sha256(first).hexdigest(), "type": "malformed"})
                    counts["malformed"] = counts.get("malformed", 0) + 1
                    last_nonempty = ("malformed", line_no)
                    continue
                record_type = str(value["type"])
                payload = value.get("payload")
                counts[record_type] = counts.get(record_type, 0) + 1
                add_index_record({"line": line_no, "bytes": len(first), "sha256": hashlib.sha256(first).hexdigest(), "type": record_type, "timestamp": value.get("timestamp")})
                last_nonempty = ("valid", line_no)
                if record_type == "session_meta":
                    candidate = _extract_thread_id(payload)
                    if candidate:
                        if session_id is not None and candidate != session_id:
                            raise _error(
                                "thread-source-incompatible",
                                "Source contains conflicting session metadata thread IDs.",
                                path=str(source),
                                thread_ids=(session_id, candidate),
                            )
                        session_id = candidate
                category = _classify(record_type, payload)
                if category == "messages":
                    capabilities["messages"] = "present"
                    role, base, path = _role_and_base(payload)
                    values, oversized = _occurrences(base if base is not None else payload, role, path, line_no, record_type)
                    for candidate_chars, field_path in oversized:
                        add_warning(CaptureWarning("task-candidate-too-long", {
                            "line": line_no,
                            "record_type": record_type,
                            "field_path": field_path,
                            "candidate_chars": candidate_chars,
                            "max_chars": MAX_TASK_CANDIDATE_CHARS,
                        }))
                    retain_occurrences(values)
                elif category == "reasoning":
                    if _reasoning_opaque(payload):
                        capabilities["reasoning"] = "opaque"
                    elif capabilities["reasoning"] != "opaque":
                        capabilities["reasoning"] = "summary"
                elif category == "tool_calls":
                    capabilities["tool_calls"] = "present"
                elif category == "attachments":
                    capabilities["attachments"] = "present"
            final = os.fstat(stream.fileno())
        finally:
            stream.close()
        if _source_snapshot(initial) != _source_snapshot(final):
            raise _error("thread-source-mutated", "Codex rollout source changed during capture.", path=str(source))
        try:
            post = _lstat_regular(source, what="rollout source")
        except SvcError as error:
            raise _error("thread-source-mutated", "Codex rollout source disappeared or became unsafe after capture.", path=str(source)) from error
        if _source_snapshot(post) != _source_snapshot(final):
            raise _error("thread-source-mutated", "Codex rollout source changed after capture.", path=str(source))
        if too_large_unterminated:
            raise _error("thread-source-mutated", "Codex rollout source ended with an oversized unterminated record.", path=str(source), line=last_nonempty[1] if last_nonempty else None)
        if last_nonempty and last_nonempty[0] == "malformed":
            raise _error("thread-source-mutated", "Codex rollout source ended with a malformed record.", path=str(source), line=last_nonempty[1])
        if session_id is None:
            raise _error("thread-source-incompatible", "Source is not a compatible rollout-v1 JSONL snapshot.", path=str(source))
        if session_id != resolved.thread_id:
            raise _error("thread-source-incompatible", "Rollout source identity changed during capture.", thread_id=resolved.thread_id)
        if suppressed_warnings:
            warnings.append(CaptureWarning("warnings-truncated", {"suppressed": suppressed_warnings}))
        if suppressed_occurrences:
            warnings.append(CaptureWarning("occurrences-truncated", {"suppressed": suppressed_occurrences, "analysis_unavailable": "task-references"}))
        warning_values = [warning.as_dict() for warning in warnings]
        index_output.write(("],\"source_sha256\":%s,\"source_bytes\":%d,\"warnings\":%s}" % (json.dumps(digest.hexdigest()), source_bytes, json.dumps(warning_values, ensure_ascii=False, sort_keys=True, separators=(",", ":")))).encode("utf-8"))
        return CaptureEvidence(
            source_sha256=digest.hexdigest(),
            source_bytes=source_bytes,
            record_counts=counts,
            capabilities=capabilities,
            occurrences=tuple(occurrences),
            warnings=tuple(warnings),
            source_snapshot=_source_snapshot(final),
        )


__all__ = ["CodexRolloutProvider"]
