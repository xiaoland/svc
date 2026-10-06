import hashlib
from pathlib import Path

import pytest

from svc_cli.errors import SvcError
from svc_cli.skill_adoption import apply_adoption, plan_adoption


def entry(root: Path, name: str = "svc-task-packet") -> Path:
    path = root / name / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(f'---\nname: {name}\ndescription: "fixture"\n---\nBody\n')
    return path


@pytest.mark.parametrize(
    "agent,target", [("codex", "AGENTS.md"), ("claude", "CLAUDE.md")]
)
def test_adoption_preserves_consumer_content_and_is_separate_from_install(
    tmp_path: Path, agent: str, target: str
) -> None:
    skills = tmp_path / "external-manager"
    skill = entry(skills)
    original = b"# Consumer authority\n\nKeep this.\n"
    (tmp_path / target).write_bytes(original)
    plan = plan_adoption(tmp_path, agent=agent, skills_root=skills)
    assert plan.local.status == "ready"
    assert (tmp_path / target).read_bytes() == original
    apply_adoption(plan, plan.local.digest)
    adopted = (tmp_path / target).read_bytes()
    assert adopted.startswith(original)
    assert b"every non-trivial task" in adopted
    assert b"external-manager/svc-task-packet/SKILL.md" in adopted
    assert (
        plan_adoption(tmp_path, agent=agent, skills_root=skills).local.status == "noop"
    )
    # Unadopt remains available after uninstall and never touches the payload.
    skill.unlink()
    remove = plan_adoption(tmp_path, agent=agent, skills_root=skills, remove=True)
    apply_adoption(remove, remove.local.digest)
    assert (tmp_path / target).read_bytes() == original + b"\n"
    assert not (skills / ".svc").exists()


def test_adoption_rejects_stale_entries_and_consumer_edits(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    skill = entry(skills)
    plan = plan_adoption(tmp_path, agent="codex", skills_root=skills)
    skill.write_text(skill.read_text() + "Changed\n")
    with pytest.raises(SvcError) as raised:
        apply_adoption(plan, plan.local.digest)
    assert raised.value.code == "plan-digest-mismatch"
    assert not (tmp_path / "AGENTS.md").exists()
    current = plan_adoption(tmp_path, agent="codex", skills_root=skills)
    apply_adoption(current, current.local.digest)
    target = tmp_path / "AGENTS.md"
    target.write_text(
        target.read_text().replace("Human product intent", "Changed intent")
    )
    before = target.read_bytes()
    for remove in (False, True):
        blocked = plan_adoption(
            tmp_path, agent="codex", skills_root=skills, remove=remove
        )
        assert blocked.local.status == "blocked"
        with pytest.raises(SvcError):
            apply_adoption(blocked, blocked.local.digest)
        assert target.read_bytes() == before


def test_adoption_requires_task_packet_and_refuses_symlink_target(
    tmp_path: Path,
) -> None:
    skills = tmp_path / "skills"
    entry(skills, "svc-workflow")
    blocked = plan_adoption(tmp_path, agent="codex", skills_root=skills)
    assert blocked.local.blockers[0].code == "task-packet-unavailable"
    entry(skills)
    elsewhere = tmp_path / "consumer.md"
    elsewhere.write_text("consumer")
    (tmp_path / "AGENTS.md").symlink_to(elsewhere)
    blocked = plan_adoption(tmp_path, agent="codex", skills_root=skills)
    assert blocked.local.blockers[0].code == "path-not-file"
    assert elsewhere.read_text() == "consumer"


@pytest.mark.parametrize(
    "agent,target,legacy_name",
    [("codex", "AGENTS.md", "svc-methods"), ("claude", "CLAUDE.md", "svc-sub-agents")],
)
def test_adoption_refreshes_legacy_pointer_and_preserves_outside_content(
    tmp_path: Path, agent: str, target: str, legacy_name: str
) -> None:
    skills = tmp_path / "skills"
    entry(skills)
    legacy = entry(skills, legacy_name)
    entry(skills, "svc-verification")
    replacement = (
        "svc-agent-collaboration" if legacy_name == "svc-sub-agents" else "svc-workflow"
    )
    entry(skills, replacement)
    body = (
        f"## SVC working guidance\n\n- `{legacy_name}`: `skills/{legacy_name}/SKILL.md`"
    )
    original = (
        "# Consumer rules\n\n"
        f"<!-- svc:begin adoption sha256={hashlib.sha256(body.encode()).hexdigest()} -->\n"
        f"{body}\n<!-- svc:end adoption -->\n"
        "\nKeep this later instruction.\n"
    )
    consumer = tmp_path / target
    consumer.write_text(original)

    refresh = plan_adoption(tmp_path, agent=agent, skills_root=skills)
    assert refresh.local.status == "ready"
    assert apply_adoption(refresh, refresh.local.digest).status == "applied"
    updated = consumer.read_text()
    assert updated.startswith("# Consumer rules\n\n")
    assert updated.endswith("\nKeep this later instruction.\n")
    assert f"skills/{replacement}/SKILL.md" in updated
    assert "skills/svc-verification/SKILL.md" in updated
    assert legacy_name not in updated
    assert legacy.is_file()
    assert (
        plan_adoption(tmp_path, agent=agent, skills_root=skills).local.status == "noop"
    )
