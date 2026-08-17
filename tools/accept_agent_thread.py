"""Black-box acceptance harness for the installed Agent-thread surface.

This module intentionally uses only the Python standard library.  It validates
one exact wheel digest, installs that wheel into a throw-away virtualenv with
network access disabled, and exercises the installed CLI from a temporary cwd.
No project module is imported by the harness itself.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Mapping, Never, Sequence

try:
    import venv
except ImportError:  # pragma: no cover
    venv = None  # type: ignore[assignment]


HARNESS_VERSION = "2"
SLICE_CHOICES = ("inventory", "evidence", "query", "read", "all")
_MAX_CHILD_OUTPUT_BYTES = 2 * 1024 * 1024
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_EVIDENCE_ID_RE = re.compile(r"^[0-9a-f]{64}$")
_EVIDENCE_CORE_MEMBERS = {
    "manifest.json",
    "native.bin",
    "native-index.jsonl",
}
_EVIDENCE_OPTIONAL_MEMBERS = {"trajectory.jsonl"}
_EVIDENCE_ID_DOMAIN = b"svc-agent-thread-evidence-id\x00v3\x00"
_BLOCKED_WHEEL_PARTS = {"tasks", "textual", "tui"}
_RAW_EVIDENCE_SUFFIXES = {".bin", ".db", ".jsonl", ".ndjson", ".sqlite", ".zip"}
_BLOCKED_DEPENDENCIES = {"textual"}
_REQUIRES_DIST_RE = re.compile(r"^Requires-Dist:\s*([A-Za-z0-9_.-]+)", re.IGNORECASE | re.MULTILINE)
_REMOVED_MODULES = (
    "svc_cli.telemetry.analysis",
    "svc_cli.telemetry.navigation",
    "svc_cli.telemetry.tui",
)
_REMOVED_PATH_PREFIXES = tuple(module.replace(".", "/") for module in _REMOVED_MODULES)
_ALLOWED_DISTRIBUTIONS = {
    "sustainable-vibe-coding",
    "pydantic",
    "pydantic-core",
    "annotated-types",
    "typing-extensions",
    "typing-inspection",
    "platformdirs",
    "filelock",
    "jsonpatch",
    "jsonpointer",
    "python-dotenv",
    "semantic-version",
    "urllib3",
    "pip",
    "setuptools",
}
_SOURCE_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_PROBE = """\
import importlib.util
import json
from pathlib import Path
import sys

source_root = Path(sys.argv[1]).resolve()
module_file = Path(__import__("svc_cli").__file__).resolve()
removed = []
for name in %r:
    try:
        if importlib.util.find_spec(name) is not None:
            removed.append(name)
    except (ImportError, ModuleNotFoundError, ValueError):
        pass
print(json.dumps({
    "module": module_file.as_posix(),
    "leaked": source_root == module_file or source_root in module_file.parents,
    "removed": removed,
    "textual": importlib.util.find_spec("textual") is not None,
}, sort_keys=True, separators=(",", ":")))
""" % (_REMOVED_MODULES,)


class HarnessError(Exception):
    """Stable harness failure with a process-level exit code."""

    def __init__(self, exit_code: int, reason: str) -> None:
        super().__init__(reason)
        self.exit_code = exit_code
        self.reason = reason


class _CaseFailure(Exception):
    pass


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> Never:  # pragma: no cover
        raise HarnessError(2, "arguments")


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        prog="accept_agent_thread",
        description="Run installed Agent-thread acceptance slices.",
    )
    parser.add_argument("--slice", choices=SLICE_CHOICES, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    return parser


def _require_path(path: Path, *, directory: bool = False) -> None:
    valid = path.is_dir() if directory else path.is_file()
    if not valid:
        raise HarnessError(4, "wheel-validation")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise HarnessError(4, "wheel-validation") from error
    return digest.hexdigest()


def _validate_wheel_contents(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise HarnessError(4, "wheel-validation")
            for name in names:
                if not name or "\\" in name or name.startswith("/") or any(part in {"", ".", ".."} for part in name.split("/")):
                    raise HarnessError(4, "wheel-validation")
                parts = {part.lower() for part in name.split("/")}
                if parts & _BLOCKED_WHEEL_PARTS or Path(name).suffix.lower() in _RAW_EVIDENCE_SUFFIXES:
                    raise HarnessError(4, "wheel-validation")
            if any(
                any(name == prefix + ".py" or name.startswith(prefix + "/") for prefix in _REMOVED_PATH_PREFIXES)
                for name in names
            ):
                raise HarnessError(4, "wheel-validation")
            metadata_members = [name for name in names if name.endswith(".dist-info/METADATA")]
            if not metadata_members:
                raise HarnessError(4, "wheel-validation")
            for member in metadata_members:
                metadata = archive.read(member)
                if len(metadata) > 1_048_576:
                    raise HarnessError(4, "wheel-validation")
                text = metadata.decode("utf-8", "strict")
                dependencies = {
                    dependency.lower().replace("_", "-")
                    for dependency in _REQUIRES_DIST_RE.findall(text)
                }
                if dependencies & _BLOCKED_DEPENDENCIES:
                    raise HarnessError(4, "wheel-validation")
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile) as error:
        raise HarnessError(4, "wheel-validation") from error


def _validate_inputs(wheel: Path, expected: str, wheelhouse: Path) -> str:
    if _SHA256_RE.fullmatch(expected) is None:
        raise HarnessError(4, "wheel-validation")
    _require_path(wheel)
    if wheel.suffix.lower() != ".whl":
        raise HarnessError(4, "wheel-validation")
    digest = _sha256_file(wheel)
    if digest != expected.lower():
        raise HarnessError(4, "wheel-validation")
    _validate_wheel_contents(wheel)
    _require_path(wheelhouse, directory=True)
    try:
        entries = tuple(wheelhouse.iterdir())
    except OSError as error:
        raise HarnessError(4, "wheel-validation") from error
    for entry in entries:
        _require_path(entry)
        if entry.suffix.lower() != ".whl":
            raise HarnessError(4, "wheel-validation")
        _validate_wheel_contents(entry)
    return digest


def _stage_wheel(source: Path, digest: str, root: Path) -> Path:
    _require_path(source)
    destination = root / source.name
    actual = hashlib.sha256()
    try:
        with source.open("rb") as source_stream:
            with destination.open("xb") as target:
                for chunk in iter(lambda: source_stream.read(1024 * 1024), b""):
                    actual.update(chunk)
                    target.write(chunk)
        if actual.hexdigest() != digest:
            raise HarnessError(4, "wheel-validation")
        if _sha256_file(destination) != digest:
            raise HarnessError(4, "wheel-validation")
        return destination
    except HarnessError:
        destination.unlink(missing_ok=True)
        raise
    except OSError as error:
        destination.unlink(missing_ok=True)
        raise HarnessError(4, "wheel-validation") from error


def _command(
    args: Sequence[str | os.PathLike[str]],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [os.fspath(value) for value in args],
            cwd=os.fspath(cwd) if cwd is not None else None,
            env=dict(env) if env is not None else None,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise HarnessError(5, "child") from error


def _environment(root: Path) -> dict[str, str]:
    value = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL", "PIP_FIND_LINKS"):
        value.pop(key, None)
    tmp = root / "tmp"
    tmp.mkdir()
    value.update(
        {
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
            "PYTHONNOUSERSITE": "1",
            "PIP_CACHE_DIR": os.fspath(root / "pip-cache"),
            "TMPDIR": os.fspath(tmp),
            "TMP": os.fspath(tmp),
            "TEMP": os.fspath(tmp),
        }
    )
    return value


def _child_python(directory: Path) -> Path:
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _create_venv(root: Path) -> Path:
    if venv is None:
        raise HarnessError(3, "venv")
    directory = root / "venv"
    try:
        venv.EnvBuilder(with_pip=True, clear=True).create(directory)
    except (OSError, RuntimeError) as error:
        raise HarnessError(3, "venv") from error
    child = _child_python(directory)
    _require_path(child)
    return child


def _install(child: Path, wheel: Path, wheelhouse: Path, root: Path, environment: Mapping[str, str]) -> None:
    result = _command(
        (child, "-m", "pip", "install", "--no-index", "--find-links", wheelhouse, wheel),
        cwd=root,
        env=environment,
    )
    if result.returncode != 0 or len((result.stdout + result.stderr).encode("utf-8", "replace")) > _MAX_CHILD_OUTPUT_BYTES:
        raise HarnessError(5, "install")


def _installed_versions(child: Path, root: Path, environment: Mapping[str, str]) -> dict[str, str]:
    code = """import importlib.metadata as m,json
out={}
for d in m.distributions():
    name=d.metadata.get('Name')
    if isinstance(name,str): out[name.lower().replace('_','-')]=d.version
print(json.dumps(out,sort_keys=True))
"""
    result = _command((child, "-c", code), cwd=root, env=environment)
    _bounded_output(result, "install")
    if result.returncode != 0:
        raise HarnessError(5, "install")
    try:
        payload = json.loads(result.stdout)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise HarnessError(5, "install") from error
    if not isinstance(payload, dict) or set(payload) - _ALLOWED_DISTRIBUTIONS or "sustainable-vibe-coding" not in payload:
        raise HarnessError(5, "install")
    if any(not isinstance(key, str) or not isinstance(value, str) or len(value) > 64 for key, value in payload.items()):
        raise HarnessError(5, "install")
    return {key: payload[key] for key in sorted(payload)}


def _bounded_output(result: subprocess.CompletedProcess[str], failure: str) -> str:
    if not isinstance(result.stdout, str) or not isinstance(result.stderr, str):
        raise _CaseFailure(failure)
    combined = result.stdout + "\n" + result.stderr
    try:
        size = len(combined.encode("utf-8", "strict"))
    except UnicodeEncodeError as error:
        raise _CaseFailure(failure) from error
    if size > _MAX_CHILD_OUTPUT_BYTES:
        raise _CaseFailure(failure)
    return combined


def _json(value: bytes | str, failure: str) -> object:
    try:
        text = value.decode("utf-8", "strict") if isinstance(value, bytes) else value

        def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
            output: dict[str, object] = {}
            for key, item in items:
                if key in output:
                    raise ValueError("duplicate key")
                output[key] = item
            return output

        return json.loads(text, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("constant")))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise _CaseFailure(failure) from error


def _run_cli(child: Path, args: Sequence[str | os.PathLike[str]], root: Path, env: Mapping[str, str], *, expect: int = 0) -> dict[str, Any]:
    result = _command((child, "-m", "svc_cli.cli", *args), cwd=root, env=env)
    _bounded_output(result, "cli-output")
    if result.returncode != expect:
        raise _CaseFailure("cli-output")
    stream = result.stdout if expect == 0 else result.stderr
    payload = _json(stream, "cli-json")
    if not isinstance(payload, dict):
        raise _CaseFailure("cli-json")
    return payload


def _run_source_probe(child: Path, root: Path, env: Mapping[str, str]) -> None:
    result = _command((child, "-c", _SOURCE_PROBE, _SOURCE_ROOT), cwd=root, env=env)
    _bounded_output(result, "source-isolation")
    if result.returncode != 0:
        raise _CaseFailure("source-isolation")
    payload = _json(result.stdout, "source-isolation")
    if not isinstance(payload, Mapping) or payload.get("leaked") or payload.get("removed") or payload.get("textual"):
        raise _CaseFailure("source-isolation")


def _envelope(kind: str, payload: Mapping[str, object], timestamp: str) -> bytes:
    return _canonical({"timestamp": timestamp, "type": kind, "payload": dict(payload)}, newline=True)


def _canonical(value: object, *, newline: bool = False) -> bytes:
    try:
        data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise _CaseFailure("fixture-json") from error
    return data + (b"\n" if newline else b"")


def _create_inventory_fixture(root: Path) -> Path:
    home = root / "inventory-fixture" / "codex-home"
    home.mkdir(parents=True)
    body = b'{"type":"session_meta","payload":{"id":"accept-thread"}}\n'
    (home / "active.jsonl").write_bytes(body)
    (home / "archived.jsonl").write_bytes(body)
    connection = sqlite3.connect(home / "state_5.sqlite")
    try:
        connection.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT, archived INTEGER, created_at INTEGER, updated_at INTEGER, recency_at_ms INTEGER, cwd TEXT, title TEXT, first_user_message TEXT)")
        rows = (
            ("inv-active", "active.jsonl", 0, 1, 300, 3000),
            ("inv-archived", "archived.jsonl", 1, 1, 200, 2000),
            ("inv-missing", "missing.jsonl", 1, 1, 250, 2500),
            ("inv-unknown", "unknown.jsonl", None, None, 100, 1000),
            ("inv\x00unsafe", "active.jsonl", 0, 1, 50, 500),
        )
        connection.executemany(
            "INSERT INTO threads (id, rollout_path, archived, created_at, updated_at, recency_at_ms, cwd, title, first_user_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [row + ("/workspace/acceptance", "Inspect parser", "Start parser work") for row in rows],
        )
        connection.commit()
    finally:
        connection.close()
    return home


def _create_source_fixture(root: Path) -> Path:
    directory = Path(tempfile.mkdtemp(prefix="evidence-fixture-", dir=root))
    source = directory / "rollout.jsonl"
    lines = [
        _envelope("session_meta", {"id": "accept-thread"}, "2026-07-28T00:00:00Z"),
        _envelope("response_item", {"type": "message", "role": "user", "content": "fix parser"}, "2026-07-28T00:00:01Z"),
        _envelope("response_item", {"type": "function_call", "name": "apply_patch", "call_id": "accept-call", "arguments": {"scope": "evidence"}}, "2026-07-28T00:00:02Z"),
        _envelope("response_item", {"type": "function_call_output", "call_id": "accept-call", "status": "success", "output": "done"}, "2026-07-28T00:00:03Z"),
        _envelope("response_item", {"type": "message", "role": "assistant", "content": "X" * 4_300_000}, "2026-07-28T00:00:04Z"),
    ]
    source.write_bytes(b"".join(lines))
    return source


def _export_fixture(child: Path, root: Path, env: Mapping[str, str]) -> tuple[Path, dict[str, Any]]:
    source = _create_source_fixture(root)
    output = source.parent / "evidence.zip"
    payload = _run_cli(child, ("telemetry", "agent-thread", "export", "--source", source, "--output", output, "--json"), root, env)
    evidence = payload.get("evidence")
    if (
        payload.get("status") != "exported"
        or payload.get("schema_version") != 3
        or "diagnostics" in payload
        or not isinstance(evidence, Mapping)
        or evidence.get("schema_version") != 3
        or not isinstance(evidence.get("native_bytes"), int)
        or not isinstance(evidence.get("native_records"), int)
    ):
        raise _CaseFailure("evidence-export")
    return output, dict(payload)


def _evidence_id(native: bytes, native_index: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(_EVIDENCE_ID_DOMAIN)
    for name, data in ((b"native.bin", native), (b"native-index.jsonl", native_index)):
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _validate_evidence_zip(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], bytes]:
    """Check only the bytes this independent consumer must trust.

    Evidence-core tests own the schema and projection invariants.  Acceptance
    keeps the smaller installed-consumer contract: core members, one snapshot
    identity, and exact frame reconstruction needed by the read case.
    """

    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            present = set(names)
            if len(names) != len(present) or not _EVIDENCE_CORE_MEMBERS <= present or not present <= _EVIDENCE_CORE_MEMBERS | _EVIDENCE_OPTIONAL_MEMBERS:
                raise _CaseFailure("evidence-members")
            manifest_bytes = archive.read("manifest.json")
            native = archive.read("native.bin")
            index_bytes = archive.read("native-index.jsonl")
            manifest = _json(manifest_bytes, "evidence-manifest")
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        raise _CaseFailure("evidence-members") from error
    if (
        not isinstance(manifest, Mapping)
        or manifest.get("format") != "svc-agent-thread-evidence"
        or manifest.get("schema_version") != 3
    ):
        raise _CaseFailure("evidence-manifest")
    capture = manifest.get("capture")
    evidence_id = manifest.get("evidence_id")
    if (
        not isinstance(capture, Mapping)
        or capture.get("status") not in {"complete", "partial"}
        or not isinstance(capture.get("unknown_remainder"), bool)
        or not isinstance(capture.get("read_interrupted"), bool)
        or not isinstance(evidence_id, str)
        or _EVIDENCE_ID_RE.fullmatch(evidence_id) is None
        or evidence_id != _evidence_id(native, index_bytes)
    ):
        raise _CaseFailure("evidence-manifest")
    source = manifest.get("source")
    if not isinstance(source, Mapping) or not all(isinstance(source.get(key), str) for key in ("provider_id", "adapter_id", "source_format", "thread_id", "source_status")):
        raise _CaseFailure("evidence-manifest")
    entries: list[dict[str, Any]] = []
    expected_start = 0
    for ordinal, line in enumerate(index_bytes.splitlines()):
        value = _json(line, "evidence-index")
        if (
            not isinstance(value, Mapping)
            or set(value) != {"native_record_id", "byte_start", "byte_end", "frame_status", "source_coordinate"}
            or value.get("native_record_id") != f"n{ordinal:06d}"
            or value.get("byte_start") != expected_start
            or not isinstance(value.get("byte_end"), int)
            or value["byte_end"] <= expected_start
            or value["byte_end"] > len(native)
            or value.get("frame_status") not in {"complete", "incomplete"}
            or not isinstance(value.get("source_coordinate"), Mapping)
        ):
            raise _CaseFailure("evidence-index")
        entries.append(
            {
                "native_record_id": value["native_record_id"],
                "byte_start": expected_start,
                "byte_end": value["byte_end"],
                "sha256": hashlib.sha256(native[expected_start:value["byte_end"]]).hexdigest(),
            }
        )
        expected_start = value["byte_end"]
    if expected_start != len(native):
        raise _CaseFailure("evidence-index")
    return dict(manifest), entries, native


def _run_inventory_case(child: Path, root: Path, env: Mapping[str, str]) -> None:
    home = _create_inventory_fixture(root)
    payload = _run_cli(child, ("telemetry", "agent-thread", "list", "--codex-home", home, "--archive-state", "all", "--limit", "100", "--json"), root, env)
    threads = payload.get("threads")
    if not isinstance(threads, list) or {item.get("thread_id") for item in threads if isinstance(item, Mapping)} != {"inv-active", "inv-archived", "inv-missing", "inv-unknown"}:
        raise _CaseFailure("inventory-shape")
    expected_keys = {
        "provider_id",
        "thread_id",
        "archive_state",
        "workspace",
        "title",
        "first_user_message",
        "workspace_truncated",
        "title_truncated",
        "first_user_message_truncated",
        "created_at",
        "updated_at",
        "recency_at_ms",
    }
    if any(not isinstance(item, Mapping) or set(item) != expected_keys for item in threads):
        raise _CaseFailure("inventory-shape")
    active = next((item for item in threads if isinstance(item, Mapping) and item.get("thread_id") == "inv-active"), None)
    if not isinstance(active, Mapping) or active.get("archive_state") != "active" or active.get("workspace") != "/workspace/acceptance" or active.get("title") != "Inspect parser" or active.get("first_user_message") != "Start parser work":
        raise _CaseFailure("inventory-rich")
    archived = _run_cli(child, ("telemetry", "agent-thread", "list", "--codex-home", home, "--archive-state", "archived", "--limit", "1", "--json"), root, env)
    if [item.get("thread_id") for item in archived.get("threads", []) if isinstance(item, Mapping)] != ["inv-missing"]:
        raise _CaseFailure("inventory-filter")


def _run_evidence_case(child: Path, root: Path, env: Mapping[str, str]) -> None:
    bundle, export = _export_fixture(child, root, env)
    manifest, entries, _native = _validate_evidence_zip(bundle)
    if len(entries) != 5 or entries[-1].get("byte_end", 0) - entries[-1].get("byte_start", 0) <= 4_194_304:
        raise _CaseFailure("evidence-oversized")
    if export.get("evidence", {}).get("evidence_id") != manifest.get("evidence_id"):
        raise _CaseFailure("evidence-binding")
    legacy = root / "legacy-v2.zip"
    with zipfile.ZipFile(legacy, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", _canonical({"format": "svc-agent-thread-bundle", "schema_version": 2}, newline=True))
        archive.writestr("native.bin", b"legacy")
        archive.writestr("native-index.jsonl", b"legacy")
        archive.writestr("trajectory.jsonl", b"legacy")
    request = root / "legacy-request.json"
    request.write_bytes(_canonical({"intent": "overview"}, newline=False))
    result = _command((child, "-m", "svc_cli.cli", "analysis", "query", "--input", legacy, "--request", request), cwd=root, env=env)
    _bounded_output(result, "legacy-cutoff")
    payload = _json(result.stderr, "legacy-cutoff")
    if result.returncode != 4 or not isinstance(payload, Mapping) or payload.get("code") != "unsupported-agent-thread-bundle-schema" or result.stdout:
        raise _CaseFailure("legacy-cutoff")


def _run_query_case(child: Path, root: Path, env: Mapping[str, str]) -> None:
    bundle, _export = _export_fixture(child, root, env)
    schema = _run_cli(child, ("analysis", "query", "--schema"), root, env)
    if schema.get("schema_version") != 2 or schema.get("guidance") != {
        "command": ["svc", "analysis", "--help"]
    }:
        raise _CaseFailure("query-schema")
    overview_request = root / "overview.json"
    overview_request.write_bytes(_canonical({"intent": "overview"}))
    overview = _run_cli(child, ("analysis", "query", "--input", bundle, "--request", overview_request), root, env)
    native_range = overview.get("native_range")
    if (
        overview.get("status") != "partial"
        or not isinstance(native_range, Mapping)
        or native_range.get("records") != 5
        or "method" in overview
    ):
        raise _CaseFailure("query-overview")
    match_request = root / "match.json"
    match_request.write_bytes(_canonical({"intent": "match", "predicates": {"text": {"terms": ["parser"], "mode": "all"}}}))
    match = _run_cli(child, ("analysis", "query", "--input", bundle, "--request", match_request), root, env)
    items = match.get("items")
    if match.get("status") != "complete" or not isinstance(items, list) or len(items) != 1 or items[0].get("ref", {}).get("record_kind") != "native" or items[0].get("matched_terms") != ["parser"]:
        raise _CaseFailure("query-match")
    malformed = root / "malformed.json"
    malformed.write_bytes(b"{")
    error = _run_cli(child, ("analysis", "query", "--input", bundle, "--request", malformed), root, env, expect=2)
    if error.get("code") != "invalid-analysis-request-json":
        raise _CaseFailure("query-error")


def _run_read_case(child: Path, root: Path, env: Mapping[str, str]) -> None:
    bundle, _export = _export_fixture(child, root, env)
    schema = _run_cli(child, ("analysis", "read", "--schema"), root, env)
    if schema.get("schema_version") != 2 or schema.get("guidance") != {
        "command": ["svc", "analysis", "--help"]
    }:
        raise _CaseFailure("read-schema")
    first_request = root / "read-first.json"
    first_request.write_bytes(_canonical({"max_items": 1, "max_bytes": 1_048_576}))
    first = _run_cli(child, ("analysis", "read", "--input", bundle, "--request", first_request), root, env)
    if not isinstance(first.get("next_cursor"), str) or first.get("items", [{}])[0].get("native_index") != 0:
        raise _CaseFailure("read-start")
    start_ref = first["items"][0]["ref"]
    ref_request = root / "read-ref.json"
    ref_request.write_bytes(_canonical({"start": start_ref, "max_items": 1, "max_bytes": 1_048_576}))
    by_ref = _run_cli(child, ("analysis", "read", "--input", bundle, "--request", ref_request), root, env)
    if by_ref.get("items", [{}])[0].get("ref") != start_ref:
        raise _CaseFailure("read-ref")
    cursor_request = root / "read-cursor.json"
    cursor_request.write_bytes(_canonical({"cursor": first["next_cursor"], "max_items": 1, "max_bytes": 1_048_576}))
    continued = _run_cli(child, ("analysis", "read", "--input", bundle, "--request", cursor_request), root, env)
    if continued.get("items", [{}])[0].get("native_index") != 1:
        raise _CaseFailure("read-cursor")
    _manifest, entries, native = _validate_evidence_zip(bundle)
    oversized = max(entries, key=lambda item: item["byte_end"] - item["byte_start"])
    request: dict[str, Any] = {"start": {"evidence_id": first["evidence_id"], "record_kind": "native", "record_id": oversized["native_record_id"]}, "max_items": 1, "max_bytes": 1_048_576}
    fragments = bytearray()
    pages = 0
    while True:
        page = root / f"read-fragment-{pages}.json"
        page.write_bytes(_canonical(request))
        response = _run_cli(child, ("analysis", "read", "--input", bundle, "--request", page), root, env)
        items = response.get("items")
        if not isinstance(items, list) or len(items) != 1:
            raise _CaseFailure("read-fragment")
        payload = items[0].get("payload")
        if not isinstance(payload, Mapping):
            raise _CaseFailure("read-fragment")
        if payload.get("encoding") == "utf-8" and isinstance(payload.get("text"), str):
            fragments.extend(payload["text"].encode("utf-8"))
        elif payload.get("encoding") == "base64" and isinstance(payload.get("data"), str):
            fragments.extend(base64.b64decode(payload["data"]))
        else:
            raise _CaseFailure("read-fragment")
        pages += 1
        cursor = response.get("next_cursor")
        if cursor is None:
            break
        request = {"cursor": cursor, "max_items": 1, "max_bytes": 1_048_576}
        if pages > 16:
            raise _CaseFailure("read-fragment")
    expected = native[oversized["byte_start"] : oversized["byte_end"]]
    if bytes(fragments) != expected or hashlib.sha256(fragments).hexdigest() != oversized["sha256"] or pages < 2:
        raise _CaseFailure("read-fragment")


def _selected(slice_name: str) -> tuple[str, ...]:
    if slice_name == "all":
        return ("inventory", "evidence", "query", "read")
    return (slice_name,)


def _report(slice_name: str, *, status: str, exit_code: int, digest: str | None = None) -> dict[str, Any]:
    return {
        "harness_version": HARNESS_VERSION,
        "slice": slice_name,
        "status": status,
        "exit_code": exit_code,
        "wheel_sha256": digest,
        "platform": platform.system().lower(),
        "python": platform.python_version(),
        "installed": {},
        "cases": {},
        "cleanup": "pending",
    }


def main(argv: Sequence[str] | None = None) -> int:
    try:
        options = _parser().parse_args(argv)
    except HarnessError as error:
        payload = _report("unknown", status="failed", exit_code=error.exit_code)
        payload["error"] = error.reason
        payload["cleanup"] = "not-started"
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return error.exit_code
    report = _report(options.slice, status="failed", exit_code=1)
    temporary: Path | None = None
    active: str | None = None
    try:
        if sys.version_info < (3, 11):
            raise HarnessError(3, "python")
        digest = _validate_inputs(options.wheel, options.expected_sha256, options.wheelhouse)
        report["wheel_sha256"] = digest
        temporary = Path(tempfile.mkdtemp(prefix="svc-accept-"))
        env = _environment(temporary)
        staged = _stage_wheel(options.wheel, digest, temporary)
        child = _create_venv(temporary)
        _install(child, staged, options.wheelhouse, temporary, env)
        report["installed"] = _installed_versions(child, temporary, env)
        _run_source_probe(child, temporary, env)
        runners = {
            "inventory": _run_inventory_case,
            "evidence": _run_evidence_case,
            "query": _run_query_case,
            "read": _run_read_case,
        }
        for case in _selected(options.slice):
            active = case
            runners[case](child, temporary, env)
            report["cases"][case] = "passed"
        report["status"] = "passed"
        report["exit_code"] = 0
    except _CaseFailure:
        report["error"] = "case"
        if active is not None:
            report["cases"][active] = "failed"
        report["exit_code"] = 6
    except HarnessError as error:
        report["error"] = error.reason
        report["exit_code"] = error.exit_code
    except (OSError, RuntimeError, sqlite3.DatabaseError, zipfile.BadZipFile, TypeError, ValueError, KeyError, IndexError):
        report["error"] = "case"
        if active is not None:
            report["cases"][active] = "failed"
        report["exit_code"] = 6
    except Exception:
        report["error"] = "case"
        if active is not None:
            report["cases"][active] = "failed"
        report["exit_code"] = 6
    finally:
        if temporary is None:
            report["cleanup"] = "not-started"
        else:
            try:
                shutil.rmtree(temporary)
                report["cleanup"] = "failed" if temporary.exists() else "passed"
            except OSError:
                report["cleanup"] = "failed"
        if report["cleanup"] == "failed":
            report["status"] = "failed"
            report["error"] = "cleanup"
            report["exit_code"] = 7
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return int(report["exit_code"])


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
