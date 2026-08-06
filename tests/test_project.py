from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

import svc_cli.plans as plans
import svc_cli.project as project
from svc_cli.errors import SvcError
from svc_cli.integration import local_config_ignore_body, navigation_body, skill_body
from svc_cli.plans import apply_local_plan
from svc_cli.project import (
    AGENTS_FILE,
    CODEX_SKILL_FILE,
    DOCS_INDEX_FILE,
    PROJECT_FILE,
    inspect_status,
    parse_project_state,
    plan_adopt,
    plan_init,
    render_project_state,
)


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_init_plan_is_deterministic_and_side_effect_free() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        before = tree_bytes(root)
        first = plan_init(root)
        second = plan_init(root)
        assert first.as_dict() == second.as_dict()
        assert tree_bytes(root) == before
        assert {write.path for write in first.writes} == {
            PROJECT_FILE,
            CODEX_SKILL_FILE,
            AGENTS_FILE,
            DOCS_INDEX_FILE,
            ".gitignore",
        }


def test_generated_guidance_is_a_thin_router_to_the_installed_corpus() -> None:
    skill = skill_body()
    navigation = navigation_body()

    for content in (skill, navigation):
        assert "svc lookup --list --json" in content
        assert "svc lookup --path <path> --json" in content
        assert "svc lookup --keyword" in content

    assert "This Skill is a router, not a copy of SVC guidance." in skill
    assert "Consumer-owned instructions" in skill
    assert "returned plan is not approval" in skill
    assert "first SVC command" in skill
    assert "Human authorization" in skill
    assert skill.index("svc status --json") < skill.index("svc lookup --list --json")
    assert navigation.index("svc status --json") < navigation.index("svc lookup --list --json")
    assert "## Declare Development Capabilities" not in skill
    assert "svc dev setup" not in skill
    assert "svc self-update" not in skill


def test_init_apply_produces_a_healthy_idempotent_project() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = plan_init(root)
        result = apply_local_plan(first, first.digest)
        assert result["status"] == "applied"
        assert parse_project_state((root / PROJECT_FILE).read_bytes()).svc_version == first.target_version
        assert (root / CODEX_SKILL_FILE).is_file()
        assert (root / DOCS_INDEX_FILE).is_file()
        assert b"svc:begin local-config" in (root / ".gitignore").read_bytes()
        assert not (root / "svc.local.json").exists()
        initial_status = inspect_status(root)
        assert initial_status["healthy"]
        assert initial_status["run"] == {
            "status": "not-declared",
            "observation": "declaration-only",
            "entries": [],
        }

        repeat = plan_init(root)
        assert repeat.status == "noop"
        snapshot = tree_bytes(root)
        assert apply_local_plan(repeat, repeat.digest)["status"] == "noop"
        assert tree_bytes(root) == snapshot


def test_init_preserves_unmarked_consumer_content_and_creates_docs_index() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        agents = b"# Consumer rules\n\nKeep this verbatim.\n"
        docs = b"# Existing docs\n\nKeep this too.\n"
        (root / AGENTS_FILE).write_bytes(agents)
        (root / "docs").mkdir()
        (root / DOCS_INDEX_FILE).write_bytes(docs)

        plan = plan_init(root)
        apply_local_plan(plan, plan.digest)
        assert (root / AGENTS_FILE).read_bytes().startswith(agents)
        assert (root / DOCS_INDEX_FILE).read_bytes().startswith(docs)
        assert b"svc:begin navigation" in (root / AGENTS_FILE).read_bytes()
        assert b"svc:begin navigation" in (root / DOCS_INDEX_FILE).read_bytes()


@pytest.mark.parametrize(
    ("relative_path", "old", "new", "expected_code"),
    (
        (AGENTS_FILE, b"This project uses", b"This project secretly uses", "generated-guidance-drift"),
        (CODEX_SKILL_FILE, b"name: svc", b"name: consumer-svc", "generated-skill-drift"),
    ),
)
def test_modified_generated_surface_blocks_without_overwrite(
    tmp_path: Path,
    relative_path: str,
    old: bytes,
    new: bytes,
    expected_code: str,
) -> None:
    initial = plan_init(tmp_path)
    apply_local_plan(initial, initial.digest)
    surface = tmp_path / relative_path
    content = surface.read_bytes()
    assert old in content
    surface.write_bytes(content.replace(old, new, 1))
    before = tree_bytes(tmp_path)

    plan = plan_init(tmp_path)

    assert expected_code in {blocker.code for blocker in plan.blockers}
    with pytest.raises(SvcError, match="unresolved blockers"):
        apply_local_plan(plan, plan.digest)
    assert tree_bytes(tmp_path) == before


def test_unowned_existing_skill_is_never_replaced() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        skill = root / CODEX_SKILL_FILE
        skill.parent.mkdir(parents=True)
        skill.write_text("# My own skill\n", encoding="utf-8")
        before = tree_bytes(root)
        plan = plan_init(root)
        assert "generated-skill-drift" in {blocker.code for blocker in plan.blockers}
        with pytest.raises(SvcError):
            apply_local_plan(plan, plan.digest)
        assert tree_bytes(root) == before


def test_stale_plan_detects_consumer_change_before_any_write() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        stale = plan_init(root)
        (root / AGENTS_FILE).write_text("concurrent consumer change\n", encoding="utf-8")
        with pytest.raises(SvcError, match="changed after planning"):
            apply_local_plan(stale, stale.digest)
        assert not (root / PROJECT_FILE).exists()


@pytest.mark.parametrize("failure", ("commit", "postcondition"))
def test_apply_failure_rolls_back_the_partial_project_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    plan = plan_init(tmp_path)
    before = tree_bytes(tmp_path)
    expected_code = "apply-failed" if failure == "commit" else "postcondition-failed"

    if failure == "commit":
        original = plans._commit_write
        calls = 0

        def fail_second(path: Path, content: bytes) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected write failure")
            original(path, content)

        monkeypatch.setattr(plans, "_commit_write", fail_second)
    else:
        def fail_postconditions(*args: object, **kwargs: object) -> None:
            raise SvcError("postcondition-failed", "injected postcondition failure")

        monkeypatch.setattr(plans, "_verify_postconditions", fail_postconditions)

    with pytest.raises(SvcError) as raised:
        apply_local_plan(plan, plan.digest)

    assert raised.value.code == expected_code
    assert raised.value.details["rollback"] == "succeeded"
    assert tree_bytes(tmp_path) == before


def test_rollback_does_not_overwrite_an_intervening_consumer_change(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        plan = plan_init(root)
        original = plans._commit_write
        calls = 0

        def fail_after_consumer_change(path: Path, content: bytes) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                (root / PROJECT_FILE).write_text("consumer change\n", encoding="utf-8")
                raise OSError("injected write failure")
            original(path, content)

        with monkeypatch.context() as patch:
            patch.setattr(plans, "_commit_write", fail_after_consumer_change)
            with pytest.raises(SvcError) as raised:
                apply_local_plan(plan, plan.digest)
        assert raised.value.code == "apply-failed"
        assert raised.value.details["rollback"] == "conflicted"
        assert (root / PROJECT_FILE).read_text(encoding="utf-8") == "consumer change\n"


def test_status_distinguishes_adoption_and_adopt_updates_only_project_metadata() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        initial = plan_init(root)
        apply_local_plan(initial, initial.digest)
        (root / PROJECT_FILE).write_bytes(render_project_state("9.9.9"))
        status = inspect_status(root)
        assert status["status"] == "actionable"
        assert status["project"]["status"] == "adoption-pending"
        assert status["next"]["action"] == "review-and-adopt"
        assert status["next"]["requires_human_authorization"]
        assert not status["healthy"]

        adopt = plan_adopt(root)
        assert [write.path for write in adopt.writes] == [PROJECT_FILE]
        apply_local_plan(adopt, adopt.digest)
        assert inspect_status(root)["healthy"]


def test_status_reports_installed_runtime_version_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        initial = plan_init(root)
        apply_local_plan(initial, initial.digest)
        mismatch_version = "0.0.0" if initial.target_version != "0.0.0" else "0.0.1"
        with monkeypatch.context() as patch:
            patch.setattr(project, "installed_distribution_version", lambda: mismatch_version)
            mismatch = inspect_status(root)
        assert mismatch["runtime"]["status"] == "mismatch"
        assert mismatch["status"] == "actionable"
        assert mismatch["next"]["command"] == ["svc", "self-update", "--json"]
        assert not mismatch["healthy"]


def test_status_lists_run_entries_as_declarations_without_execution(tmp_path: Path) -> None:
    initial = plan_init(tmp_path)
    apply_local_plan(initial, initial.digest)
    configuration = json.loads((tmp_path / PROJECT_FILE).read_text(encoding="utf-8"))
    configuration["run"] = {
        "z-last": {"argv": ["never-start-this"]},
        "a-first": {"argv": ["never-start-this-either"]},
    }
    (tmp_path / PROJECT_FILE).write_text(json.dumps(configuration), encoding="utf-8")

    status = inspect_status(tmp_path)
    assert status["run"] == {
        "status": "declared",
        "observation": "declaration-only",
        "entries": ["a-first", "z-last"],
    }


def test_status_makes_unadopted_state_and_authorization_gate_explicit(tmp_path: Path) -> None:
    before = tree_bytes(tmp_path)

    status = inspect_status(tmp_path)

    assert status["status"] == "unadopted"
    assert status["project"]["status"] == "missing"
    assert status["configuration"] == {"status": "not-configured"}
    assert status["dev"] == {
        "status": "unavailable",
        "observation": "declaration-only",
        "profile": None,
        "targets": [],
    }
    assert status["run"] == {
        "status": "unavailable",
        "observation": "declaration-only",
        "entries": [],
    }
    assert status["next"] == {
        "action": "request-adoption-authorization",
        "reason": "SVC is not adopted; obtain Human authorization before running svc init.",
        "requires_human_authorization": True,
    }
    assert not status["healthy"]
    assert tree_bytes(tmp_path) == before


@pytest.mark.parametrize(
    ("filename", "content"),
    (
        (PROJECT_FILE, b"{not-json"),
        ("svc.local.json", b"{}\n"),
    ),
)
def test_status_reports_malformed_project_state_without_suggesting_init(
    tmp_path: Path,
    filename: str,
    content: bytes,
) -> None:
    (tmp_path / filename).write_bytes(content)
    before = tree_bytes(tmp_path)

    status = inspect_status(tmp_path)

    assert status["status"] == "malformed"
    assert status["next"]["action"] == "repair-project-configuration"
    assert status["next"]["requires_human_authorization"]
    assert "command" not in status["next"]
    assert tree_bytes(tmp_path) == before


def test_status_reports_schema_v1_as_actionable_migration(tmp_path: Path) -> None:
    (tmp_path / PROJECT_FILE).write_text(
        '{"schema_version":1,"svc_version":"10.0.0"}\n',
        encoding="utf-8",
    )

    status = inspect_status(tmp_path)

    assert status["status"] == "actionable"
    assert status["project"]["status"] == "schema-v1-write-blocked"
    assert status["configuration"]["status"] == "not-inspected"
    assert status["next"]["action"] == "migrate-project-configuration"
    assert status["next"]["requires_human_authorization"]


def test_status_summarizes_declared_dev_targets_without_observing_them(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial = plan_init(tmp_path)
    apply_local_plan(initial, initial.digest)
    (tmp_path / PROJECT_FILE).write_text(
        json.dumps(
            {
                "schema_version": 2,
                "svc_version": initial.target_version,
                "dev": {
                    "profile": "local",
                    "profiles": {
                        "local": {
                            "targets": {
                                "web": {
                                    "probe": {"kind": "exec", "argv": ["unreachable-probe"]},
                                    "provision": {"kind": "manual"},
                                },
                                "api": {
                                    "probe": {"kind": "exec", "argv": ["unreachable-probe"]},
                                    "provision": {"kind": "manual"},
                                },
                            }
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    def unexpected_probe(*args: object, **kwargs: object) -> object:
        raise AssertionError("root status must not probe declared dev targets")

    monkeypatch.setattr("svc_cli.dev.runtime.probe_target", unexpected_probe)
    status = inspect_status(tmp_path)

    assert status["status"] == "healthy"
    assert status["dev"] == {
        "status": "declared",
        "observation": "declaration-only",
        "profile": "local",
        "targets": ["api", "web"],
    }
    assert status["next"]["action"] == "continue"
    assert status["configuration"]["effective"]["digest"]


def test_init_manages_only_a_clean_local_config_ignore_section() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        original = b"node_modules\r\nsvc.local.json\r\n"
        (root / ".gitignore").write_bytes(original)
        plan = plan_init(root)
        apply_local_plan(plan, plan.digest)
        ignored = (root / ".gitignore").read_bytes()
        assert ignored.startswith(original)
        assert local_config_ignore_body().encode() in ignored.replace(b"\r\n", b"\n")
        assert b"\r\n" in ignored

        drifted = ignored.replace(
            b"svc.local.json\r\n# svc:end local-config",
            b"private-svc.local.json\r\n# svc:end local-config",
        )
        (root / ".gitignore").write_bytes(drifted)
        blocked = plan_init(root)
        assert "managed-ignore-drift" in {item.code for item in blocked.blockers}


def test_schema_v1_blocks_writes_and_v2_adopt_preserves_consumer_bytes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        legacy = b'{\n  "schema_version": 1,\n  "svc_version": "10.0.0"\n}\n'
        (root / PROJECT_FILE).write_bytes(legacy)
        blocked = plan_init(root)
        assert "schema-v1-write-blocked" in {item.code for item in blocked.blockers}
        assert (root / PROJECT_FILE).read_bytes() == legacy

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        current = (
            b'{\n'
            b'  "schema_version": 2,\n'
            b'  "svc_version" : "9.9.9",\n'
            b'  "dev": {"profile":"local","profiles":{"local":{"targets":{"app":{'
            b'"probe":{"kind":"exec","argv":["check"]},"provision":{"kind":"manual"}}}}}}\n'
            b'}\n'
        )
        (root / PROJECT_FILE).write_bytes(current)
        adopt = plan_adopt(root)
        assert [write.path for write in adopt.writes] == [PROJECT_FILE]
        updated = adopt.writes[0].content
        expected = current.replace(b'"9.9.9"', f'"{adopt.target_version}"'.encode())
        assert updated == expected
        apply_local_plan(adopt, adopt.digest)
        assert (root / PROJECT_FILE).read_bytes() == updated


def test_invalid_local_overlay_blocks_init_without_rewriting_it() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        initial = plan_init(root)
        apply_local_plan(initial, initial.digest)
        local = root / "svc.local.json"
        local.write_text('{"schema_version": 2}\n', encoding="utf-8")
        before = local.read_bytes()
        blocked = plan_init(root)
        assert "invalid-project-configuration" in {item.code for item in blocked.blockers}
        with pytest.raises(SvcError):
            apply_local_plan(blocked, blocked.digest)
        assert local.read_bytes() == before


def test_apply_preserves_existing_consumer_file_mode_and_rejects_mode_drift() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        agents = root / AGENTS_FILE
        agents.write_text("# Consumer\n", encoding="utf-8")
        os.chmod(agents, 0o640)
        plan = plan_init(root)
        os.chmod(agents, 0o600)
        with pytest.raises(SvcError, match="mode changed"):
            apply_local_plan(plan, plan.digest)
        os.chmod(agents, 0o640)
        apply_local_plan(plan, plan.digest)
        assert agents.stat().st_mode & 0o777 == 0o640
