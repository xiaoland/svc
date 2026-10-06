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
from test_skills import release_bytes, standalone_files


@pytest.fixture
def releases(monkeypatch: pytest.MonkeyPatch):
    assets = {
        f"/16.0.0/{filename}": content
        for filename, content in standalone_files().items()
    }
    legacy = release_bytes(version="15.0.0")
    assets["/15.0.0/svc-corpus-15.0.0.zip"] = legacy
    assets["/15.0.0/svc-corpus-15.0.0.zip.sha256"] = (
        hashlib.sha256(legacy).hexdigest().encode()
    )
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
        skills, "CATALOG_DOWNLOAD", base + "/{version}/svc-skills-{version}.json"
    )
    monkeypatch.setattr(
        skills, "RELEASE_DOWNLOAD", base + "/{version}/svc-corpus-{version}.zip"
    )
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
    scope = ["--agent", "codex", "--version", "16.0.0", "--json"]
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
        "/16.0.0/svc-skills-16.0.0.json",
        "/16.0.0/svc-skills-16.0.0.json.sha256",
        "/16.0.0/svc-workflow-16.0.0.zip",
    }
    record_path = Path(".agents/skills/.svc/svc-workflow.json")
    recorded = json.loads((single / record_path).read_text())
    assert (
        recorded["archive_sha256"]
        == hashlib.sha256(assets["/16.0.0/svc-workflow-16.0.0.zip"]).hexdigest()
    )
    assert recorded["source"].endswith("/16.0.0/svc-workflow-16.0.0.zip")
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
        "/16.0.0/svc-skills-16.0.0.json",
        "/16.0.0/svc-skills-16.0.0.json.sha256",
    }
    assert not any("svc-corpus" in request for request in requests)


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


@pytest.mark.parametrize("corruption", ["catalog", "archive", "file-map", "extra-file"])
def test_invalid_selected_artifact_never_writes_or_falls_back_to_legacy(
    tmp_path: Path, releases, corruption: str
) -> None:
    assets, requests = releases
    catalog_key = "/16.0.0/svc-skills-16.0.0.json"
    archive_key = "/16.0.0/svc-workflow-16.0.0.zip"
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
    else:
        raw = io.BytesIO(assets[archive_key])
        with zipfile.ZipFile(raw, "a") as stream:
            stream.writestr("svc-workflow/unlisted.txt", b"extra")
        assets[archive_key] = raw.getvalue()
        skill["archive_sha256"] = hashlib.sha256(raw.getvalue()).hexdigest()
    if corruption in {"file-map", "extra-file"}:
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
            "16.0.0",
            "--skill",
            "svc-workflow",
            "--json",
        ]
    )
    assert code != 0
    assert not (tmp_path / ".agents").exists()
    assert not any("svc-corpus" in request for request in requests)


def test_explicit_published_v15_keeps_legacy_online_and_offline_consumption(
    tmp_path: Path, releases
) -> None:
    assets, requests = releases
    online = tmp_path / "online"
    offline = tmp_path / "offline"
    online.mkdir()
    offline.mkdir()
    scope = ["--agent", "codex", "--skill", "svc-workflow", "--json"]
    assert (
        apply(
            ["skills", "install", "--repo", str(online), *scope, "--version", "15.0.0"]
        )["status"]
        == "applied"
    )
    assert set(requests) == {
        "/15.0.0/svc-corpus-15.0.0.zip",
        "/15.0.0/svc-corpus-15.0.0.zip.sha256",
    }
    archive = tmp_path / "renamed-v15.zip"
    archive.write_bytes(assets["/15.0.0/svc-corpus-15.0.0.zip"])
    archive.with_suffix(".zip.sha256").write_bytes(
        assets["/15.0.0/svc-corpus-15.0.0.zip.sha256"]
    )
    assert (
        apply(
            [
                "skills",
                "install",
                "--repo",
                str(offline),
                *scope,
                "--archive",
                str(archive),
            ]
        )["status"]
        == "applied"
    )
    record = Path(".agents/skills/.svc/svc-workflow.json")
    for repo in (online, offline):
        assert json.loads((repo / record).read_text())["version"] == "15.0.0"


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
    assert (
        apply(["skills", "install", *scope, "--version", "15.0.0"])["status"]
        == "applied"
    )
    assert (
        apply(["skills", "update", *scope, "--version", "16.0.0"])["status"]
        == "applied"
    )
    record = json.loads(
        (tmp_path / ".agents/skills/.svc/svc-workflow.json").read_text()
    )
    assert record["version"] == "16.0.0"
    assert (
        record["archive_sha256"]
        == hashlib.sha256(assets["/16.0.0/svc-workflow-16.0.0.zip"]).hexdigest()
    )
    entry = tmp_path / ".agents/skills/svc-workflow/SKILL.md"
    edited = entry.read_bytes() + b"Local customization\n"
    entry.write_bytes(edited)
    code, stdout, _ = invoke_text(["skills", "update", *scope, "--version", "16.0.0"])
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
        "16.0.0",
        "--skill",
        "svc-workflow",
        "--json",
    ]
    code, stdout, _ = invoke_text(command)
    assert code == 0
    digest = str(assert_compact_json(stdout)["plan_digest"])
    assets.update(
        {
            f"/16.0.0/{filename}": raw
            for filename, raw in standalone_files(
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
        "16.0.0",
        "--skill",
        "svc-workflow",
        "--json",
    ]
    assert apply(["skills", "install", *scope])["status"] == "applied"
    record = tmp_path / ".agents/skills/.svc/svc-workflow.json"
    original_record = record.read_bytes()
    archive_key = "/16.0.0/svc-workflow-16.0.0.zip"
    output = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(assets[archive_key])) as before,
        zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as after,
    ):
        for name in reversed(before.namelist()):
            after.writestr(name, before.read(name))
    assert output.getvalue() != assets[archive_key]
    assets[archive_key] = output.getvalue()
    catalog_key = "/16.0.0/svc-skills-16.0.0.json"
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
