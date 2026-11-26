from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from svc_cli.errors import SvcError
from svc_cli.telemetry.agent_threads import ProviderContext, ThreadSelection
from svc_cli.telemetry.providers import CodexRolloutProvider


def _envelope(record_type: str, payload: object) -> dict[str, object]:
    return {
        "timestamp": "2026-01-01T00:00:00Z",
        "type": record_type,
        "payload": payload,
    }


def _source(path: Path, thread_id: str = "thread-rollout") -> bytes:
    records = (
        _envelope("session_meta", {"id": thread_id}),
        _envelope(
            "response_item",
            {"type": "message", "role": "user", "content": "raw"},
        ),
    )
    native = (
        "\n".join(json.dumps(item, separators=(",", ":")) for item in records) + "\n"
    ).encode()
    path.write_bytes(native)
    return native


def _resolved(provider: CodexRolloutProvider, source: Path):
    return provider.resolve(
        ProviderContext(home=source.parent),
        ThreadSelection(source=source),
    )


def test_resolution_rejects_mismatched_id_and_missing_source(tmp_path: Path) -> None:
    provider = CodexRolloutProvider()
    selected = tmp_path / "selected.jsonl"
    _source(selected, "actual-thread")
    with sqlite3.connect(tmp_path / "state_5.sqlite") as database:
        database.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT)")
        database.execute(
            "INSERT INTO threads VALUES (?, ?)",
            ("selected-thread", selected.name),
        )
    with pytest.raises(SvcError) as raised:
        provider.resolve(
            ProviderContext(home=tmp_path),
            ThreadSelection(thread_id="selected-thread"),
        )
    assert raised.value.code == "thread-source-incompatible"

    with pytest.raises(SvcError) as raised:
        _resolved(provider, tmp_path / "missing.jsonl")
    assert raised.value.code == "thread-source-not-found"
