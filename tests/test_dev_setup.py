from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path

import pytest

from svc_cli.dev.setup import plan_setup
from svc_cli.errors import SvcError
from svc_cli.plans import apply_local_plan


def write_config(root: Path, targets: tuple[str, ...] = ("frontend",)) -> None:
    target = {
        "probe": {"kind": "exec", "argv": ["true"]},
        "provision": {"kind": "manual"},
    }
    value = {
        "schema_version": 2,
        "svc_version": "10.0.1",
        "dev": {"profile": "local", "profiles": {"local": {"targets": {name: target for name in targets}}}},
    }
    (root / "svc.json").write_text(json.dumps(value), encoding="utf-8")


def test_vscode_jsonc_insert_is_surgical_idempotent_and_leaves_launch_untouched() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_config(root, ("frontend", "backend"))
        vscode = root / ".vscode"
        vscode.mkdir()
        tasks = vscode / "tasks.json"
        original = (
            b"{\r\n"
            b"  // Consumer comment\r\n"
            b"  \"version\": \"2.0.0\",\r\n"
            b"  \"tasks\": [\r\n"
            b"    {\"label\":\"consumer\",\"command\":\"keep\"},\r\n"
            b"  ],\r\n"
            b"}\r\n"
        )
        tasks.write_bytes(original)
        launch = vscode / "launch.json"
        launch.write_bytes(b'{"consumer":true}\r\n')
        before_launch = launch.read_bytes()

        plan = plan_setup(root, "vscode")
        assert plan.status == "ready"
        assert tasks.read_bytes() == original
        apply_local_plan(plan, plan.digest)
        updated = tasks.read_bytes()
        assert b"// Consumer comment\r\n" in updated
        assert b'{"label":"consumer","command":"keep"}' in updated
        assert b"svc:dev:begin target=frontend" in updated
        assert b"svc:dev:begin target=backend" in updated
        assert b"\n" not in updated.replace(b"\r\n", b"")
        assert launch.read_bytes() == before_launch
        assert plan_setup(root, "vscode").status == "noop"


@pytest.mark.parametrize("conflict", ("edited-managed-task", "reserved-consumer-label"))
def test_vscode_ownership_conflicts_block_without_writing(tmp_path: Path, conflict: str) -> None:
    write_config(tmp_path)
    if conflict == "edited-managed-task":
        initial = plan_setup(tmp_path, "vscode")
        apply_local_plan(initial, initial.digest)
        tasks = tmp_path / ".vscode" / "tasks.json"
        original = tasks.read_bytes().replace(b'"command": "svc"', b'"command": "consumer"')
    else:
        (tmp_path / ".vscode").mkdir()
        tasks = tmp_path / ".vscode" / "tasks.json"
        original = b'{"version":"2.0.0","tasks":[{"label":"svc:dev:frontend"}]}'
    tasks.write_bytes(original)

    blocked = plan_setup(tmp_path, "vscode")

    assert "invalid-vscode-tasks" in {item.code for item in blocked.blockers}
    assert tasks.read_bytes() == original


def test_npm_update_is_surgical_idempotent_and_preserves_mode() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_config(root)
        package = root / "package.json"
        original = b'{\n  "name": "consumer",\n  "scripts": {\n    "test": "pytest"\n  }\n}\n'
        package.write_bytes(original)
        package.chmod(0o640)
        plan = plan_setup(root, "npm")
        assert plan.status == "ready"
        apply_local_plan(plan, plan.digest)
        updated = package.read_bytes()
        assert b'"test": "pytest",' in updated
        assert b'"svc:dev:frontend": "svc dev ensure frontend"' in updated
        assert stat.S_IMODE(package.stat().st_mode) == 0o640
        assert plan_setup(root, "npm").status == "noop"


def test_npm_rejects_managed_script_drift(tmp_path: Path) -> None:
    write_config(tmp_path)
    package = tmp_path / "package.json"
    package.write_text('{"name":"consumer"}', encoding="utf-8")
    initial = plan_setup(tmp_path, "npm")
    apply_local_plan(initial, initial.digest)
    drifted = package.read_bytes().replace(b"svc dev ensure frontend", b"consumer command")
    package.write_bytes(drifted)

    blocked = plan_setup(tmp_path, "npm")

    assert "invalid-package-json" in {item.code for item in blocked.blockers}
    assert package.read_bytes() == drifted


def test_npm_rejects_malformed_package_json(tmp_path: Path) -> None:
    write_config(tmp_path)
    package = tmp_path / "package.json"
    malformed = b'{"scripts":{"test":"ok",}}'
    package.write_bytes(malformed)

    blocked = plan_setup(tmp_path, "npm")

    assert "invalid-package-json" in {item.code for item in blocked.blockers}
    assert package.read_bytes() == malformed


def test_plan_digest_binds_config_and_destination_bytes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_config(root)
        (root / "package.json").write_text('{"name":"consumer"}', encoding="utf-8")
        plan = plan_setup(root, "npm")
        (root / "package.json").write_text('{"name":"changed"}', encoding="utf-8")
        with pytest.raises(SvcError) as raised:
            apply_local_plan(plan, plan.digest)
        assert raised.value.code == "stale-plan"

        first = plan_setup(root, "npm")
        write_config(root, ("frontend", "backend"))
        second = plan_setup(root, "npm")
        assert first.digest != second.digest


def test_vscode_parent_symlink_swap_after_planning_is_stale_and_writes_nothing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_config(root)
        plan = plan_setup(root, "vscode")
        redirected = root / "redirected"
        redirected.mkdir()
        try:
            os.symlink(redirected, root / ".vscode")
        except OSError as error:
            pytest.skip(f"symlinks unavailable: {error}")
        with pytest.raises(SvcError) as raised:
            apply_local_plan(plan, plan.digest)
        assert raised.value.code == "stale-plan"
        assert not (redirected / "tasks.json").exists()
