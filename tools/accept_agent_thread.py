"""Black-box acceptance harness for the agent-thread release slices.

The harness intentionally has no dependency on the repository checkout.  It
validates a wheel, creates a host-local temporary virtual environment, installs
that wheel with ``--no-index``, and exercises the installed commands through
synthetic Codex fixtures.  Keeping this module standard-library only makes it
useful before (and after) the project environment is installed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    import venv
except ImportError:  # pragma: no cover - depends on the base Python build
    venv = None  # type: ignore[assignment]


HARNESS_VERSION = "1"
SLICE_CHOICES = ("inventory", "bundle", "analysis", "ui", "all")
_INSTALLED_DISTRIBUTIONS = (
    "sustainable-vibe-coding",
    "pydantic",
    "platformdirs",
    "filelock",
    "textual",
    "rich",
    "markdown-it-py",
    "mdit-py-plugins",
    "linkify-it-py",
    "uc-micro-py",
    "mdurl",
    "pygments",
    "typing-extensions",
)
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_OPAQUE_THREAD_REF_RE = re.compile(r"^thread_[0-9a-f]{64}$")
_OPAQUE_REF_RE = re.compile(
    r"^(?:thread|turn|call|actor|lane|concurrency|workspace)_[0-9a-f]{64}(?:_d[0-9]{6})?$"
)
_RECORD_ID_RE = re.compile(r"^r[0-9]{6}$")
_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$"
)
_MAX_CHILD_OUTPUT_BYTES = 128 * 1024
_BUNDLE_MEMBERS = ("manifest.json", "trajectory.jsonl")
_BUNDLE_FORMAT = "svc-agent-thread-bundle"
_BUNDLE_SCHEMA_VERSION = 2
_TRAJECTORY_SCHEMA = "svc.trajectory/v1"
_RECORD_TYPES = ("meta", "message", "reasoning", "tool_call", "tool_result", "context", "event")
_RELATIONSHIP_KEYS = {
    "turn_ref",
    "actor_ref",
    "parent_actor_ref",
    "lane_ref",
    "concurrency_group",
}
_RECORD_FIELDS = {
    "meta": {
        "trajectory_schema",
        "provider_id",
        "adapter_id",
        "source_format",
        "thread_ref",
        "workspace",
        "content_profile",
    },
    "message": {"role", "content", "content_meta", "task_refs"},
    "reasoning": {"reasoning_kind", "content", "content_meta"},
    "tool_call": {
        "tool_call_id",
        "name",
        "name_meta",
        "name_fingerprint",
        "arguments_kind",
        "arguments",
        "arguments_meta",
        "arguments_fingerprint",
    },
    "tool_result": {
        "tool_call_id",
        "content",
        "content_meta",
        "status",
        "link_status",
    },
    "context": {
        "context_kind",
        "content",
        "content_meta",
        "attributes",
        "attributes_meta",
        "fingerprint",
    },
    "event": {"event_kind", "outcome"},
}
_BUNDLE_TASK_REFERENCE = "tasks/bundle/packet.md"
_PRIVATE_SENTINELS = (
    "SVC_ACCEPT_PRIVATE_CWD_7E21",
    "SVC_ACCEPT_PRIVATE_TITLE_7E21",
    "SVC_ACCEPT_PRIVATE_MESSAGE_7E21",
    "SVC_ACCEPT_PRIVATE_PREVIEW_7E21",
    "SVC_ACCEPT_PRIVATE_REASONING_7E21",
    "SVC_ACCEPT_PRIVATE_TOOL_7E21",
    "SVC_ACCEPT_PRIVATE_THREAD_7E21",
    "SVC_ACCEPT_PRIVATE_TASK_PACKET_7E21",
)
_EXPECTED_BOUNDS = {
    "source_bytes": 268_435_456,
    "native_line_bytes": 4_194_304,
    "native_json_depth": 64,
    "records": 50_000,
    "trajectory_bytes": 33_554_432,
    "schema_v2_zip_bytes": 67_108_864,
    "manifest_bytes": 1_048_576,
    "workspace_label_code_points": 256,
    "message_context_code_points": 16_384,
    "reasoning_code_points": 8_192,
    "tool_name_code_points": 256,
    "tool_arguments_code_points": 20_000,
    "tool_result_code_points": 2_500,
    "context_attribute_keys": 6,
    "context_attribute_code_points": 512,
    "tool_config_names": 256,
    "task_reference_code_points": 1_024,
    "task_reference_occurrences": 2_048,
    "structural_label_ascii": 128,
    "diagnostics": 256,
    "diagnostic_detail_keys": 16,
    "diagnostic_detail_ascii": 128,
}
_EXPECTED_POLICY = {
    "profile": "bounded-normalized-v1",
    "sensitivity": "acknowledged",
    "redaction": "none",
    "noise_policy": "structural-v1",
    "task_reference_policy": "lexical-relative-packet-v1",
    "timestamp_policy": "utc-rfc3339-nanosecond-v1",
    "bounds": _EXPECTED_BOUNDS,
}
_MANIFEST_KEYS = {
    "format",
    "schema_version",
    "trajectory",
    "bundle_id",
    "exporter",
    "generated_at",
    "source",
    "policy",
    "result_status",
    "capabilities",
    "counts",
    "lossiness",
    "diagnostics",
}
_COUNT_KEYS = {
    "source_bytes_read",
    "source_events_seen",
    "records_emitted",
    "trajectory_bytes",
    "records_by_type",
    "messages_by_role",
    "tool_calls",
    "tool_results",
    "task_references",
    "diagnostics_emitted",
    "diagnostics_suppressed",
}
_LOSS_KEYS = {
    "dropped": {
        "provider_envelope",
        "ui_event",
        "rate_limit_noise",
        "world_state",
        "duplicate_bookkeeping",
        "opaque_metadata",
        "unsupported_record",
        "invalid_json",
        "oversize_record",
        "excessive_json_depth",
        "duplicate_tool_result",
        "absolute_task_reference",
        "invalid_task_reference",
        "oversize_task_reference",
    },
    "truncated": {
        "timestamp_precision",
        "workspace_label",
        "message",
        "context_content",
        "context_attribute",
        "reasoning",
        "tool_name",
        "tool_config_names",
        "tool_arguments",
        "tool_result",
        "task_references",
        "diagnostics",
    },
    "unavailable": {
        "reasoning",
        "tool_linkage",
        "context",
        "task_references",
        "explicit_concurrency",
        "timestamps",
        "terminal_events",
    },
    "synthesized": {"tool_call_id"},
    "partial_reasons": {
        "source_grew",
        "source_changed",
        "source_displaced",
        "source_read_interrupted",
        "input_limit",
        "record_limit",
        "trajectory_limit",
    },
}
_SCHEMA_V1_PROBE_MARKER = "svc-accept-schema-v1"
_SCHEMA_V1_PROBE = f"""# {_SCHEMA_V1_PROBE_MARKER}
import json
import sys
import zipfile
from pathlib import Path

from svc_cli.telemetry.trajectory import TrajectoryError, validate_bundle

output = Path(sys.argv[1])
sentinel = sys.argv[2].encode("utf-8")
manifest = {{
    "schema_version": 1,
    "exporter": {{"name": "svc"}},
    "provider": {{}},
    "thread": {{}},
    "artifact": {{}},
}}
encoded_manifest = (
    json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    + "\\n"
).encode("utf-8")
with zipfile.ZipFile(
    output,
    mode="w",
    compression=zipfile.ZIP_DEFLATED,
) as archive:
    archive.writestr("manifest.json", encoded_manifest)
    archive.writestr("providers/codex/rollout.jsonl", sentinel)
    archive.writestr("thread/index.json", sentinel)
    archive.writestr("task-packets/tasks/x/packet.md", sentinel)

opened = []
def member_open(archive, info):
    opened.append(info.filename)
    return archive.open(info, mode="r")

code = None
try:
    validate_bundle(output, member_open=member_open)
except TrajectoryError as error:
    code = error.code

payload = {{"code": code, "opened": opened}}
sys.stdout.write(
    json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\\n"
)
raise SystemExit(
    0
    if code == "unsupported-agent-thread-bundle-schema"
    and opened == ["manifest.json"]
    else 1
)
"""
_ANALYSIS_ROOT_KEYS = {
    "format",
    "schema_version",
    "bundle_id",
    "analyzer",
    "result_status",
    "dimensions",
    "metrics",
    "findings",
    "unknowns",
    "lossiness",
}
_ANALYSIS_DIMENSIONS = (
    "task_evidence",
    "interaction_transitions",
    "constraint_evidence",
    "tool_outcomes",
    "loop_candidates",
    "lanes",
    "terminal_coverage",
    "svc_signals",
    "context_changes",
    "coverage",
)
_ANALYSIS_METRIC_KEYS = {
    "task_evidence": {
        "user_turn_count",
        "user_turn_refs",
        "task_references",
    },
    "interaction_transitions": {
        "boundary_count",
        "boundaries",
        "structured_approval_count",
    },
    "constraint_evidence": {
        "context_record_count",
        "task_reference_count",
        "structured_approval_count",
        "evidence_refs",
    },
    "tool_outcomes": {
        "calls",
        "results",
        "success",
        "error",
        "unknown",
        "pending",
        "orphan",
        "late_linked",
        "truncated_results",
        "retry_groups",
        "tools",
    },
    "loop_candidates": {
        "retry_group_count",
        "loop_candidate_count",
        "stall_candidate_count",
        "recovery_candidate_count",
        "groups",
    },
    "lanes": {
        "actor_count",
        "lane_count",
        "concurrency_group_count",
        "parent_link_count",
        "actors",
        "lanes",
        "concurrency_groups",
    },
    "terminal_coverage": {
        "status",
        "terminal_evidence_refs",
        "tail_loss",
    },
    "svc_signals": {
        "task_references",
        "svc_cli_calls",
        "test_calls",
        "build_calls",
        "signals",
    },
    "context_changes": {
        "context_records",
        "changes",
        "by_kind",
        "change_refs",
    },
    "coverage": {
        "records_total",
        "records_by_type",
        "messages_by_role",
        "timestamped_records",
        "untimestamped_records",
        "first_timestamp",
        "last_timestamp",
        "source_status",
        "bundle_result_status",
        "capabilities",
    },
}
_ANALYSIS_ANALYZER = {
    "name": "svc-agent-thread-analyzer",
    "version": 1,
    "method": "deterministic-v1",
}
_MAX_ANALYSIS_BYTES = 2_097_152
_ANALYSIS_IMPORT_PROBE_MARKER = "svc-accept-analysis-import-isolation"
_ANALYSIS_IMPORT_PROBE = """# svc-accept-analysis-import-isolation
import builtins
import contextlib
import io
import json
import sys

original_import = builtins.__import__
blocked = []
def guarded_import(name, *args, **kwargs):
    if name == "textual" or name.startswith("textual."):
        blocked.append(name)
        raise ImportError("textual import blocked")
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
stdout = io.StringIO()
stderr = io.StringIO()
code = 1
try:
    from svc_cli.cli import main
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main([
            "telemetry",
            "agent-thread",
            "analyze",
            "--input",
            sys.argv[1],
            "--json",
        ])
finally:
    builtins.__import__ = original_import

try:
    value = json.loads(stdout.getvalue())
except (TypeError, ValueError, json.JSONDecodeError):
    value = None
root = {
    "format",
    "schema_version",
    "bundle_id",
    "analyzer",
    "result_status",
    "dimensions",
    "metrics",
    "findings",
    "unknowns",
    "lossiness",
}
textual_loaded = any(
    name == "textual" or name.startswith("textual.")
    for name in sys.modules
)
tui_loaded = "svc_cli.telemetry.tui" in sys.modules
passed = (
    code == 0
    and stderr.getvalue() == ""
    and isinstance(value, dict)
    and set(value) == root
    and not blocked
    and not textual_loaded
    and not tui_loaded
)
payload = {
    "code": code,
    "root": isinstance(value, dict) and set(value) == root,
    "textual_imported": bool(blocked or textual_loaded),
    "tui_imported": tui_loaded,
}
sys.stdout.write(
    json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\\n"
)
raise SystemExit(0 if passed else 1)
"""
_UI_PROBE_MARKER = "svc-accept-textual-headless"
_UI_PROBE = """# svc-accept-textual-headless
import asyncio
import json
import sys
from pathlib import Path

from textual.widgets import TabbedContent, TabPane

from svc_cli.telemetry.analysis import analyze_trajectory
from svc_cli.telemetry.trajectory import validate_bundle
from svc_cli.telemetry.tui import AgentThreadAnalysisApp, AnalysisDocument

VIEWS = (
    "overview",
    "timeline",
    "tools",
    "lanes",
    "context",
    "tasks",
    "terminal",
    "loss",
)

async def exercise(bundle, size, quit_key):
    analysis = analyze_trajectory(bundle)
    document = AnalysisDocument(bundle, analysis)
    app = AgentThreadAnalysisApp(initial_document=document)
    streams = (sys.stdin, sys.stdout, sys.stderr)
    entered = False
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        if app.document is not document or len(app.query("TabPane")) != 8:
            raise RuntimeError("initial document was not rendered")
        await pilot.press("enter")
        await pilot.pause()
        entered = app.document is document
        tabs = app.query_one("#analysis-tabs", TabbedContent)
        for key, expected in zip("12345678", VIEWS):
            await pilot.press(key)
            await pilot.pause()
            if tabs.active != expected:
                raise RuntimeError("analysis view did not activate")
        await pilot.press(quit_key)
    if app.is_running or (sys.stdin, sys.stdout, sys.stderr) != streams:
        raise RuntimeError("headless terminal state was not restored")
    return entered

async def main():
    bundle = validate_bundle(Path(sys.argv[1]))
    wide = await exercise(bundle, (80, 24), "q")
    narrow = await exercise(bundle, (30, 10), "escape")
    if not wide or not narrow:
        raise RuntimeError("enter interaction was not preserved")
    return {
        "entered": 2,
        "quits": ["q", "escape"],
        "restored": True,
        "sizes": [[80, 24], [30, 10]],
        "views": 8,
    }

payload = asyncio.run(main())
sys.stdout.write(
    json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\\n"
)
"""


class HarnessError(Exception):
    """An expected, user-facing harness failure with a stable exit code."""

    def __init__(self, exit_code: int, reason: str) -> None:
        super().__init__(reason)
        self.exit_code = exit_code
        self.reason = reason


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:  # pragma: no cover - exercised through main
        raise HarnessError(2, "arguments")


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        prog="accept_agent_thread",
        description="Run the SHA-bound agent-thread acceptance slice.",
    )
    parser.add_argument("--slice", choices=SLICE_CHOICES, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    return parser


def _is_reparse_point(info: os.stat_result) -> bool:
    attributes = getattr(info, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse and attributes & reparse)


def _lstat_regular(path: Path, *, directory: bool = False) -> os.stat_result:
    try:
        info = path.lstat()
    except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as exc:
        raise HarnessError(4, "wheel-validation") from exc
    if stat.S_ISLNK(info.st_mode) or _is_reparse_point(info):
        raise HarnessError(4, "wheel-validation")
    expected = stat.S_IFDIR if directory else stat.S_IFREG
    if stat.S_IFMT(info.st_mode) != expected:
        raise HarnessError(4, "wheel-validation")
    return info


def _identity(info: os.stat_result) -> tuple[int, int, int]:
    return (getattr(info, "st_dev", -1), getattr(info, "st_ino", -1), stat.S_IFMT(info.st_mode))


def _open_verified(path: Path, expected_identity: os.stat_result) -> tuple[int, os.stat_result]:
    flags = os.O_RDONLY
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if nofollow:
        flags |= nofollow
    binary = getattr(os, "O_BINARY", 0)
    if binary:
        flags |= binary
    try:
        descriptor = os.open(path, flags)
    except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as exc:
        raise HarnessError(4, "wheel-validation") from exc
    try:
        opened = os.fstat(descriptor)
        if _identity(opened) != _identity(expected_identity):
            raise HarnessError(4, "wheel-validation")
        return descriptor, opened
    except Exception:
        os.close(descriptor)
        raise


def _sha256_file(path: Path, expected_identity: os.stat_result) -> str:
    descriptor, _opened = _open_verified(path, expected_identity)
    try:
        digest = hashlib.sha256()
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _stage_wheel(source: Path, expected_digest: str, root: Path) -> Path:
    """Copy the validated wheel from one stable descriptor into our temp root.

    The pip child only receives this staged copy.  The source path is checked
    again after copying, so a replacement between initial validation and the
    install cannot silently change the SHA-bound artifact.
    """

    source_info = _lstat_regular(source)
    if source.suffix.lower() != ".whl":
        raise HarnessError(4, "wheel-validation")
    descriptor, opened = _open_verified(source, source_info)
    staged = root / source.name
    digest = hashlib.sha256()
    try:
        destination_descriptor = os.open(
            staged,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
            0o600,
        )
        try:
            with os.fdopen(descriptor, "rb", closefd=True) as source_stream:
                descriptor = -1
                with os.fdopen(destination_descriptor, "wb", closefd=True) as destination_stream:
                    destination_descriptor = -1
                    for chunk in iter(lambda: source_stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                        destination_stream.write(chunk)
        finally:
            if destination_descriptor >= 0:
                os.close(destination_descriptor)
        if digest.hexdigest() != expected_digest.lower():
            raise HarnessError(4, "wheel-validation")
        if _identity(source.lstat()) != _identity(opened):
            raise HarnessError(4, "wheel-validation")
        staged_info = _lstat_regular(staged)
        if _sha256_file(staged, staged_info) != expected_digest.lower():
            raise HarnessError(4, "wheel-validation")
        return staged
    except HarnessError:
        staged.unlink(missing_ok=True)
        raise
    except (OSError, RuntimeError) as exc:
        staged.unlink(missing_ok=True)
        raise HarnessError(4, "wheel-validation") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _validate_inputs(wheel: Path, expected: str, wheelhouse: Path) -> str:
    if not _SHA256_RE.fullmatch(expected):
        raise HarnessError(4, "wheel-validation")
    wheel_info = _lstat_regular(wheel)
    if wheel.suffix.lower() != ".whl":
        raise HarnessError(4, "wheel-validation")
    digest = _sha256_file(wheel, wheel_info)
    if digest != expected.lower():
        raise HarnessError(4, "wheel-validation")
    _lstat_regular(wheelhouse, directory=True)
    try:
        entries = tuple(wheelhouse.iterdir())
    except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as exc:
        raise HarnessError(4, "wheel-validation") from exc
    for entry in entries:
        _lstat_regular(entry)
        if entry.suffix.lower() != ".whl":
            raise HarnessError(4, "wheel-validation")
    return digest


def _command(
    args: Sequence[str | os.PathLike[str]],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a child command without shell interpolation or output leakage."""

    return subprocess.run(
        [os.fspath(value) for value in args],
        cwd=os.fspath(cwd) if cwd is not None else None,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _isolated_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for key in (
        "PYTHONPATH",
        "PYTHONHOME",
        "PIP_INDEX_URL",
        "PIP_EXTRA_INDEX_URL",
        "PIP_FIND_LINKS",
        "PIP_TRUSTED_HOST",
    ):
        environment.pop(key, None)
    environment.update(
        {
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
            "PYTHONNOUSERSITE": "1",
        }
    )
    return environment


def _child_python(venv_directory: Path) -> Path:
    if os.name == "nt":
        return venv_directory / "Scripts" / "python.exe"
    return venv_directory / "bin" / "python"


def _create_virtualenv(root: Path) -> Path:
    directory = root / "venv"
    if venv is None:
        raise HarnessError(3, "venv")
    try:
        venv.EnvBuilder(with_pip=True, clear=False).create(directory)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        raise HarnessError(3, "venv") from exc
    child = _child_python(directory)
    try:
        _lstat_regular(child)
    except HarnessError as exc:
        raise HarnessError(3, "venv") from exc
    return child


def _install_wheel(child: Path, wheel: Path, wheelhouse: Path, root: Path, environment: dict[str, str]) -> None:
    try:
        result = _command(
            (
                child,
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                wheelhouse,
                wheel,
            ),
            cwd=root,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise HarnessError(5, "install") from exc
    if result.returncode != 0:
        raise HarnessError(5, "install")


def _installed_versions(child: Path, root: Path, environment: dict[str, str]) -> dict[str, str]:
    # Keep the helper expression local to the child process and avoid relying
    # on an import from the checkout.
    code = (
        "import importlib.metadata as m,json; "
        f"names={_INSTALLED_DISTRIBUTIONS!r}; "
        "out={}; "
        "\nfor n in names:\n  "
        "\n  try: out[n]=m.version(n)\n  except m.PackageNotFoundError: pass\n"
        "print(json.dumps(out, sort_keys=True))"
    )
    try:
        result = _command((child, "-c", code), cwd=root, env=environment)
    except (OSError, subprocess.SubprocessError) as exc:
        raise HarnessError(5, "install") from exc
    if result.returncode != 0:
        raise HarnessError(5, "install")
    if not isinstance(result.stdout, str) or len(result.stdout) > 16 * 1024:
        raise HarnessError(5, "install")
    try:
        payload = json.loads(result.stdout)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HarnessError(5, "install") from exc
    allowed = set(_INSTALLED_DISTRIBUTIONS)
    if not isinstance(payload, dict) or len(payload) > len(allowed):
        raise HarnessError(5, "install")
    if any(
        key not in allowed
        or not isinstance(value, str)
        or not 1 <= len(value) <= 64
        or not re.fullmatch(r"[A-Za-z0-9.+!_~-]+", value)
        for key, value in payload.items()
    ):
        raise HarnessError(5, "install")
    if not {"sustainable-vibe-coding", "textual"} <= set(payload):
        raise HarnessError(5, "install")
    return {key: payload[key] for key in sorted(payload)}


def _create_inventory_fixture(root: Path) -> tuple[Path, dict[str, str]]:
    fixtures = root / "fixtures"
    home = fixtures / "codex-home"
    home.mkdir(parents=True)
    # Deliberately invalid transcript-shaped bytes prove inventory never
    # parses or serializes a rollout body while checking source availability.
    body_sentinel = (_PRIVATE_SENTINELS[3] + "\n").encode("utf-8")
    (home / "active.jsonl").write_bytes(body_sentinel)
    (home / "archived.jsonl").write_bytes(body_sentinel)
    database = home / "state_5.sqlite"
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            """
            CREATE TABLE threads (
                id TEXT, rollout_path TEXT, archived INTEGER,
                created_at INTEGER, updated_at INTEGER,
                recency_at_ms INTEGER, updated_at_ms INTEGER,
                cwd TEXT, title TEXT, first_user_message TEXT,
                preview TEXT, reasoning TEXT, tool_payload TEXT
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO threads (
                id, rollout_path, archived, created_at, updated_at,
                recency_at_ms, updated_at_ms, cwd, title, first_user_message,
                preview, reasoning, tool_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    "inv-active-new",
                    "active.jsonl",
                    0,
                    1_700_000_000,
                    1_700_000_300,
                    3_000,
                    3_000,
                    _PRIVATE_SENTINELS[0],
                    _PRIVATE_SENTINELS[1],
                    _PRIVATE_SENTINELS[2],
                    _PRIVATE_SENTINELS[3],
                    _PRIVATE_SENTINELS[4],
                    _PRIVATE_SENTINELS[5],
                ),
                (
                    "inv-archived",
                    "archived.jsonl",
                    1,
                    1_700_000_000,
                    1_700_000_200,
                    2_000,
                    2_000,
                    _PRIVATE_SENTINELS[0],
                    _PRIVATE_SENTINELS[1],
                    _PRIVATE_SENTINELS[2],
                    _PRIVATE_SENTINELS[3],
                    _PRIVATE_SENTINELS[4],
                    _PRIVATE_SENTINELS[5],
                ),
                (
                    "inv-archived-missing",
                    "missing-archived.jsonl",
                    1,
                    1_700_000_000,
                    1_700_000_250,
                    2_500,
                    2_500,
                    _PRIVATE_SENTINELS[0],
                    _PRIVATE_SENTINELS[1],
                    _PRIVATE_SENTINELS[2],
                    _PRIVATE_SENTINELS[3],
                    _PRIVATE_SENTINELS[4],
                    _PRIVATE_SENTINELS[5],
                ),
                (
                    "inv-unknown",
                    "missing.jsonl",
                    None,
                    None,
                    1_700_000_100,
                    1_000,
                    1_000,
                    _PRIVATE_SENTINELS[0],
                    _PRIVATE_SENTINELS[1],
                    _PRIVATE_SENTINELS[2],
                    _PRIVATE_SENTINELS[3],
                    _PRIVATE_SENTINELS[4],
                    _PRIVATE_SENTINELS[5],
                ),
                (
                    "inv-unsafe",
                    "../escape.jsonl",
                    1,
                    1_700_000_000,
                    1_700_000_400,
                    4_000,
                    4_000,
                    _PRIVATE_SENTINELS[0],
                    _PRIVATE_SENTINELS[1],
                    _PRIVATE_SENTINELS[2],
                    _PRIVATE_SENTINELS[3],
                    _PRIVATE_SENTINELS[4],
                    _PRIVATE_SENTINELS[5],
                ),
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return home, {
        "active": "inv-active-new",
        "archived": "inv-archived",
        "archived_missing": "inv-archived-missing",
        "unknown": "inv-unknown",
    }


class _CaseFailure(Exception):
    pass


def _bounded_child_output(
    result: subprocess.CompletedProcess[str],
    failure: str,
) -> str:
    if not isinstance(result.stdout, str) or not isinstance(result.stderr, str):
        raise _CaseFailure(failure)
    combined = f"{result.stdout}\n{result.stderr}"
    try:
        output_size = len(combined.encode("utf-8", errors="strict"))
    except UnicodeEncodeError as exc:
        raise _CaseFailure(failure) from exc
    if output_size > _MAX_CHILD_OUTPUT_BYTES or any(
        sentinel in combined for sentinel in _PRIVATE_SENTINELS
    ):
        raise _CaseFailure(failure)
    return combined


def _inventory_payload(
    child: Path,
    home: Path,
    archive_state: str,
    limit: int,
    root: Path,
    environment: dict[str, str],
) -> dict[str, Any]:
    result = _command(
        (
            child,
            "-m",
            "svc_cli.cli",
            "telemetry",
            "agent-thread",
            "list",
            "--archive-state",
            archive_state,
            "--codex-home",
            home,
            "--limit",
            str(limit),
            "--json",
        ),
        cwd=root,
        env=environment,
    )
    _bounded_child_output(result, "inventory-output")
    if result.returncode != 0:
        raise _CaseFailure("inventory-output")
    try:
        payload = json.loads(result.stdout)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise _CaseFailure("inventory-json") from exc
    if not isinstance(payload, dict):
        raise _CaseFailure("inventory-shape")
    threads = payload.get("threads")
    if not isinstance(threads, list) or len(threads) > limit:
        raise _CaseFailure("inventory-shape")
    for item in threads:
        if not isinstance(item, dict):
            raise _CaseFailure("inventory-shape")
        if set(item) - {"provider_id", "thread_id", "source_state", "created_at", "updated_at"}:
            raise _CaseFailure("inventory-private")
    return payload


def _run_inventory_case(child: Path, root: Path, environment: dict[str, str]) -> None:
    home, identifiers = _create_inventory_fixture(root)
    all_payload = _inventory_payload(child, home, "all", 100, root, environment)
    all_ids = {item.get("thread_id") for item in all_payload["threads"]}
    if (
        identifiers["active"] not in all_ids
        or identifiers["archived"] not in all_ids
        or identifiers["archived_missing"] not in all_ids
        or identifiers["unknown"] not in all_ids
    ):
        raise _CaseFailure("inventory-all")
    warnings = all_payload.get("warnings")
    if not isinstance(warnings, list) or not any(
        isinstance(warning, dict)
        and warning.get("code") == "thread-source-omitted"
        and isinstance(warning.get("count"), int)
        and warning["count"] >= 1
        for warning in warnings
    ):
        raise _CaseFailure("inventory-omitted")
    archived_payload = _inventory_payload(child, home, "archived", 1, root, environment)
    archived_ids = {item.get("thread_id") for item in archived_payload["threads"]}
    if archived_ids != {identifiers["archived_missing"]}:
        raise _CaseFailure("inventory-archive-filter")
    active_payload = _inventory_payload(child, home, "active", 1, root, environment)
    active_ids = {item.get("thread_id") for item in active_payload["threads"]}
    if active_ids != {identifiers["active"]}:
        raise _CaseFailure("inventory-active-filter")


def _canonical_json_bytes(value: object, *, newline: bool = False) -> bytes:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8", errors="strict")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise _CaseFailure("bundle-json") from exc
    return encoded + (b"\n" if newline else b"")


def _strict_json_value(value: bytes | str, failure: str) -> object:
    try:
        text = value.decode("utf-8", errors="strict") if isinstance(value, bytes) else value

        def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, item in pairs:
                if key in result:
                    raise ValueError("duplicate key")
                result[key] = item
            return result

        def reject_constant(_constant: str) -> None:
            raise ValueError("non-finite number")

        return json.loads(
            text,
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise _CaseFailure(failure) from exc


def _create_bundle_fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    fixture = root / "bundle-fixture"
    repository = fixture / "repository"
    provider_home = fixture / "codex-home"
    export_directory = fixture / "exports"
    packet_directory = repository / "tasks" / "bundle"
    packet_directory.mkdir(parents=True)
    provider_home.mkdir(parents=True)
    export_directory.mkdir(parents=True)
    (packet_directory / "packet.md").write_text(
        f"# Acceptance packet\n\n{_PRIVATE_SENTINELS[7]}\n",
        encoding="utf-8",
    )

    source = provider_home / "rollout.jsonl"
    large_tool_output = (
        ("L" * 3_000)
        + _PRIVATE_SENTINELS[5]
        + ("R" * 3_000)
    )
    records = (
        {
            "timestamp": "2026-07-28T00:00:00Z",
            "type": "session_meta",
            "payload": {
                "id": _PRIVATE_SENTINELS[6],
                "cwd": f"/private/{_PRIVATE_SENTINELS[0]}/fixture-repository",
            },
        },
        {
            "timestamp": "2026-07-28T00:00:01Z",
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": (
                    f"{_PRIVATE_SENTINELS[2]} "
                    f"work from {_BUNDLE_TASK_REFERENCE}"
                ),
            },
        },
        {
            "timestamp": "2026-07-28T00:00:02Z",
            "type": "response_item",
            "payload": {
                "type": "reasoning",
                "encrypted_content": _PRIVATE_SENTINELS[4],
            },
        },
        {
            "timestamp": "2026-07-28T00:00:03Z",
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "title": _PRIVATE_SENTINELS[1],
                "preview": _PRIVATE_SENTINELS[3],
            },
        },
        {
            "timestamp": "2026-07-28T00:00:04Z",
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "acceptance-tool",
                "call_id": "acceptance-call",
                "arguments": {"scope": "bundle"},
            },
        },
        {
            "timestamp": "2026-07-28T00:00:05Z",
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "call_id": "acceptance-call",
                "status": "success",
                "output": large_tool_output,
            },
        },
    )
    source.write_bytes(
        b"".join(_canonical_json_bytes(record, newline=True) for record in records)
    )
    return source, export_directory / "bundle.zip", repository, provider_home


def _is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _bounded_text_valid(
    value: object,
    metadata: object,
    limit: int,
    *,
    allow_none: bool = False,
) -> bool:
    if not isinstance(metadata, Mapping) or set(metadata) != {
        "truncated",
        "observed_code_points",
        "retained_code_points",
        "strategy",
    }:
        return False
    if value is None:
        return bool(
            allow_none
            and metadata["truncated"] is False
            and metadata["observed_code_points"] == 0
            and metadata["retained_code_points"] == 0
            and metadata["strategy"] == "none"
        )
    observed = metadata["observed_code_points"]
    retained = metadata["retained_code_points"]
    strategy = metadata["strategy"]
    if (
        not isinstance(value, str)
        or not isinstance(metadata["truncated"], bool)
        or not _is_integer(observed)
        or not _is_integer(retained)
        or retained != len(value)
        or observed < retained
        or retained > limit
        or strategy not in {"none", "head", "head_tail"}
    ):
        return False
    if metadata["truncated"]:
        return strategy != "none" and observed > retained
    return strategy == "none" and observed == retained


def _valid_source_ref(value: object, *, meta: bool) -> bool:
    if not isinstance(value, Mapping):
        return False
    if meta:
        return set(value) == {"event_index", "component"} and value == {
            "event_index": None,
            "component": "meta",
        }
    if (
        "event_index" not in value
        or not _is_integer(value["event_index"])
        or value["event_index"] < 0
        or not set(value)
        <= {"event_index", "line", "byte_offset", "component_index", "component"}
    ):
        return False
    for key in ("line", "byte_offset", "component_index"):
        if key in value and (
            not _is_integer(value[key]) or value[key] < 0
        ):
            return False
    return "component" not in value or (
        isinstance(value["component"], str)
        and re.fullmatch(r"[a-z][a-z0-9_-]{0,127}", value["component"])
        is not None
    )


def _valid_task_reference(value: object) -> bool:
    if (
        not isinstance(value, str)
        or len(value) > _EXPECTED_BOUNDS["task_reference_code_points"]
        or "\\" in value
    ):
        return False
    parts = value.split("/")
    return (
        len(parts) >= 3
        and parts[0] == "tasks"
        and parts[-1] == "packet.md"
        and all(part not in {"", ".", ".."} for part in parts[1:-1])
    )


def _validate_workspace(value: object) -> None:
    required = {
        "status",
        "flavor",
        "label",
        "ref",
        "label_truncated",
        "observed_code_points",
        "retained_code_points",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise _CaseFailure("bundle-trajectory")
    if value["status"] == "missing":
        if (
            value["flavor"] is not None
            or value["label"] is not None
            or value["ref"] is not None
            or value["label_truncated"] is not False
            or value["observed_code_points"] != 0
            or value["retained_code_points"] != 0
        ):
            raise _CaseFailure("bundle-trajectory")
        return
    metadata = {
        "truncated": value["label_truncated"],
        "observed_code_points": value["observed_code_points"],
        "retained_code_points": value["retained_code_points"],
        "strategy": "head" if value["label_truncated"] else "none",
    }
    if (
        value["status"] != "present"
        or value["flavor"] not in {"posix", "windows", "unc"}
        or not isinstance(value["ref"], str)
        or not value["ref"].startswith("workspace_")
        or _OPAQUE_REF_RE.fullmatch(value["ref"]) is None
        or not _bounded_text_valid(
            value["label"],
            metadata,
            _EXPECTED_BOUNDS["workspace_label_code_points"],
        )
    ):
        raise _CaseFailure("bundle-trajectory")


def _validate_trajectory_record(record: Mapping[str, object], index: int) -> None:
    record_type = record.get("type")
    if not isinstance(record_type, str) or record_type not in _RECORD_FIELDS:
        raise _CaseFailure("bundle-trajectory")
    required = {
        "type",
        "record_id",
        "record_index",
        "timestamp",
        "source_ref",
    } | _RECORD_FIELDS[record_type]
    if not required <= set(record) or not set(record) <= required | _RELATIONSHIP_KEYS:
        raise _CaseFailure("bundle-trajectory")
    if (
        not isinstance(record["record_id"], str)
        or _RECORD_ID_RE.fullmatch(record["record_id"]) is None
        or record["record_id"] != f"r{index:06d}"
        or record["record_index"] != index
        or (
            record["timestamp"] is not None
            and (
                not isinstance(record["timestamp"], str)
                or _TIMESTAMP_RE.fullmatch(record["timestamp"]) is None
            )
        )
        or not _valid_source_ref(record["source_ref"], meta=record_type == "meta")
    ):
        raise _CaseFailure("bundle-trajectory")
    for key in _RELATIONSHIP_KEYS & set(record):
        if (
            not isinstance(record[key], str)
            or _OPAQUE_REF_RE.fullmatch(record[key]) is None
        ):
            raise _CaseFailure("bundle-trajectory")

    if record_type == "meta":
        if (
            index != 0
            or record["timestamp"] is not None
            or record["trajectory_schema"] != _TRAJECTORY_SCHEMA
            or record["provider_id"] != "codex"
            or record["adapter_id"] != "codex-rollout-v1"
            or record["source_format"] != "rollout-v1"
            or record["content_profile"] != "bounded-normalized-v1"
            or not isinstance(record["thread_ref"], str)
            or _OPAQUE_THREAD_REF_RE.fullmatch(record["thread_ref"]) is None
            or bool(_RELATIONSHIP_KEYS & set(record))
        ):
            raise _CaseFailure("bundle-trajectory")
        _validate_workspace(record["workspace"])
    elif record_type == "message":
        task_refs = record["task_refs"]
        if (
            record["role"] not in {"user", "assistant"}
            or not _bounded_text_valid(
                record["content"],
                record["content_meta"],
                _EXPECTED_BOUNDS["message_context_code_points"],
            )
            or not isinstance(task_refs, list)
            or len(task_refs)
            > _EXPECTED_BOUNDS["task_reference_occurrences"]
            or len(set(task_refs)) != len(task_refs)
            or any(not _valid_task_reference(item) for item in task_refs)
        ):
            raise _CaseFailure("bundle-trajectory")
    elif record_type == "reasoning":
        if (
            record["reasoning_kind"] not in {"summary", "full"}
            or not _bounded_text_valid(
                record["content"],
                record["content_meta"],
                _EXPECTED_BOUNDS["reasoning_code_points"],
            )
        ):
            raise _CaseFailure("bundle-trajectory")
    elif record_type == "tool_call":
        if (
            not isinstance(record["tool_call_id"], str)
            or not record["tool_call_id"].startswith("call_")
            or _OPAQUE_REF_RE.fullmatch(record["tool_call_id"]) is None
            or not _bounded_text_valid(
                record["name"],
                record["name_meta"],
                _EXPECTED_BOUNDS["tool_name_code_points"],
            )
            or record["arguments_kind"] not in {"json", "text", "absent"}
            or not _bounded_text_valid(
                record["arguments"],
                record["arguments_meta"],
                _EXPECTED_BOUNDS["tool_arguments_code_points"],
                allow_none=True,
            )
            or not isinstance(record["name_fingerprint"], str)
            or re.fullmatch(r"[0-9a-f]{64}", record["name_fingerprint"]) is None
            or (
                record["arguments_kind"] == "absent"
                and (
                    record["arguments"] is not None
                    or record["arguments_fingerprint"] is not None
                )
            )
            or (
                record["arguments_kind"] != "absent"
                and (
                    not isinstance(record["arguments_fingerprint"], str)
                    or re.fullmatch(
                        r"[0-9a-f]{64}",
                        record["arguments_fingerprint"],
                    )
                    is None
                )
            )
        ):
            raise _CaseFailure("bundle-trajectory")
    elif record_type == "tool_result":
        if (
            not isinstance(record["tool_call_id"], str)
            or not record["tool_call_id"].startswith("call_")
            or _OPAQUE_REF_RE.fullmatch(record["tool_call_id"]) is None
            or not _bounded_text_valid(
                record["content"],
                record["content_meta"],
                _EXPECTED_BOUNDS["tool_result_code_points"],
            )
            or record["status"] not in {"success", "error", "unknown"}
            or record["link_status"] not in {"linked", "unresolved"}
        ):
            raise _CaseFailure("bundle-trajectory")
    elif record_type == "context":
        attributes = record["attributes"]
        attributes_meta = record["attributes_meta"]
        if (
            record["context_kind"]
            not in {"system", "developer", "tool_config", "turn"}
            or not _bounded_text_valid(
                record["content"],
                record["content_meta"],
                _EXPECTED_BOUNDS["message_context_code_points"],
                allow_none=True,
            )
            or not isinstance(attributes, Mapping)
            or not isinstance(attributes_meta, Mapping)
            or set(attributes) != set(attributes_meta)
            or len(attributes) > _EXPECTED_BOUNDS["context_attribute_keys"]
            or not isinstance(record["fingerprint"], str)
            or re.fullmatch(r"[0-9a-f]{64}", record["fingerprint"]) is None
        ):
            raise _CaseFailure("bundle-trajectory")
    elif record_type == "event":
        if record["event_kind"] not in {
            "turn_start",
            "turn_complete",
            "turn_abort",
            "agent_start",
            "agent_complete",
            "compaction",
            "approval",
            "error",
        }:
            raise _CaseFailure("bundle-trajectory")


def _validate_trajectory(
    trajectory: bytes,
) -> tuple[list[Mapping[str, object]], dict[str, object]]:
    if (
        not trajectory
        or not trajectory.endswith(b"\n")
        or len(trajectory) > _EXPECTED_BOUNDS["trajectory_bytes"]
    ):
        raise _CaseFailure("bundle-trajectory")
    records: list[Mapping[str, object]] = []
    for line in trajectory.splitlines(keepends=True):
        if (
            line == b"\n"
            or not line.endswith(b"\n")
            or len(line) > _EXPECTED_BOUNDS["native_line_bytes"]
        ):
            raise _CaseFailure("bundle-trajectory")
        value = _strict_json_value(line[:-1], "bundle-trajectory")
        if (
            not isinstance(value, Mapping)
            or _canonical_json_bytes(value, newline=True) != line
        ):
            raise _CaseFailure("bundle-trajectory")
        _validate_trajectory_record(value, len(records))
        records.append(value)
        if len(records) > _EXPECTED_BOUNDS["records"]:
            raise _CaseFailure("bundle-trajectory")
    if (
        not records
        or records[0]["type"] != "meta"
        or sum(record["type"] == "meta" for record in records) != 1
    ):
        raise _CaseFailure("bundle-trajectory")

    records_by_type = {
        record_type: sum(record["type"] == record_type for record in records)
        for record_type in _RECORD_TYPES
    }
    messages_by_role = {
        role: sum(
            record["type"] == "message" and record["role"] == role
            for record in records
        )
        for role in ("user", "assistant")
    }
    stats: dict[str, object] = {
        "records_emitted": len(records),
        "trajectory_bytes": len(trajectory),
        "records_by_type": records_by_type,
        "messages_by_role": messages_by_role,
        "tool_calls": records_by_type["tool_call"],
        "tool_results": records_by_type["tool_result"],
        "task_references": sum(
            len(record["task_refs"])
            for record in records
            if record["type"] == "message"
        ),
    }
    return records, stats


def _nonnegative_integer_map(value: object, keys: set[str]) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == keys
        and all(_is_integer(item) and item >= 0 for item in value.values())
    )


def _validate_manifest(
    manifest: object,
    manifest_bytes: bytes,
    trajectory: bytes,
    records: list[Mapping[str, object]],
    trajectory_stats: Mapping[str, object],
) -> Mapping[str, object]:
    if (
        not isinstance(manifest, Mapping)
        or set(manifest) != _MANIFEST_KEYS
        or manifest["format"] != _BUNDLE_FORMAT
        or manifest["schema_version"] != _BUNDLE_SCHEMA_VERSION
        or manifest["result_status"] not in {"ready", "partial"}
        or _canonical_json_bytes(manifest, newline=True) != manifest_bytes
    ):
        raise _CaseFailure("bundle-manifest")

    trajectory_shape = manifest["trajectory"]
    trajectory_digest = hashlib.sha256(trajectory).hexdigest()
    if (
        not isinstance(trajectory_shape, Mapping)
        or set(trajectory_shape)
        != {"schema", "member", "sha256", "bytes", "records"}
        or trajectory_shape["schema"] != _TRAJECTORY_SCHEMA
        or trajectory_shape["member"] != "trajectory.jsonl"
        or trajectory_shape["sha256"] != trajectory_digest
        or trajectory_shape["bytes"] != len(trajectory)
        or trajectory_shape["records"] != len(records)
    ):
        raise _CaseFailure("bundle-manifest")

    exporter = manifest["exporter"]
    source = manifest["source"]
    if (
        not isinstance(exporter, Mapping)
        or set(exporter)
        != {"name", "version", "normalizer_name", "normalizer_version"}
        or exporter["name"] != "svc"
        or not isinstance(exporter["version"], str)
        or exporter["normalizer_name"] != "svc-agent-thread-normalizer"
        or exporter["normalizer_version"] != 1
        or not isinstance(manifest["generated_at"], str)
        or _TIMESTAMP_RE.fullmatch(manifest["generated_at"]) is None
        or not isinstance(source, Mapping)
        or set(source)
        != {
            "provider_id",
            "adapter_id",
            "source_format",
            "thread_ref",
            "source_status",
        }
        or source["provider_id"] != "codex"
        or source["adapter_id"] != "codex-rollout-v1"
        or source["source_format"] != "rollout-v1"
        or not isinstance(source["thread_ref"], str)
        or _OPAQUE_THREAD_REF_RE.fullmatch(source["thread_ref"]) is None
        or source["source_status"] != "stable"
        or records[0]["thread_ref"] != source["thread_ref"]
        or manifest["policy"] != _EXPECTED_POLICY
    ):
        raise _CaseFailure("bundle-manifest")

    capabilities = manifest["capabilities"]
    capability_values = {
        "reasoning": {"full", "summary", "opaque", "absent"},
        "tool_linkage": {"explicit", "mixed", "synthesized", "absent"},
        "context": {"full", "partial", "absent"},
        "task_references": {"available", "unavailable"},
        "explicit_concurrency": {"available", "unavailable"},
        "timestamps": {"full", "partial", "absent"},
        "terminal_events": {"available", "unavailable"},
    }
    if (
        not isinstance(capabilities, Mapping)
        or set(capabilities) != set(capability_values)
        or any(
            capabilities[key] not in values
            for key, values in capability_values.items()
        )
    ):
        raise _CaseFailure("bundle-manifest")

    counts = manifest["counts"]
    if (
        not isinstance(counts, Mapping)
        or set(counts) != _COUNT_KEYS
        or any(
            not _is_integer(counts[key]) or counts[key] < 0
            for key in {
                "source_bytes_read",
                "source_events_seen",
                "records_emitted",
                "trajectory_bytes",
                "tool_calls",
                "tool_results",
                "task_references",
                "diagnostics_emitted",
                "diagnostics_suppressed",
            }
        )
        or counts["source_bytes_read"] > _EXPECTED_BOUNDS["source_bytes"]
        or not _nonnegative_integer_map(
            counts["records_by_type"], set(_RECORD_TYPES)
        )
        or not _nonnegative_integer_map(
            counts["messages_by_role"], {"user", "assistant"}
        )
        or any(counts[key] != value for key, value in trajectory_stats.items())
    ):
        raise _CaseFailure("bundle-counts")

    lossiness = manifest["lossiness"]
    if (
        not isinstance(lossiness, Mapping)
        or set(lossiness) != set(_LOSS_KEYS)
        or any(
            not _nonnegative_integer_map(lossiness[group], keys)
            for group, keys in _LOSS_KEYS.items()
        )
        or lossiness["dropped"]["provider_envelope"] < 1
        or lossiness["dropped"]["rate_limit_noise"] < 1
        or lossiness["truncated"]["tool_result"] < 1
    ):
        raise _CaseFailure("bundle-lossiness")

    diagnostics = manifest["diagnostics"]
    if (
        not isinstance(diagnostics, list)
        or len(diagnostics) > _EXPECTED_BOUNDS["diagnostics"]
        or any(
            not isinstance(item, Mapping)
            or not _is_integer(item.get("count"))
            or item["count"] <= 0
            or not isinstance(item.get("details"), Mapping)
            or len(item["details"])
            > _EXPECTED_BOUNDS["diagnostic_detail_keys"]
            for item in diagnostics
        )
        or counts["diagnostics_emitted"]
        != sum(item["count"] for item in diagnostics)
        or any(
            sentinel in _canonical_json_bytes(diagnostics).decode("utf-8")
            for sentinel in _PRIVATE_SENTINELS
        )
    ):
        raise _CaseFailure("bundle-diagnostics")

    identity = {
        "normalizer_name": exporter["normalizer_name"],
        "normalizer_version": exporter["normalizer_version"],
        "source": source,
        "policy": manifest["policy"],
        "result_status": manifest["result_status"],
        "capabilities": capabilities,
        "counts": counts,
        "lossiness": lossiness,
        "diagnostics": diagnostics,
    }
    expected_bundle_id = hashlib.sha256(
        b"svc-agent-thread-bundle-v2\0"
        + trajectory
        + b"\0"
        + _canonical_json_bytes(identity)
    ).hexdigest()
    if (
        not isinstance(manifest["bundle_id"], str)
        or re.fullmatch(r"[0-9a-f]{64}", manifest["bundle_id"]) is None
        or manifest["bundle_id"] != expected_bundle_id
    ):
        raise _CaseFailure("bundle-identity")
    return manifest


def _validate_bundle(path: Path) -> Mapping[str, object]:
    try:
        info = path.lstat()
        if (
            stat.S_ISLNK(info.st_mode)
            or _is_reparse_point(info)
            or not stat.S_ISREG(info.st_mode)
            or info.st_size <= 0
            or info.st_size > _EXPECTED_BOUNDS["schema_v2_zip_bytes"]
            or (
                os.name != "nt"
                and stat.S_IMODE(info.st_mode) != 0o600
            )
        ):
            raise _CaseFailure("bundle-file")
        with zipfile.ZipFile(path, mode="r") as archive:
            infos = archive.infolist()
            names = tuple(item.filename for item in infos)
            if (
                names != _BUNDLE_MEMBERS
                or any(
                    token in name.lower()
                    for name in names
                    for token in ("native", "raw", "task", "analysis")
                )
            ):
                raise _CaseFailure("bundle-members")
            limits = {
                "manifest.json": _EXPECTED_BOUNDS["manifest_bytes"],
                "trajectory.jsonl": _EXPECTED_BOUNDS["trajectory_bytes"],
            }
            member_bytes: dict[str, bytes] = {}
            for member in infos:
                if (
                    member.is_dir()
                    or member.date_time != (1980, 1, 1, 0, 0, 0)
                    or member.compress_type != zipfile.ZIP_DEFLATED
                    or stat.S_IMODE(member.external_attr >> 16) != 0o600
                    or member.file_size < 0
                    or member.file_size > limits[member.filename]
                ):
                    raise _CaseFailure("bundle-members")
                with archive.open(member, mode="r") as stream:
                    data = stream.read(limits[member.filename] + 1)
                if len(data) != member.file_size or len(data) > limits[member.filename]:
                    raise _CaseFailure("bundle-members")
                member_bytes[member.filename] = data
    except _CaseFailure:
        raise
    except (
        FileNotFoundError,
        NotADirectoryError,
        PermissionError,
        OSError,
        RuntimeError,
        ValueError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
    ) as exc:
        raise _CaseFailure("bundle-file") from exc

    manifest_bytes = member_bytes["manifest.json"]
    trajectory = member_bytes["trajectory.jsonl"]
    manifest = _strict_json_value(manifest_bytes, "bundle-manifest")
    records, stats = _validate_trajectory(trajectory)
    validated = _validate_manifest(
        manifest,
        manifest_bytes,
        trajectory,
        records,
        stats,
    )
    normalized_bytes = manifest_bytes + trajectory
    if (
        _PRIVATE_SENTINELS[2].encode("utf-8") not in trajectory
        or any(
            _PRIVATE_SENTINELS[index].encode("utf-8") in normalized_bytes
            for index in (0, 1, 3, 4, 5, 6, 7)
        )
        or any(
            marker in trajectory
            for marker in (
                b'"session_meta"',
                b'"response_item"',
                b'"event_msg"',
                b'"encrypted_content"',
            )
        )
        or not any(
            record["type"] == "message"
            and _BUNDLE_TASK_REFERENCE in record["task_refs"]
            for record in records
        )
        or not any(
            record["type"] == "tool_result"
            and record["content_meta"]["truncated"] is True
            for record in records
        )
    ):
        raise _CaseFailure("bundle-normalization")
    return validated


def _validate_export_payload(
    payload: object,
    output: Path,
    manifest: Mapping[str, object],
) -> None:
    if not isinstance(payload, Mapping):
        raise _CaseFailure("bundle-output")
    bundle = payload.get("bundle")
    if (
        payload.get("schema_version") != 1
        or payload.get("command") != "telemetry agent-thread export"
        or payload.get("status") != "exported"
        or not isinstance(bundle, Mapping)
        or bundle.get("path") != os.fspath(output)
        or bundle.get("bundle_id") != manifest["bundle_id"]
        or bundle.get("trajectory") != manifest["trajectory"]
        or payload.get("source") != manifest["source"]
        or payload.get("result_status") != manifest["result_status"]
        or payload.get("capabilities") != manifest["capabilities"]
        or payload.get("counts") != manifest["counts"]
        or payload.get("lossiness") != manifest["lossiness"]
        or payload.get("diagnostics") != manifest["diagnostics"]
    ):
        raise _CaseFailure("bundle-output")


def _run_schema_v1_probe(
    child: Path,
    root: Path,
    environment: dict[str, str],
) -> None:
    output = root / "bundle-fixture" / "schema-v1.zip"
    result = _command(
        (
            child,
            "-c",
            _SCHEMA_V1_PROBE,
            output,
            _PRIVATE_SENTINELS[7],
        ),
        cwd=root,
        env=environment,
    )
    _bounded_child_output(result, "bundle-schema-v1")
    payload = _strict_json_value(result.stdout, "bundle-schema-v1")
    if (
        result.returncode != 0
        or result.stderr
        or payload
        != {
            "code": "unsupported-agent-thread-bundle-schema",
            "opened": ["manifest.json"],
        }
    ):
        raise _CaseFailure("bundle-schema-v1")


def _run_bundle_case(
    child: Path,
    root: Path,
    environment: dict[str, str],
) -> tuple[Path, Path]:
    source, output, repository, provider_home = _create_bundle_fixture(root)
    command = (
        child,
        "-m",
        "svc_cli.cli",
        "telemetry",
        "agent-thread",
        "export",
        "--source",
        source,
        "--output",
        output,
        "--repo",
        repository,
        "--include-sensitive",
        "--json",
    )
    result = _command(
        command,
        cwd=root,
        env=environment,
    )
    _bounded_child_output(result, "bundle-output")
    if result.returncode != 0:
        raise _CaseFailure("bundle-output")
    payload = _strict_json_value(result.stdout, "bundle-output")
    manifest = _validate_bundle(output)
    _validate_export_payload(payload, output, manifest)

    before = output.lstat()
    before_digest = hashlib.sha256(output.read_bytes()).hexdigest()
    repeated = _command(command, cwd=root, env=environment)
    _bounded_child_output(repeated, "bundle-no-overwrite")
    repeated_payload = _strict_json_value(
        repeated.stderr,
        "bundle-no-overwrite",
    )
    error = (
        repeated_payload.get("error")
        if isinstance(repeated_payload, Mapping)
        else None
    )
    after = output.lstat()
    if (
        repeated.returncode == 0
        or repeated.stdout
        or not isinstance(error, Mapping)
        or error.get("code") != "output-exists"
        or _identity(after) != _identity(before)
        or after.st_size != before.st_size
        or stat.S_IMODE(after.st_mode) != stat.S_IMODE(before.st_mode)
        or hashlib.sha256(output.read_bytes()).hexdigest() != before_digest
        or _validate_bundle(output) != manifest
    ):
        raise _CaseFailure("bundle-no-overwrite")
    _run_schema_v1_probe(child, root, environment)
    return output, provider_home


def _validate_analysis_payload(
    payload: object,
    encoded: bytes,
    bundle_id: object,
) -> None:
    if (
        len(encoded) > _MAX_ANALYSIS_BYTES
        or not isinstance(payload, Mapping)
        or set(payload) != _ANALYSIS_ROOT_KEYS
        or payload["format"] != "svc-agent-thread-analysis"
        or payload["schema_version"] != 1
        or payload["bundle_id"] != bundle_id
        or payload["analyzer"] != _ANALYSIS_ANALYZER
        or payload["result_status"] not in {"ready", "partial"}
        or _canonical_json_bytes(payload, newline=True) != encoded
    ):
        raise _CaseFailure("analysis-schema")
    dimensions = payload["dimensions"]
    metrics = payload["metrics"]
    if (
        not isinstance(dimensions, Mapping)
        or set(dimensions) != set(_ANALYSIS_DIMENSIONS)
        or not isinstance(metrics, Mapping)
        or set(metrics) != set(_ANALYSIS_DIMENSIONS)
        or any(
            not isinstance(entry, Mapping)
            or set(entry) != {"status", "finding_ids", "unknown_ids"}
            or entry["status"] not in {"available", "partial", "unavailable"}
            or not isinstance(entry["finding_ids"], list)
            or not isinstance(entry["unknown_ids"], list)
            for entry in dimensions.values()
        )
        or any(
            not isinstance(metrics[dimension], Mapping)
            or set(metrics[dimension]) != keys
            for dimension, keys in _ANALYSIS_METRIC_KEYS.items()
        )
    ):
        raise _CaseFailure("analysis-schema")

    findings = payload["findings"]
    unknowns = payload["unknowns"]
    if (
        not isinstance(findings, list)
        or not isinstance(unknowns, list)
        or len(findings) > 256
        or len(unknowns) > 256
        or any(
            not isinstance(item, Mapping)
            or set(item)
            != {
                "id",
                "dimension",
                "code",
                "kind",
                "confidence",
                "evidence_refs",
                "details",
            }
            or item["id"] != f"f{index:06d}"
            or item["dimension"] not in _ANALYSIS_DIMENSIONS
            or not isinstance(item["evidence_refs"], list)
            or not isinstance(item["details"], Mapping)
            for index, item in enumerate(findings, 1)
        )
        or any(
            not isinstance(item, Mapping)
            or set(item)
            != {
                "id",
                "dimension",
                "code",
                "cause",
                "evidence_refs",
                "details",
            }
            or item["id"] != f"u{index:06d}"
            or item["dimension"] not in _ANALYSIS_DIMENSIONS
            or not isinstance(item["evidence_refs"], list)
            or not isinstance(item["details"], Mapping)
            for index, item in enumerate(unknowns, 1)
        )
    ):
        raise _CaseFailure("analysis-schema")

    lossiness = payload["lossiness"]
    if (
        not isinstance(lossiness, Mapping)
        or set(lossiness) != {"bundle", "analysis"}
        or not isinstance(lossiness["bundle"], Mapping)
        or set(lossiness["bundle"])
        != {
            "mode",
            "source_status",
            "result_status",
            "dropped",
            "truncated",
            "unavailable",
            "synthesized",
            "partial_reasons",
        }
        or not isinstance(lossiness["analysis"], Mapping)
        or set(lossiness["analysis"])
        != {
            "limits_reached",
            "findings_omitted",
            "unknowns_omitted",
            "evidence_refs_omitted",
            "metric_entries_omitted",
        }
    ):
        raise _CaseFailure("analysis-schema")


def _run_analysis_import_probe(
    child: Path,
    bundle: Path,
    root: Path,
    environment: dict[str, str],
) -> None:
    result = _command(
        (child, "-c", _ANALYSIS_IMPORT_PROBE, bundle),
        cwd=root,
        env=environment,
    )
    _bounded_child_output(result, "analysis-import")
    payload = _strict_json_value(result.stdout, "analysis-import")
    if (
        result.returncode != 0
        or result.stderr
        or payload
        != {
            "code": 0,
            "root": True,
            "textual_imported": False,
            "tui_imported": False,
        }
    ):
        raise _CaseFailure("analysis-import")


def _run_analysis_case(
    child: Path,
    root: Path,
    environment: dict[str, str],
) -> None:
    bundle, provider_home = _run_bundle_case(
        child,
        root / "analysis-prerequisite",
        environment,
    )
    shutil.rmtree(provider_home)
    if provider_home.exists():
        raise _CaseFailure("analysis-provider-independence")
    command = (
        child,
        "-m",
        "svc_cli.cli",
        "telemetry",
        "agent-thread",
        "analyze",
        "--input",
        bundle,
        "--json",
    )
    first = _command(command, cwd=root, env=environment)
    _bounded_child_output(first, "analysis-output")
    if first.returncode != 0 or first.stderr:
        raise _CaseFailure("analysis-output")
    first_payload = _strict_json_value(first.stdout, "analysis-output")
    with zipfile.ZipFile(bundle, mode="r") as archive:
        manifest = _strict_json_value(
            archive.read("manifest.json"),
            "analysis-input",
        )
    if not isinstance(manifest, Mapping):
        raise _CaseFailure("analysis-input")
    _validate_analysis_payload(
        first_payload,
        first.stdout.encode("utf-8", errors="strict"),
        manifest["bundle_id"],
    )

    second = _command(command, cwd=root, env=environment)
    _bounded_child_output(second, "analysis-output")
    if (
        second.returncode != 0
        or second.stderr
        or second.stdout != first.stdout
    ):
        raise _CaseFailure("analysis-determinism")
    _run_analysis_import_probe(child, bundle, root, environment)


def _run_ui_case(
    child: Path,
    root: Path,
    environment: dict[str, str],
) -> None:
    bundle, provider_home = _run_bundle_case(
        child,
        root / "ui-prerequisite",
        environment,
    )
    shutil.rmtree(provider_home)
    if provider_home.exists():
        raise _CaseFailure("ui-provider-independence")
    result = _command(
        (child, "-c", _UI_PROBE, bundle),
        cwd=root,
        env=environment,
    )
    _bounded_child_output(result, "ui-output")
    payload = _strict_json_value(result.stdout, "ui-output")
    if (
        result.returncode != 0
        or result.stderr
        or payload
        != {
            "entered": 2,
            "quits": ["q", "escape"],
            "restored": True,
            "sizes": [[80, 24], [30, 10]],
            "views": 8,
        }
    ):
        raise _CaseFailure("ui-output")


def _base_report(slice_name: str, *, status: str, exit_code: int, digest: str | None = None) -> dict[str, Any]:
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


def _emit(report: dict[str, Any]) -> None:
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))


def _slice_cases(slice_name: str) -> tuple[str, ...]:
    if slice_name == "inventory":
        return ("inventory",)
    if slice_name == "bundle":
        return ("bundle",)
    if slice_name == "analysis":
        return ("analysis",)
    if slice_name == "ui":
        return ("ui",)
    if slice_name == "all":
        return ("inventory", "bundle", "analysis", "ui")
    raise HarnessError(2, "slice")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        options = _parser().parse_args(argv)
    except HarnessError as exc:
        report = _base_report("unknown", status="failed", exit_code=exc.exit_code)
        report["error"] = exc.reason
        report["cleanup"] = "not-started"
        _emit(report)
        return exc.exit_code

    report = _base_report(options.slice, status="failed", exit_code=1)
    temporary_root: Path | None = None
    cleanup_error = False
    active_case: str | None = None
    case_statuses: dict[str, str] = {}
    try:
        selected_cases = _slice_cases(options.slice)
        if sys.version_info < (3, 11):
            raise HarnessError(3, "python")
        try:
            import ensurepip  # noqa: F401
        except ImportError as exc:
            raise HarnessError(3, "ensurepip") from exc
        # The child process runs from its private temporary root, so preserve
        # caller paths as absolute lexical paths without resolving links.
        wheel = options.wheel.absolute()
        wheelhouse = options.wheelhouse.absolute()
        digest = _validate_inputs(wheel, options.expected_sha256, wheelhouse)
        report["wheel_sha256"] = digest
        try:
            temporary_root = Path(tempfile.mkdtemp(prefix="svc-accept-"))
        except (OSError, RuntimeError) as exc:
            raise HarnessError(3, "temporary-directory") from exc
        environment = _isolated_environment()
        # Keep pip's cache inside the exact harness-owned root as well; the
        # acceptance run must not leave state in the caller's home directory.
        environment["PIP_CACHE_DIR"] = os.fspath(temporary_root / "pip-cache")
        child_tmp = temporary_root / "tmp"
        child_tmp.mkdir()
        for key in ("TMPDIR", "TMP", "TEMP"):
            environment[key] = os.fspath(child_tmp)
        staged_wheel = _stage_wheel(wheel, digest, temporary_root)
        child = _create_virtualenv(temporary_root)
        _install_wheel(child, staged_wheel, wheelhouse, temporary_root, environment)
        report["installed"] = _installed_versions(child, temporary_root, environment)
        runners = {
            "inventory": _run_inventory_case,
            "bundle": _run_bundle_case,
            "analysis": _run_analysis_case,
            "ui": _run_ui_case,
        }
        for case_name in selected_cases:
            active_case = case_name
            runners[case_name](child, temporary_root, environment)
            case_statuses[case_name] = "passed"
            report["cases"] = dict(case_statuses)
        active_case = None
        report["status"] = "passed"
        report["exit_code"] = 0
    except _CaseFailure:
        report["error"] = "case"
        if active_case is not None:
            case_statuses[active_case] = "failed"
        report["cases"] = dict(case_statuses)
        report["exit_code"] = 6
    except HarnessError as exc:
        report["error"] = exc.reason
        report["exit_code"] = exc.exit_code
    except (OSError, RuntimeError, sqlite3.DatabaseError, subprocess.SubprocessError):
        report["error"] = "case"
        if active_case is not None:
            case_statuses[active_case] = "failed"
        report["cases"] = dict(case_statuses)
        report["exit_code"] = 6
    finally:
        if temporary_root is not None:
            try:
                shutil.rmtree(temporary_root)
                if temporary_root.exists():
                    cleanup_error = True
            except (OSError, RuntimeError):
                cleanup_error = True
        report["cleanup"] = "failed" if cleanup_error else ("passed" if temporary_root is not None else "not-started")
    if cleanup_error:
        report["status"] = "failed"
        report["error"] = "cleanup"
        report["exit_code"] = 7
    _emit(report)
    return int(report["exit_code"])


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
