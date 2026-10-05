from pathlib import Path

import pytest

from svc_cli import skills
from svc_cli.cli import main
from test_cli import assert_compact_json, invoke_text
from test_skills import release


def test_skills_schema_bypasses_required_host_and_source() -> None:
    code, stdout, stderr = invoke_text(["skills", "install", "--json-schema"])
    assert (code, stderr) == (0, "")
    schema = assert_compact_json(stdout)
    assert schema["$id"] == "urn:svc:cli-output:skills:v1"


def test_cli_install_update_adopt_and_remove_are_separate_exact_plans(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = release(
        body=b'---\nname: svc-task-packet\ndescription: "Fixture"\n---\nTask\n',
        names=("svc-task-packet",),
    )
    monkeypatch.setattr(skills, "resolve_release", lambda version: first)
    base = [
        "skills",
        "install",
        "--repo",
        str(tmp_path),
        "--agent",
        "codex",
        "--version",
        "1.0.0",
        "--skill",
        "svc-task-packet",
        "--json",
    ]
    code, stdout, stderr = invoke_text(base)
    assert (code, stderr) == (0, "")
    plan = assert_compact_json(stdout)
    assert plan["mode"] == "plan"
    assert not (tmp_path / ".agents").exists()
    code, stdout, stderr = invoke_text(base + ["--apply", str(plan["plan_digest"])])
    assert (code, stderr) == (0, "")
    assert assert_compact_json(stdout)["status"] == "applied"
    assert not (tmp_path / "AGENTS.md").exists()
    _, stdout, _ = invoke_text(
        [
            "skills",
            "status",
            "--repo",
            str(tmp_path),
            "--agent",
            "codex",
            "--skill",
            "svc-task-packet",
            "--json",
        ]
    )
    installed = assert_compact_json(stdout)["targets"][0]["units"][0]
    assert installed["recorded_version"] == "1.0.0"
    assert installed["actual_version"] is None
    _, stdout, _ = invoke_text(
        [
            "skills",
            "check",
            "--repo",
            str(tmp_path),
            "--agent",
            "codex",
            "--version",
            "1.0.0",
            "--skill",
            "svc-task-packet",
            "--json",
        ]
    )
    assert (
        assert_compact_json(stdout)["targets"][0]["units"][0]["actual_version"]
        == "1.0.0"
    )
    adopt = ["skills", "adopt", "--repo", str(tmp_path), "--agent", "codex", "--json"]
    code, stdout, stderr = invoke_text(adopt)
    assert (code, stderr) == (0, "")
    assert not (tmp_path / "AGENTS.md").exists()
    digest = str(assert_compact_json(stdout)["plan_digest"])
    assert invoke_text(adopt + ["--apply", digest])[0] == 0
    assert "every non-trivial task" in (tmp_path / "AGENTS.md").read_text()
    remove = [
        "skills",
        "remove",
        "--repo",
        str(tmp_path),
        "--agent",
        "codex",
        "--skill",
        "svc-task-packet",
        "--json",
    ]
    _, stdout, _ = invoke_text(remove)
    digest = str(assert_compact_json(stdout)["plan_digest"])
    assert invoke_text(remove + ["--apply", digest])[0] == 0
    assert "svc:begin adoption" in (tmp_path / "AGENTS.md").read_text()
    unadopt = [
        "skills",
        "unadopt",
        "--repo",
        str(tmp_path),
        "--agent",
        "codex",
        "--json",
    ]
    _, stdout, _ = invoke_text(unadopt)
    digest = str(assert_compact_json(stdout)["plan_digest"])
    assert invoke_text(unadopt + ["--apply", digest])[0] == 0
    assert "svc:begin adoption" not in (tmp_path / "AGENTS.md").read_text()


def test_multi_host_preflight_preserves_all_targets_when_one_is_foreign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(skills, "resolve_release", lambda version: release())
    foreign = tmp_path / ".claude/skills/svc-methods/SKILL.md"
    foreign.parent.mkdir(parents=True)
    foreign.write_bytes(b"foreign-manager")
    base = [
        "skills",
        "install",
        "--repo",
        str(tmp_path),
        "--version",
        "1.0.0",
        "--agent",
        "codex",
        "--agent",
        "claude",
        "--skill",
        "svc-methods",
        "--json",
    ]
    code, stdout, stderr = invoke_text(base)
    assert (code, stderr) == (3, "")
    plan = assert_compact_json(stdout)
    assert plan["status"] == "blocked"
    code, stdout, stderr = invoke_text(base + ["--apply", str(plan["plan_digest"])])
    assert (code, stderr) == (3, "")
    assert not (tmp_path / ".agents").exists()
    assert foreign.read_bytes() == b"foreign-manager"


def test_skills_write_grammar_requires_explicit_agent_and_source(
    tmp_path: Path,
) -> None:
    assert main(["skills", "install", "--repo", str(tmp_path)]) == 2
    code, stdout, stderr = invoke_text(
        ["skills", "install", "--agent", "codex", "--json"]
    )
    assert (code, stdout) == (2, "")
    assert assert_compact_json(stderr)["code"] == "invalid-cli-usage"


def test_multi_host_runtime_failure_preserves_completed_target_and_reports_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import svc_cli.plans as transactions

    monkeypatch.setattr(skills, "resolve_release", lambda version: release())
    base = [
        "skills",
        "install",
        "--repo",
        str(tmp_path),
        "--version",
        "1.0.0",
        "--agent",
        "codex",
        "--agent",
        "claude",
        "--skill",
        "svc-methods",
        "--json",
    ]
    _, stdout, _ = invoke_text(base)
    digest = str(assert_compact_json(stdout)["plan_digest"])
    commit = transactions._commit_mutation

    def fail_claude_reference(path, mutation, content):
        if ".claude" in path.parts and path.name == "guide.md":
            raise OSError("injected second-host failure")
        return commit(path, mutation, content)

    monkeypatch.setattr(transactions, "_commit_mutation", fail_claude_reference)
    code, stdout, stderr = invoke_text(base + ["--apply", digest])
    assert (code, stderr) == (4, "")
    result = assert_compact_json(stdout)
    assert result["status"] == "partial"
    assert result["targets"][0]["units"][0]["actual_version"] == "1.0.0"
    failure = result["targets"][1]["units"][0]
    assert failure["status"] == "failed"
    assert failure["installation_status"] == "absent"
    assert failure["actual_version"] is None
    assert failure["error"]["details"]["rollback"]["status"] == "succeeded"
    assert (tmp_path / ".agents/skills/svc-methods/SKILL.md").is_file()
    assert not (tmp_path / ".claude/skills/svc-methods/SKILL.md").exists()


def test_absent_status_does_not_claim_installation_is_current(tmp_path: Path) -> None:
    code, stdout, stderr = invoke_text(
        ["skills", "status", "--repo", str(tmp_path), "--json"]
    )
    assert (code, stderr) == (0, "")
    assert assert_compact_json(stdout)["status"] == "absent"
