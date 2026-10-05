from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

import svc_cli.skills as skills
from svc_cli.errors import SvcError
from svc_cli.skills import (
    DEFAULT_SKILLS,
    REPOSITORY,
    SkillArchiveError,
    SkillTarget,
    apply_plan,
    check,
    install,
    parse_release,
    remove,
    skills_root,
    status,
    update,
)


def release(
    *,
    version: str = "1.0.0",
    body: bytes = b"# SVC\n",
    names: tuple[str, ...] = ("svc-methods",),
):
    def document(name: str, payload: bytes) -> bytes:
        if payload.startswith(b"---\n"):
            lines = payload.decode().splitlines(keepends=True)
            end = next(
                index
                for index, line in enumerate(lines[1:], 1)
                if line.rstrip("\r\n") == "---"
            )
            if not any(line.startswith("metadata:") for line in lines[1:end]):
                lines.insert(end, f'metadata: {{"version": "{version}"}}\n')
            return "".join(lines).encode()
        return (
            f'---\nname: {name}\ndescription: "Fixture"\nmetadata: '
            f'{{"version": "{version}"}}\n---\n'.encode()
            + payload
        )

    files_by_skill: dict[str, dict[str, bytes]] = {
        name: {
            "SKILL.md": document(name, body if name in names else b"# SVC\n"),
            "references/guide.md": b"# Section\nguide\n",
        }
        for name in DEFAULT_SKILLS
    }
    entries = []
    for name, files in files_by_skill.items():
        path = f"corpus/{name}"
        entries.append(
            {
                "name": name,
                "path": path,
                "files": {
                    relative: hashlib.sha256(content).hexdigest()
                    for relative, content in files.items()
                },
            }
        )
    manifest = {
        "schema_version": 1,
        "version": version,
        "repository": REPOSITORY,
        "revision": "a" * 40,
        "skills": entries,
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        for name, files in files_by_skill.items():
            for relative, content in files.items():
                archive.writestr(f"corpus/{name}/{relative}", content)
    return parse_release(output.getvalue())


def test_install_is_a_plan_and_apply_preserves_nested_skill_files(
    tmp_path: Path,
) -> None:
    target = SkillTarget(tmp_path)
    plan = install(release(), target, ["svc-methods"])

    assert plan.status == "ready"
    assert not (tmp_path / ".agents").exists()

    result = apply_plan(plan, plan.digest)

    assert result.status == "applied"
    assert result.units[0].status == "applied"
    assert status(target, ["svc-methods"])[0].status == "current"
    assert (tmp_path / ".agents/skills/svc-methods/references/guide.md").is_file()
    record = tmp_path / ".agents/skills/.svc/svc-methods.json"
    assert record.is_file()
    assert json.loads(record.read_text())["source"] == "bytes"


def test_default_selection_does_not_take_over_unrelated_skill(tmp_path: Path) -> None:
    target = SkillTarget(tmp_path)
    unrelated = target.skills_root / "svc-custom"
    unrelated.mkdir(parents=True)
    (unrelated / "SKILL.md").write_text("external\n")

    plan = install(release(), target)

    assert {unit.name for unit in plan.units} == set(DEFAULT_SKILLS)
    result = apply_plan(plan, plan.digest)
    assert result.status == "applied"
    assert (unrelated / "SKILL.md").read_text() == "external\n"


def test_install_does_not_take_over_unknown_skill(tmp_path: Path) -> None:
    path = tmp_path / ".agents/skills/svc-methods/SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"consumer-owned\n")
    plan = install(release(), SkillTarget(tmp_path), ["svc-methods"])

    assert plan.status == "blocked"
    result = apply_plan(plan, plan.digest)
    assert result.status == "blocked"
    assert path.read_bytes() == b"consumer-owned\n"


def test_update_and_remove_protect_baseline_and_extra_files(tmp_path: Path) -> None:
    target = SkillTarget(tmp_path)
    first = install(release(), target, ["svc-methods"])
    apply_plan(first, first.digest)
    extra = tmp_path / ".agents/skills/svc-methods/local.md"
    extra.write_bytes(b"keep\n")

    update_plan = update(
        release(version="2.0.0", body=b"# v2\n"), target, ["svc-methods"]
    )
    remove_plan = remove(target, ["svc-methods"])

    assert update_plan.status == "blocked"
    assert remove_plan.status == "blocked"
    assert extra.read_bytes() == b"keep\n"


def test_remove_cleans_empty_directories_for_reinstall(tmp_path: Path) -> None:
    target = SkillTarget(tmp_path)
    first = install(release(), target, ["svc-methods"])
    apply_plan(first, first.digest)
    removal = remove(target, ["svc-methods"])
    assert apply_plan(removal, removal.digest).status == "applied"
    assert not (tmp_path / ".agents/skills/svc-methods").exists()

    reinstall = install(release(version="2.0.0"), target, ["svc-methods"])
    assert reinstall.status == "ready"
    assert apply_plan(reinstall, reinstall.digest).status == "applied"


def test_install_same_archive_is_noop_and_remove_absent_is_noop(tmp_path: Path) -> None:
    target = SkillTarget(tmp_path)
    first = install(release(), target, ["svc-methods"])
    apply_plan(first, first.digest)

    repeat = install(release(), target, ["svc-methods"])
    absent = remove(target, ["svc-task-packet"])

    assert repeat.status == "noop"
    assert apply_plan(repeat, repeat.digest).status == "noop"
    assert absent.status == "noop"
    assert apply_plan(absent, absent.digest).status == "noop"


def test_plan_rejects_extra_file_and_record_change_without_writes(
    tmp_path: Path,
) -> None:
    target = SkillTarget(tmp_path)
    first = install(release(), target, ["svc-methods"])
    apply_plan(first, first.digest)
    planned = update(release(version="2.0.0", body=b"# v2\n"), target, ["svc-methods"])
    record = tmp_path / ".agents/skills/.svc/svc-methods.json"
    record_data = json.loads(record.read_text())
    record_data["source"] = "changed-source"
    record.write_text(json.dumps(record_data))
    before = (tmp_path / ".agents/skills/svc-methods/SKILL.md").read_bytes()

    result = apply_plan(planned, planned.digest)

    assert result.status == "failed"
    assert result.units[0].status == "failed"
    assert (tmp_path / ".agents/skills/svc-methods/SKILL.md").read_bytes() == before

    planned_again = update(
        release(version="2.0.0", body=b"# v2\n"), target, ["svc-methods"]
    )
    record.write_bytes(record.read_bytes().rstrip() + b"\n")
    extra = tmp_path / ".agents/skills/svc-methods/local.md"
    extra.write_bytes(b"local\n")
    result = apply_plan(planned_again, planned_again.digest)
    assert result.status == "failed"
    assert extra.read_bytes() == b"local\n"


def test_failed_unit_stops_later_units_and_keeps_prior_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = SkillTarget(tmp_path)
    archive = release(names=("svc-methods", "svc-task-packet", "svc-specs"))
    selected = ["svc-methods", "svc-task-packet", "svc-specs"]
    plan = install(archive, target, selected)
    blocked = tmp_path / ".agents/skills/svc-task-packet/SKILL.md"
    original_apply = skills.apply_local_plan
    calls = 0

    def apply_then_edit(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        result = original_apply(*args, **kwargs)
        if calls == 1:
            blocked.parent.mkdir(parents=True)
            blocked.write_bytes(b"external\n")
        return result

    monkeypatch.setattr(skills, "apply_local_plan", apply_then_edit)
    result = apply_plan(plan, plan.digest)

    assert result.status == "partial"
    assert [unit.status for unit in result.units] == ["applied", "failed", "skipped"]
    assert (tmp_path / ".agents/skills/svc-methods/SKILL.md").is_file()
    assert not (tmp_path / ".agents/skills/svc-specs/SKILL.md").exists()
    assert result.units[1].failure is not None
    assert result.units[1].failure.code == "stale-plan"
    assert result.verification == "partial"


def test_global_targets_are_explicit_and_do_not_use_real_home(tmp_path: Path) -> None:
    codex = SkillTarget(tmp_path, "codex", "global")
    claude = SkillTarget(tmp_path, "claude", "global")

    for target in (codex, claude):
        plan = install(release(), target, ["svc-methods"])
        assert str(target.skills_root).startswith(str(tmp_path))
        assert apply_plan(plan, plan.digest).status == "applied"
    assert not (Path.home() / ".agents/skills/svc-methods").exists()
    assert not (Path.home() / ".claude/skills/svc-methods").exists()


def test_latest_release_filters_pages_prereleases_and_non_corpus_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        def __init__(self, value: object) -> None:
            self.value = value

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, limit: int = -1) -> bytes:
            return json.dumps(self.value).encode()

    def open_url(request: object, timeout: float = 0.0) -> Response:
        url = request.full_url if hasattr(request, "full_url") else str(request)
        page = int(url.rsplit("page=", 1)[1])
        if page == 1:
            value = [{"tag_name": "cli-v99.0.0", "draft": False, "prerelease": False}]
            value += [
                {
                    "tag_name": "corpus-v1.0.0",
                    "draft": False,
                    "prerelease": False,
                }
                for _ in range(100)
            ]
        else:
            value = [
                {"tag_name": "corpus-v1.2.0", "draft": False, "prerelease": False},
                {"tag_name": "corpus-v1.10.0", "draft": False, "prerelease": False},
            ]
        return Response(value)

    monkeypatch.setattr(skills.urllib.request, "urlopen", open_url)

    assert skills._latest_release_version(1.0) == "1.10.0"


def test_resolve_release_rejects_archive_with_wrong_requested_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrong = release(version="2.0.0")
    monkeypatch.setattr(skills, "read_release", lambda *args, **kwargs: wrong)

    with pytest.raises(SkillArchiveError, match="does not match requested version"):
        skills.resolve_release("1.0.0")


def test_source_network_errors_are_structured(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        raise OSError("offline")

    monkeypatch.setattr(skills.urllib.request, "urlopen", fail)
    with pytest.raises(SvcError) as raised:
        skills.read_release("https://example.invalid/release.zip")
    assert raised.value.code == "skills-source-failed"


def test_symlink_parent_is_blocked_without_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".agents").symlink_to(outside, target_is_directory=True)

    plan = install(release(), SkillTarget(tmp_path), ["svc-methods"])

    assert plan.status == "blocked"
    assert not (outside / "skills").exists()


def test_check_is_read_only_and_detects_release_change(tmp_path: Path) -> None:
    target = SkillTarget(tmp_path)
    first = install(release(), target, ["svc-methods"])
    apply_plan(first, first.digest)
    before = (tmp_path / ".agents/skills/svc-methods/SKILL.md").read_bytes()

    result = check(target, release(version="2.0.0", body=b"# v2\n"), ["svc-methods"])

    assert result.units[0].status == "outdated"
    assert (tmp_path / ".agents/skills/svc-methods/SKILL.md").read_bytes() == before


def test_release_rejects_unmanifested_and_unsafe_members() -> None:
    archive = release()
    assert archive.manifest.version == "1.0.0"

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as raw:
        raw.writestr("manifest.json", b"{}")
        raw.writestr("../escape", b"no")
    with pytest.raises(SkillArchiveError):
        parse_release(output.getvalue())


def test_release_validates_frontmatter_version_and_markdown_closure() -> None:
    with pytest.raises(SkillArchiveError, match="metadata version"):
        release(
            body=b'---\nname: svc-methods\ndescription: "Fixture"\nmetadata: {"version": "9.9.9"}\n---\nBody\n',
            names=("svc-methods",),
        )


def test_markdown_links_normalize_internal_parent_fragments_and_titles() -> None:
    archive = release(
        body=(
            b'---\nname: svc-methods\ndescription: "Fixture"\n'
            b'metadata: {"version": "1.0.0"}\n---\n'
            b'[guide](references/../references/guide.md#section "title")\n'
            b"[encoded](references/guide%2Emd)\n"
            b"![image](references/guide.md)\n"
            b"`[ignored](missing.md)`\n"
            b"```\n[ignored](missing.md)\n```\n"
        ),
        names=("svc-methods",),
    )

    assert archive.manifest.version == "1.0.0"
    with pytest.raises(SkillArchiveError, match="Missing Markdown target"):
        release(
            body=b'---\nname: svc-methods\ndescription: "Fixture"\nmetadata: {"version": "1.0.0"}\n---\n[missing](missing.md)\n',
            names=("svc-methods",),
        )
    with pytest.raises(SkillArchiveError, match="Missing Markdown fragment"):
        release(
            body=b'---\nname: svc-methods\ndescription: "Fixture"\nmetadata: {"version": "1.0.0"}\n---\n[missing](references/guide.md#missing)\n',
            names=("svc-methods",),
        )
    with pytest.raises(SkillArchiveError, match="escapes Skill"):
        release(
            body=b'---\nname: svc-methods\ndescription: "Fixture"\nmetadata: {"version": "1.0.0"}\n---\n[escape](../../outside.md)\n',
            names=("svc-methods",),
        )


def test_skills_root_matches_supported_host_scopes(tmp_path: Path) -> None:
    assert skills_root(tmp_path, "codex") == tmp_path / ".agents/skills"
    assert skills_root(tmp_path, "claude") == tmp_path / ".claude/skills"
    assert (
        skills_root(tmp_path, "codex", True, home=tmp_path)
        == tmp_path / ".agents/skills"
    )
