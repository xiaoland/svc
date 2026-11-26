"""Consume standalone release artifacts through actual HTTP and offline CLI paths."""

import hashlib
import io
import json
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from svc_cli import skills
from test_cli import assert_compact_json, invoke_text
from test_skills import PUBLIC_SKILLS, RELEASE_SKILLS, release_bytes, standalone_files


CORPUS_17_SKILLS = (*RELEASE_SKILLS, "svc-writing")
PUBLIC_TAG = "skills-v1.0.0"


def public_assets(**kwargs) -> dict[str, bytes]:
    return standalone_files(
        version="1.0.0", skill_names=PUBLIC_SKILLS, tag=PUBLIC_TAG, **kwargs
    )


def save_assets(directory: Path, assets: dict[str, bytes]) -> Path:
    directory.mkdir()
    for name, content in assets.items():
        (directory / name).write_bytes(content)
    return directory


def save_v15_archive(directory: Path) -> Path:
    raw = release_bytes(version="15.0.0")
    name = "svc-corpus-15.0.0.zip"
    return (
        save_assets(
            directory,
            {name: raw, name + ".sha256": hashlib.sha256(raw).hexdigest().encode()},
        )
        / name
    )


@pytest.fixture
def releases(monkeypatch: pytest.MonkeyPatch):
    assets = {
        f"/{PUBLIC_TAG}/{filename}": content
        for filename, content in public_assets().items()
    }
    assets["/releases?per_page=100&page=1"] = json.dumps(
        [
            {"tag_name": "corpus-v17.0.0", "draft": False, "prerelease": False},
            {"tag_name": PUBLIC_TAG, "draft": False, "prerelease": False},
        ]
    ).encode()
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            if self.path not in assets:
                self.send_error(404)
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(assets[self.path])

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(
        skills, "CATALOG_DOWNLOAD", base + "/{tag}/svc-skills-{version}.json"
    )
    monkeypatch.setattr(skills, "RELEASE_API", base + "/releases")
    try:
        yield assets, requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def apply(arguments: list[str]) -> dict[str, object]:
    code, stdout, stderr = invoke_text(arguments)
    assert (code, stderr) == (0, "")
    planned = assert_compact_json(stdout)
    code, stdout, stderr = invoke_text(
        arguments + ["--apply", str(planned["plan_digest"])]
    )
    assert (code, stderr) == (0, "")
    return assert_compact_json(stdout)


def test_http_selection_preserves_per_skill_identity_and_check_fetches_only_catalog(
    tmp_path: Path, releases
) -> None:
    assets, requests = releases
    single = tmp_path / "single"
    complete = tmp_path / "complete"
    single.mkdir()
    complete.mkdir()
    scope = ["--agent", "codex", "--version", "1.0.0", "--json"]
    assert (
        apply(
            [
                "skills",
                "install",
                "--repo",
                str(single),
                *scope,
                "--skill",
                "svc-workflow",
            ]
        )["status"]
        == "applied"
    )
    assert set(requests) == {
        f"/{PUBLIC_TAG}/svc-skills-1.0.0.json",
        f"/{PUBLIC_TAG}/svc-skills-1.0.0.json.sha256",
        f"/{PUBLIC_TAG}/svc-workflow-1.0.0.zip",
    }
    record_path = Path(".agents/skills/.svc/svc-workflow.json")
    recorded = json.loads((single / record_path).read_text())
    assert (
        recorded["archive_sha256"]
        == hashlib.sha256(assets[f"/{PUBLIC_TAG}/svc-workflow-1.0.0.zip"]).hexdigest()
    )
    assert recorded["tag"] == PUBLIC_TAG
    assert recorded["source"].endswith(f"/{PUBLIC_TAG}/svc-workflow-1.0.0.zip")
    assert (
        apply(["skills", "install", "--repo", str(complete), *scope])["status"]
        == "applied"
    )
    assert json.loads((complete / record_path).read_text()) == recorded
    requests.clear()
    for repo, selection in ((single, ["--skill", "svc-workflow"]), (complete, [])):
        code, stdout, stderr = invoke_text(
            ["skills", "check", "--repo", str(repo), *scope, *selection]
        )
        assert (code, stderr) == (0, "")
        assert assert_compact_json(stdout)["status"] == "current"
    assert set(requests) == {
        f"/{PUBLIC_TAG}/svc-skills-1.0.0.json",
        f"/{PUBLIC_TAG}/svc-skills-1.0.0.json.sha256",
    }
    assert not any("svc-corpus" in request for request in requests)


def test_missing_public_skill_requires_separate_install_before_full_update(
    tmp_path: Path, releases
) -> None:
    scope = ["--repo", str(tmp_path), "--agent", "codex", "--json"]
    old = save_assets(tmp_path / "v16", standalone_files(version="16.0.1"))
    for name in RELEASE_SKILLS:
        archive = old / f"{name}-16.0.1.zip"
        assert (
            apply(["skills", "install", *scope, "--archive", str(archive)])["status"]
            == "applied"
        )

    upgrade = ["skills", "update", *scope, "--version", "1.0.0"]
    code, stdout, stderr = invoke_text(upgrade)
    assert (code, stderr) == (3, "")
    plan = assert_compact_json(stdout)
    assert plan["status"] == "blocked"
    assert {
        unit["name"]
        for unit in plan["targets"][0]["units"]
        if unit["installation_status"] == "absent"
    } == {"svc-writing"}
    assert (
        apply(
            [
                "skills",
                "install",
                *scope,
                "--version",
                "1.0.0",
                "--skill",
                "svc-writing",
            ]
        )["status"]
        == "applied"
    )
    assert apply(upgrade)["status"] == "applied"


def test_owned_v17_installation_updates_to_public_release_and_rolls_back(
    tmp_path: Path, releases
) -> None:
    old = save_assets(
        tmp_path / "v17",
        standalone_files(version="17.0.0", skill_names=CORPUS_17_SKILLS),
    )
    scope = ["--repo", str(tmp_path), "--agent", "codex", "--json"]
    instructions = tmp_path / "AGENTS.md"
    instructions.write_text("Consumer instructions\n")
    for name in CORPUS_17_SKILLS:
        archive = old / f"{name}-17.0.0.zip"
        installed = apply(["skills", "install", *scope, "--archive", str(archive)])
        assert installed["status"] == "applied"
        assert str(installed["release_notes"]).endswith("/corpus-v17.0.0")

    root = tmp_path / ".agents/skills"

    def installed_bytes():
        return {
            path.relative_to(root): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }

    baseline = installed_bytes()
    code, stdout, stderr = invoke_text(["skills", "check", *scope])
    assert (code, stderr) == (0, "")
    before = assert_compact_json(stdout)
    assert before["status"] == "available"
    assert before["target_version"] == "1.0.0"
    assert {unit["recorded_version"] for unit in before["targets"][0]["units"]} == {
        "17.0.0"
    }
    updated = apply(["skills", "update", *scope, "--version", "1.0.0"])
    assert updated["status"] == "applied"
    assert str(updated["release_notes"]).endswith(f"/{PUBLIC_TAG}")
    code, stdout, stderr = invoke_text(["skills", "check", *scope])
    assert (code, stderr) == (0, "")
    status = assert_compact_json(stdout)
    assert status["status"] == "current"
    assert {unit["name"] for unit in status["targets"][0]["units"]} == set(
        CORPUS_17_SKILLS
    )
    for name in CORPUS_17_SKILLS:
        record = json.loads((root / ".svc" / f"{name}.json").read_bytes())
        assert record["tag"] == PUBLIC_TAG
        archive = old / f"{name}-17.0.0.zip"
        assert (
            apply(["skills", "update", *scope, "--archive", str(archive)])["status"]
            == "applied"
        )
    assert installed_bytes() == baseline
    assert instructions.read_text() == "Consumer instructions\n"


@pytest.mark.parametrize("version", ["15.0.0", "16.0.1"])
def test_explicit_skill_selection_rejects_skill_missing_from_target_release(
    tmp_path: Path, version: str
) -> None:
    if version == "15.0.0":
        archive = save_v15_archive(tmp_path / "v15")
    else:
        directory = save_assets(tmp_path / "v16", standalone_files(version=version))
        archive = directory / f"svc-workflow-{version}.zip"
    code, stdout, stderr = invoke_text(
        [
            "skills",
            "install",
            "--repo",
            str(tmp_path),
            "--agent",
            "codex",
            "--archive",
            str(archive),
            "--skill",
            "svc-writing",
            "--json",
        ]
    )
    assert (code, stdout) == (4, "")
    error = assert_compact_json(stderr)["error"]
    assert error["code"] == "invalid-release"
    assert error["message"] == "Offline archive does not contain every selected Skill"


@pytest.mark.parametrize(
    ("version", "catalog_names"),
    [
        ("16.0.1", CORPUS_17_SKILLS),
        ("17.0.0", RELEASE_SKILLS),
        ("17.0.0", (*RELEASE_SKILLS, "svc-unknown")),
    ],
)
def test_offline_catalog_rejects_incorrect_skill_set_even_for_known_zip(
    tmp_path: Path, version: str, catalog_names: tuple[str, ...]
) -> None:
    for filename, content in standalone_files(
        version=version, skill_names=catalog_names
    ).items():
        (tmp_path / filename).write_bytes(content)
    with pytest.raises(skills.SkillArchiveError):
        skills.read_release(tmp_path / f"svc-workflow-{version}.zip")


def test_public_catalog_requires_all_seven_skills_even_at_1_0_0(tmp_path: Path) -> None:
    directory = save_assets(
        tmp_path / "skills",
        standalone_files(version="1.0.0", skill_names=RELEASE_SKILLS, tag=PUBLIC_TAG),
    )
    with pytest.raises(skills.SkillArchiveError, match="exactly its SVC Skill set"):
        skills.read_release(directory / "svc-workflow-1.0.0.zip")


def test_implicit_offline_catalog_must_match_version_in_archive_name(
    tmp_path: Path,
) -> None:
    files = standalone_files(version="17.0.0", skill_names=CORPUS_17_SKILLS)
    archive = tmp_path / "svc-workflow-16.0.1.zip"
    archive.write_bytes(files["svc-workflow-17.0.0.zip"])
    for suffix in (".json", ".json.sha256"):
        (tmp_path / f"svc-skills-16.0.1{suffix}").write_bytes(
            files[f"svc-skills-17.0.0{suffix}"]
        )
    with pytest.raises(
        skills.SkillArchiveError, match="Catalog version does not match"
    ):
        skills.read_release(archive)


def test_offline_single_zip_defaults_to_contained_skill_and_supports_renaming(
    tmp_path: Path,
) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    for name, content in standalone_files().items():
        (assets / name).write_bytes(content)
    repo = tmp_path / "consumer"
    repo.mkdir()
    archive = assets / "svc-verification-16.0.0.zip"
    base = [
        "skills",
        "install",
        "--repo",
        str(repo),
        "--agent",
        "codex",
        "--archive",
        str(archive),
        "--json",
    ]
    assert apply(base)["status"] == "applied"
    entries = {
        path.name for path in (repo / ".agents/skills").iterdir() if path.name != ".svc"
    }
    assert entries == {"svc-verification"}
    assert invoke_text(base + ["--skill", "svc-workflow"])[0] != 0
    renamed = assets / "custom.zip"
    archive.rename(renamed)
    catalog = assets / "svc-skills-16.0.0.json"
    assert (
        invoke_text(
            [
                "skills",
                "check",
                "--repo",
                str(repo),
                "--agent",
                "codex",
                "--archive",
                str(renamed),
                "--catalog",
                str(catalog),
                "--json",
            ]
        )[0]
        == 0
    )


@pytest.mark.parametrize(
    "corruption",
    ["catalog", "archive", "file-map", "extra-file", "wrong-tag", "legacy-catalog"],
)
def test_invalid_selected_artifact_never_writes_or_falls_back_to_legacy(
    tmp_path: Path, releases, corruption: str
) -> None:
    assets, requests = releases
    catalog_key = f"/{PUBLIC_TAG}/svc-skills-1.0.0.json"
    archive_key = f"/{PUBLIC_TAG}/svc-workflow-1.0.0.zip"
    catalog = json.loads(assets[catalog_key])
    skill = next(
        skill for skill in catalog["skills"] if skill["name"] == "svc-workflow"
    )
    if corruption == "catalog":
        assets[catalog_key] += b" "
    elif corruption == "archive":
        assets[archive_key] += b"tampered"
    elif corruption == "file-map":
        skill["files"]["SKILL.md"] = "0" * 64
    elif corruption == "extra-file":
        raw = io.BytesIO(assets[archive_key])
        with zipfile.ZipFile(raw, "a") as stream:
            stream.writestr("svc-workflow/unlisted.txt", b"extra")
        assets[archive_key] = raw.getvalue()
        skill["archive_sha256"] = hashlib.sha256(raw.getvalue()).hexdigest()
    elif corruption == "wrong-tag":
        catalog["tag"] = "corpus-v1.0.0"
    else:
        catalog = json.loads(standalone_files(version="1.0.0")["svc-skills-1.0.0.json"])
    if corruption not in {"catalog", "archive"}:
        assets[catalog_key] = json.dumps(catalog).encode()
        assets[catalog_key + ".sha256"] = (
            hashlib.sha256(assets[catalog_key]).hexdigest().encode()
        )
    code, _, _ = invoke_text(
        [
            "skills",
            "install",
            "--repo",
            str(tmp_path),
            "--agent",
            "codex",
            "--version",
            "1.0.0",
            "--skill",
            "svc-workflow",
            "--json",
        ]
    )
    assert code != 0
    assert not (tmp_path / ".agents").exists()
    assert all(request.startswith(f"/{PUBLIC_TAG}/") for request in requests)
    if corruption in {"wrong-tag", "legacy-catalog"}:
        assert archive_key not in requests


def test_explicit_version_never_falls_back_to_legacy_release(
    tmp_path: Path, releases
) -> None:
    assets, requests = releases
    scope = ["--agent", "codex", "--skill", "svc-workflow", "--json"]
    legacy = release_bytes(version="15.0.0")
    assets["/corpus-v15.0.0/svc-corpus-15.0.0.zip"] = legacy
    assets["/corpus-v15.0.0/svc-corpus-15.0.0.zip.sha256"] = (
        hashlib.sha256(legacy).hexdigest().encode()
    )
    code, stdout, stderr = invoke_text(
        ["skills", "install", "--repo", str(tmp_path), *scope, "--version", "15.0.0"]
    )
    assert (code, stdout) == (4, "")
    assert assert_compact_json(stderr)["error"]["code"] == "skills-source-failed"
    assert requests == ["/skills-v15.0.0/svc-skills-15.0.0.json"]


def test_default_check_requires_a_public_skills_release(
    tmp_path: Path, releases
) -> None:
    assets, requests = releases
    endpoint = "/releases?per_page=100&page=1"
    assets[endpoint] = json.dumps(
        [{"tag_name": "corpus-v17.0.0", "draft": False, "prerelease": False}]
    ).encode()
    code, stdout, stderr = invoke_text(
        ["skills", "check", "--repo", str(tmp_path), "--agent", "codex", "--json"]
    )
    assert (code, stdout) == (4, "")
    assert (
        "No stable skills-v release" in assert_compact_json(stderr)["error"]["message"]
    )
    assert requests == [endpoint]


def test_v15_owned_skill_updates_to_individual_artifact_and_preserves_local_changes(
    tmp_path: Path, releases
) -> None:
    assets, _ = releases
    scope = [
        "--repo",
        str(tmp_path),
        "--agent",
        "codex",
        "--skill",
        "svc-workflow",
        "--json",
    ]
    archive = save_v15_archive(tmp_path / "legacy")
    assert (
        apply(["skills", "install", *scope, "--archive", str(archive)])["status"]
        == "applied"
    )
    assert (
        apply(["skills", "update", *scope, "--version", "1.0.0"])["status"] == "applied"
    )
    record = json.loads(
        (tmp_path / ".agents/skills/.svc/svc-workflow.json").read_text()
    )
    assert record["version"] == "1.0.0"
    assert (
        record["archive_sha256"]
        == hashlib.sha256(assets[f"/{PUBLIC_TAG}/svc-workflow-1.0.0.zip"]).hexdigest()
    )
    entry = tmp_path / ".agents/skills/svc-workflow/SKILL.md"
    edited = entry.read_bytes() + b"Local customization\n"
    entry.write_bytes(edited)
    code, stdout, _ = invoke_text(["skills", "update", *scope, "--version", "1.0.0"])
    assert code != 0
    assert assert_compact_json(stdout)["status"] == "blocked"
    assert entry.read_bytes() == edited


def test_changed_release_before_apply_invalidates_exact_plan(
    tmp_path: Path, releases
) -> None:
    assets, _ = releases
    command = [
        "skills",
        "install",
        "--repo",
        str(tmp_path),
        "--agent",
        "codex",
        "--version",
        "1.0.0",
        "--skill",
        "svc-workflow",
        "--json",
    ]
    code, stdout, _ = invoke_text(command)
    assert code == 0
    digest = str(assert_compact_json(stdout)["plan_digest"])
    assets.update(
        {
            f"/{PUBLIC_TAG}/{filename}": raw
            for filename, raw in public_assets(
                body=b"Changed behavior guidance\n"
            ).items()
        }
    )
    code, _, stderr = invoke_text(command + ["--apply", digest])
    assert code != 0
    assert assert_compact_json(stderr)["error"]["code"] == "plan-digest-mismatch"
    assert not (tmp_path / ".agents").exists()


def test_equivalent_zip_representation_does_not_make_installed_skill_outdated(
    tmp_path: Path, releases
) -> None:
    assets, _ = releases
    scope = [
        "--repo",
        str(tmp_path),
        "--agent",
        "codex",
        "--version",
        "1.0.0",
        "--skill",
        "svc-workflow",
        "--json",
    ]
    assert apply(["skills", "install", *scope])["status"] == "applied"
    record = tmp_path / ".agents/skills/.svc/svc-workflow.json"
    original_record = record.read_bytes()
    archive_key = f"/{PUBLIC_TAG}/svc-workflow-1.0.0.zip"
    output = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(assets[archive_key])) as before,
        zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as after,
    ):
        for name in reversed(before.namelist()):
            after.writestr(name, before.read(name))
    assert output.getvalue() != assets[archive_key]
    assets[archive_key] = output.getvalue()
    catalog_key = f"/{PUBLIC_TAG}/svc-skills-1.0.0.json"
    catalog = json.loads(assets[catalog_key])
    next(skill for skill in catalog["skills"] if skill["name"] == "svc-workflow")[
        "archive_sha256"
    ] = hashlib.sha256(output.getvalue()).hexdigest()
    assets[catalog_key] = json.dumps(catalog, indent=2).encode()
    assets[catalog_key + ".sha256"] = (
        hashlib.sha256(assets[catalog_key]).hexdigest().encode()
    )
    code, stdout, stderr = invoke_text(["skills", "check", *scope])
    assert (code, stderr) == (0, "")
    assert assert_compact_json(stdout)["status"] == "current"
    assert apply(["skills", "install", *scope])["status"] == "noop"
    assert record.read_bytes() == original_record
