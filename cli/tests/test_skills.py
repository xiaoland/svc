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
    REPOSITORY,
    SkillArchiveError,
    SkillTarget,
    apply_plan,
    check,
    install,
    parse_release,
    remove,
    status,
    update,
)


# A distribution contract fixture must not inherit the installer's expected set.
RELEASE_SKILLS = (
    "svc-workflow",
    "svc-verification",
    "svc-task-packet",
    "svc-agent-collaboration",
    "svc-specs",
    "svc-taste",
)


def release_bytes(
    *,
    version: str = "1.0.0",
    body: bytes = b"# SVC\n",
    names: tuple[str, ...] = ("svc-workflow",),
    skill_names: tuple[str, ...] = RELEASE_SKILLS,
) -> bytes:
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
        for name in skill_names
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
    return output.getvalue()


def release(
    *,
    version: str = "1.0.0",
    body: bytes = b"# SVC\n",
    names: tuple[str, ...] = ("svc-workflow",),
):
    return parse_release(release_bytes(version=version, body=body, names=names))


def standalone_files(
    *,
    version: str = "16.0.0",
    body: bytes = b"# SVC\n",
    names: tuple[str, ...] = ("svc-workflow",),
) -> dict[str, bytes]:
    legacy = release_bytes(version=version, body=body, names=names)
    assets: dict[str, bytes] = {}
    entries = []
    with zipfile.ZipFile(io.BytesIO(legacy)) as stream:
        for name in RELEASE_SKILLS:
            prefix = f"corpus/{name}/"
            files = {
                path.removeprefix("corpus/"): stream.read(path)
                for path in stream.namelist()
                if path.startswith(prefix)
            }
            files[f"{name}/LICENSE"] = b"MIT fixture license\n"
            output = io.BytesIO()
            with zipfile.ZipFile(
                output, "w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                for path, content in files.items():
                    archive.writestr(path, content)
            filename = f"{name}-{version}.zip"
            raw = output.getvalue()
            assets[filename] = raw
            entries.append(
                {
                    "name": name,
                    "path": name,
                    "files": {
                        path.removeprefix(f"{name}/"): hashlib.sha256(
                            content
                        ).hexdigest()
                        for path, content in files.items()
                    },
                    "archive": filename,
                    "archive_sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
    assets[f"svc-skills-{version}.json"] = json.dumps(
        {
            "schema_version": 2,
            "version": version,
            "repository": REPOSITORY,
            "revision": "a" * 40,
            "skills": entries,
        }
    ).encode()
    for filename, raw in tuple(assets.items()):
        assets[f"{filename}.sha256"] = hashlib.sha256(raw).hexdigest().encode()
    return assets


def test_default_selection_does_not_take_over_unrelated_skill(tmp_path: Path) -> None:
    target = SkillTarget(tmp_path)
    unrelated = target.skills_root / "svc-custom"
    unrelated.mkdir(parents=True)
    (unrelated / "SKILL.md").write_text("external\n")

    plan = install(release(), target)

    result = apply_plan(plan, plan.digest)
    assert result.status == "applied"
    assert {unit.name for unit in status(target)} == set(RELEASE_SKILLS)
    assert {
        path.name
        for path in target.skills_root.iterdir()
        if path.is_dir() and path.name != ".svc"
    } == set(RELEASE_SKILLS) | {"svc-custom"}
    assert (unrelated / "SKILL.md").read_text() == "external\n"


def test_update_and_remove_protect_baseline_and_extra_files(tmp_path: Path) -> None:
    target = SkillTarget(tmp_path)
    first = install(release(), target, ["svc-workflow"])
    apply_plan(first, first.digest)
    extra = tmp_path / ".agents/skills/svc-workflow/local.md"
    extra.write_bytes(b"keep\n")

    update_plan = update(
        release(version="2.0.0", body=b"# v2\n"), target, ["svc-workflow"]
    )
    remove_plan = remove(target, ["svc-workflow"])

    assert update_plan.status == "blocked"
    assert remove_plan.status == "blocked"
    assert extra.read_bytes() == b"keep\n"


def test_plan_rejects_extra_file_and_record_change_without_writes(
    tmp_path: Path,
) -> None:
    target = SkillTarget(tmp_path)
    first = install(release(), target, ["svc-workflow"])
    apply_plan(first, first.digest)
    planned = update(release(version="2.0.0", body=b"# v2\n"), target, ["svc-workflow"])
    record = tmp_path / ".agents/skills/.svc/svc-workflow.json"
    record_data = json.loads(record.read_text())
    record_data["source"] = "changed-source"
    record.write_text(json.dumps(record_data))
    before = (tmp_path / ".agents/skills/svc-workflow/SKILL.md").read_bytes()

    result = apply_plan(planned, planned.digest)

    assert result.status == "failed"
    assert result.units[0].status == "failed"
    assert (tmp_path / ".agents/skills/svc-workflow/SKILL.md").read_bytes() == before

    planned_again = update(
        release(version="2.0.0", body=b"# v2\n"), target, ["svc-workflow"]
    )
    record.write_bytes(record.read_bytes().rstrip() + b"\n")
    extra = tmp_path / ".agents/skills/svc-workflow/local.md"
    extra.write_bytes(b"local\n")
    result = apply_plan(planned_again, planned_again.digest)
    assert result.status == "failed"
    assert extra.read_bytes() == b"local\n"


def test_failed_unit_stops_later_units_and_keeps_prior_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = SkillTarget(tmp_path)
    archive = release(names=("svc-workflow", "svc-task-packet", "svc-specs"))
    selected = ["svc-workflow", "svc-task-packet", "svc-specs"]
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
    assert (tmp_path / ".agents/skills/svc-workflow/SKILL.md").is_file()
    assert not (tmp_path / ".agents/skills/svc-specs/SKILL.md").exists()
    assert result.units[1].failure is not None
    assert result.units[1].failure.code == "stale-plan"
    assert result.verification == "partial"


def test_global_targets_preserve_existing_home_installations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    for directory in (".agents", ".claude"):
        existing = home / directory / "skills/svc-workflow/SKILL.md"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"existing home installation\n")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    for host, directory in (("codex", ".agents"), ("claude", ".claude")):
        target = SkillTarget(tmp_path / "explicit", host, "global")
        plan = install(release(), target, ["svc-workflow"])
        assert apply_plan(plan, plan.digest).status == "applied"
        assert (target.root / directory / "skills/svc-workflow/SKILL.md").is_file()
        assert (
            home / directory / "skills/svc-workflow/SKILL.md"
        ).read_bytes() == b"existing home installation\n"


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
            return (
                self.value
                if isinstance(self.value, bytes)
                else json.dumps(self.value).encode()
            )

    def open_url(request: object, timeout: float = 0.0) -> Response:
        url = request.full_url if hasattr(request, "full_url") else str(request)
        if "page=" not in url:
            downloads.append(url)
            return Response(assets[url.rsplit("/", 1)[1]])
        page = int(url.rsplit("page=", 1)[1])
        if page == 1:
            value = [{"tag_name": "cli-v99.0.0", "draft": False, "prerelease": False}]
            value += [
                {"tag_name": "corpus-v8.0.0", "draft": True, "prerelease": False},
                {"tag_name": "corpus-v9.0.0", "draft": False, "prerelease": True},
            ]
            value += [
                {"tag_name": "corpus-v1.0.0", "draft": False, "prerelease": False}
                for _ in range(97)
            ]
        else:
            value = [
                {"tag_name": "corpus-v1.2.0", "draft": False, "prerelease": False},
                {"tag_name": "corpus-v1.10.0", "draft": False, "prerelease": False},
            ]
        return Response(value)

    monkeypatch.setattr(skills.urllib.request, "urlopen", open_url)

    assets = standalone_files(version="1.10.0")
    downloads = []
    assert skills.resolve_release(names=["svc-workflow"]).manifest.version == "1.10.0"
    assert {url.rsplit("/", 1)[1] for url in downloads} == {
        "svc-skills-1.10.0.json",
        "svc-skills-1.10.0.json.sha256",
        "svc-workflow-1.10.0.zip",
    }
    assert all("/corpus-v1.10.0/" in url for url in downloads)


def test_resolve_release_rejects_archive_with_wrong_requested_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrong = release(version="2.0.0")
    monkeypatch.setattr(skills, "read_release", lambda *args, **kwargs: wrong)

    with pytest.raises(SkillArchiveError):
        skills.resolve_release("15.0.0")


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

    plan = install(release(), SkillTarget(tmp_path), ["svc-workflow"])

    assert plan.status == "blocked"
    assert not (outside / "skills").exists()


@pytest.mark.parametrize("extra", ["corpus/svc-workflow/unlisted.md", "../escape"])
def test_release_rejects_one_unmanifested_or_unsafe_member(extra: str) -> None:
    output = io.BytesIO(release_bytes())
    with zipfile.ZipFile(output, "a") as raw:
        raw.writestr(extra, b"untrusted")
    with pytest.raises(SkillArchiveError):
        parse_release(output.getvalue())


def test_release_rejects_metadata_version_different_from_manifest() -> None:
    with pytest.raises(SkillArchiveError):
        release(
            body=b'---\nname: svc-workflow\ndescription: "Fixture"\nmetadata: {"version": "9.9.9"}\n---\nBody\n',
            names=("svc-workflow",),
        )


def test_markdown_links_normalize_internal_parent_fragments_and_titles() -> None:
    archive = release(
        body=(
            b'---\nname: svc-workflow\ndescription: "Fixture"\n'
            b'metadata: {"version": "1.0.0"}\n---\n'
            b'[guide](references/../references/guide.md#section "title")\n'
            b"[encoded](references/guide%2Emd)\n"
            b"![image](references/guide.md)\n"
            b"`[ignored](missing.md)`\n"
            b"```\n[ignored](missing.md)\n```\n"
        ),
        names=("svc-workflow",),
    )

    assert archive.manifest.version == "1.0.0"
    with pytest.raises(SkillArchiveError):
        release(
            body=b'---\nname: svc-workflow\ndescription: "Fixture"\nmetadata: {"version": "1.0.0"}\n---\n[missing](missing.md)\n',
            names=("svc-workflow",),
        )
    with pytest.raises(SkillArchiveError):
        release(
            body=b'---\nname: svc-workflow\ndescription: "Fixture"\nmetadata: {"version": "1.0.0"}\n---\n[missing](references/guide.md#missing)\n',
            names=("svc-workflow",),
        )
    with pytest.raises(SkillArchiveError):
        release(
            body=b'---\nname: svc-workflow\ndescription: "Fixture"\nmetadata: {"version": "1.0.0"}\n---\n[escape](../../outside.md)\n',
            names=("svc-workflow",),
        )


@pytest.mark.parametrize("mixed", [False, True])
def test_release_rejects_legacy_and_mixed_collaboration_entries(mixed: bool) -> None:
    names = tuple(
        "svc-sub-agents" if name == "svc-agent-collaboration" else name
        for name in RELEASE_SKILLS
    )
    if mixed:
        names += ("svc-agent-collaboration",)
    raw = release_bytes(version="15.0.0", skill_names=names)
    with pytest.raises(SkillArchiveError):
        parse_release(raw)


@pytest.mark.parametrize("mixed", [False, True])
def test_release_rejects_retired_methods_and_mixed_workflow(mixed: bool) -> None:
    names = tuple(name for name in RELEASE_SKILLS if name != "svc-workflow")
    names += ("svc-methods",)
    if mixed:
        names += ("svc-workflow",)
    raw = release_bytes(version="15.0.0", skill_names=names)
    with pytest.raises(SkillArchiveError):
        parse_release(raw)


@pytest.mark.parametrize(
    "legacy_name,modified", [("svc-methods", False), ("svc-sub-agents", True)]
)
def test_legacy_installation_can_be_inspected_and_safely_removed(
    tmp_path: Path, modified: bool, legacy_name: str
) -> None:
    target = SkillTarget(tmp_path)
    replacement = (
        "svc-agent-collaboration" if legacy_name == "svc-sub-agents" else "svc-workflow"
    )
    legacy = target.skills_root / legacy_name
    legacy.mkdir(parents=True)
    body = (
        f'---\nname: {legacy_name}\ndescription: "Legacy"\nmetadata: {{"version": "15.0.0"}}\n---\nLegacy guidance\n'
    ).encode()
    entry = legacy / "SKILL.md"
    entry.write_bytes(body)
    record = target.skills_root / f".svc/{legacy_name}.json"
    record.parent.mkdir()
    record.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": legacy_name,
                "host": "codex",
                "scope": "project",
                "version": "15.0.0",
                "source": "legacy-release.zip",
                "repository": REPOSITORY,
                "revision": "a" * 40,
                "archive_sha256": "b" * 64,
                "path": f".agents/skills/{legacy_name}",
                "files": {"SKILL.md": hashlib.sha256(body).hexdigest()},
            }
        )
    )
    if modified:
        entry.write_bytes(body + b"Consumer edit\n")
    before = entry.read_bytes()
    assert status(target, [legacy_name])[0].status == (
        "modified" if modified else "current"
    )

    # Both layouts belong to the same unpublished v15 development cycle.
    # Current defaults install the replacement without claiming the old directory.
    plan = install(release(version="15.0.0"), target)
    assert apply_plan(plan, plan.digest).status == "applied"
    assert status(target, [replacement])[0].status == "current"
    assert legacy_name not in {unit.name for unit in status(target)}
    assert entry.read_bytes() == before
    unavailable = update(release(version="15.0.0"), target, [legacy_name])
    assert unavailable.status == "blocked"
    assert entry.read_bytes() == before

    removal = remove(target, [legacy_name])
    result = apply_plan(removal, removal.digest)
    if modified:
        assert result.status == "blocked"
        assert entry.read_bytes() == before
        assert record.is_file()
    else:
        assert result.status == "applied"
        assert not legacy.exists()
        assert not record.exists()
    assert status(target, [replacement])[0].status == "current"


def test_verification_remains_an_independently_installable_and_updatable_skill(
    tmp_path: Path,
) -> None:
    target = SkillTarget(tmp_path)
    first = install(release(version="15.0.0"), target, ["svc-verification"])
    assert apply_plan(first, first.digest).status == "applied"
    entry = target.skills_root / "svc-verification/SKILL.md"
    assert b"name: svc-verification" in entry.read_bytes()
    revised = release(
        version="15.0.0",
        body=b"Revised verification guidance\n",
        names=("svc-verification",),
    )
    planned = update(revised, target, ["svc-verification"])
    assert apply_plan(planned, planned.digest).status == "applied"
    assert b"Revised verification guidance" in entry.read_bytes()
    assert check(target, revised, ["svc-verification"]).units[0].status == "current"
    assert status(target, ["svc-workflow"])[0].status == "absent"
