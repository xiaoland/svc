from pathlib import Path

import pytest

from svc_cli import skills
from svc_cli.cli import main
from test_cli import assert_compact_json, invoke_text
from test_skills import release, release_bytes


def test_skills_schema_bypasses_required_host_and_source() -> None:
    code, stdout, stderr = invoke_text(["skills", "install", "--json-schema"])
    assert (code, stderr) == (0, "")
    schema = assert_compact_json(stdout)
    assert schema["$id"] == "urn:svc:cli-output:skills:v1"


def test_offline_install_check_update_remove_and_reinstall(tmp_path: Path) -> None:
    import hashlib

    archive = tmp_path / "release.zip"

    def write_release(version: str, body: bytes) -> None:
        content = release_bytes(version=version, body=body, names=("svc-task-packet",))
        archive.write_bytes(content)
        archive.with_suffix(".zip.sha256").write_text(
            hashlib.sha256(content).hexdigest()
        )

    scope = [
        "--repo",
        str(tmp_path),
        "--agent",
        "codex",
        "--skill",
        "svc-task-packet",
        "--json",
    ]
    entry = tmp_path / ".agents/skills/svc-task-packet/SKILL.md"
    guide = entry.parent / "references/guide.md"
    consumer = tmp_path / "AGENTS.md"
    write_release("1.0.0", b"# First\n[Guide](references/guide.md)\n")
    install = ["skills", "install", *scope, "--archive", str(archive)]
    code, stdout, stderr = invoke_text(install)
    assert (code, stderr) == (0, "")
    plan = assert_compact_json(stdout)
    assert not entry.exists()
    assert invoke_text(install + ["--apply", str(plan["plan_digest"])])[0] == 0
    first = entry.read_bytes()
    assert b"# First" in first
    assert guide.read_bytes() == b"# Section\nguide\n"
    assert not consumer.exists()
    code, stdout, stderr = invoke_text(install)
    assert (code, stderr) == (0, "")
    assert assert_compact_json(stdout)["status"] == "noop"

    adopt = ["skills", "adopt", "--repo", str(tmp_path), "--agent", "codex", "--json"]
    _, stdout, _ = invoke_text(adopt)
    assert not consumer.exists()
    assert (
        invoke_text(
            adopt + ["--apply", str(assert_compact_json(stdout)["plan_digest"])]
        )[0]
        == 0
    )
    adopted = consumer.read_bytes()
    assert b"every non-trivial task" in adopted

    write_release("2.0.0", b"# Second\n[Guide](references/guide.md)\n")
    code, stdout, stderr = invoke_text(
        ["skills", "check", *scope, "--archive", str(archive)]
    )
    assert (code, stderr) == (0, "")
    unit = assert_compact_json(stdout)["targets"][0]["units"][0]
    assert unit["installation_status"] == "outdated"
    assert entry.read_bytes() == first
    upgrade = ["skills", "update", *scope, "--archive", str(archive)]
    _, stdout, _ = invoke_text(upgrade)
    assert entry.read_bytes() == first
    assert (
        invoke_text(
            upgrade + ["--apply", str(assert_compact_json(stdout)["plan_digest"])]
        )[0]
        == 0
    )
    assert b"# Second" in entry.read_bytes()
    assert guide.read_bytes() == b"# Section\nguide\n"
    assert consumer.read_bytes() == adopted
    _, stdout, _ = invoke_text(["skills", "check", *scope, "--archive", str(archive)])
    unit = assert_compact_json(stdout)["targets"][0]["units"][0]
    assert unit["installation_status"] == "current"
    assert unit["actual_version"] == "2.0.0"

    removal = ["skills", "remove", *scope]
    _, stdout, _ = invoke_text(removal)
    assert (
        invoke_text(
            removal + ["--apply", str(assert_compact_json(stdout)["plan_digest"])]
        )[0]
        == 0
    )
    assert not entry.parent.exists()
    assert consumer.read_bytes() == adopted
    _, stdout, _ = invoke_text(removal)
    assert assert_compact_json(stdout)["status"] == "noop"
    _, stdout, _ = invoke_text(install)
    assert (
        invoke_text(
            install + ["--apply", str(assert_compact_json(stdout)["plan_digest"])]
        )[0]
        == 0
    )
    assert b"# Second" in entry.read_bytes()

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
    assert (
        invoke_text(
            unadopt + ["--apply", str(assert_compact_json(stdout)["plan_digest"])]
        )[0]
        == 0
    )
    assert b"svc:begin adoption" not in consumer.read_bytes()
    assert entry.is_file()


def test_multi_host_preflight_preserves_all_targets_when_one_is_foreign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        skills, "resolve_release", lambda version, *args, **kwargs: release()
    )
    foreign = tmp_path / ".claude/skills/svc-workflow/SKILL.md"
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
        "svc-workflow",
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

    monkeypatch.setattr(
        skills, "resolve_release", lambda version, *args, **kwargs: release()
    )
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
        "svc-workflow",
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
    assert (tmp_path / ".agents/skills/svc-workflow/SKILL.md").is_file()
    assert not (tmp_path / ".claude/skills/svc-workflow/SKILL.md").exists()


def test_absent_status_does_not_claim_installation_is_current(tmp_path: Path) -> None:
    code, stdout, stderr = invoke_text(
        ["skills", "status", "--repo", str(tmp_path), "--json"]
    )
    assert (code, stderr) == (0, "")
    assert assert_compact_json(stdout)["status"] == "absent"
