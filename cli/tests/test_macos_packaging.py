from __future__ import annotations

import hashlib
import json
import plistlib
import shutil
import subprocess
from pathlib import Path

import pytest

from tools import macos_app as app
from tools import publish_macos_release as release


SHA = "a" * 40


def bundle(path: Path, identity: str = app.BUNDLE_ID, content: str = "old") -> Path:
    (path / "Contents").mkdir(parents=True)
    (path / "Contents/Info.plist").write_bytes(
        plistlib.dumps({"CFBundleIdentifier": identity})
    )
    (path / "Contents/payload").write_text(content)
    return path


def test_failed_install_restores_existing_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = bundle(tmp_path / "SVC.app")
    new = bundle(tmp_path / "candidate.app", content="new")

    def verify(path: Path) -> None:
        app.bundle_info(path)
        if path == old and (path / "Contents/payload").read_text() == "new":
            raise ValueError("signature mismatch after replacement")

    monkeypatch.setattr(app, "verify", verify)
    with pytest.raises(ValueError, match="signature mismatch"):
        app.replace_bundle(new, old)
    assert (old / "Contents/payload").read_text() == "old"
    assert (new / "Contents/payload").read_text() == "new"


def test_failed_rollback_preserves_recoverable_old_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = bundle(tmp_path / "SVC.app")
    candidate = bundle(tmp_path / "candidate.app", content="new")
    rename = Path.rename

    def verify(path: Path) -> None:
        if path == destination:
            raise ValueError("installed signature failed")
        app.bundle_info(path)

    def fail_restore(path: Path, target: Path) -> Path:
        if path.name == "old.app":
            raise OSError("restore denied")
        return rename(path, target)

    monkeypatch.setattr(app, "verify", verify)
    monkeypatch.setattr(Path, "rename", fail_restore)
    with pytest.raises(ValueError, match="旧应用保留在"):
        app.replace_bundle(candidate, destination)
    backups = list(tmp_path.glob(".svc-replace-*/old.app/Contents/payload"))
    assert len(backups) == 1 and backups[0].read_text() == "old"


def test_reinstall_replaces_contents_without_nesting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = bundle(tmp_path / "SVC.app")
    new = bundle(tmp_path / "candidate.app", content="new")
    monkeypatch.setattr(app, "verify", app.bundle_info)
    app.replace_bundle(new, old)
    app.replace_bundle(new, old)
    assert (old / "Contents/payload").read_text() == "new"
    assert not (old / "candidate.app").exists()
    assert not list(tmp_path.glob(".svc-replace-*"))


def test_install_refuses_foreign_bundle_and_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    foreign = bundle(tmp_path / "SVC.app", identity="other.app")
    new = bundle(tmp_path / "candidate.app", content="new")
    monkeypatch.setattr(app, "verify", app.bundle_info)
    with pytest.raises(ValueError, match="不是 SVC"):
        app.replace_bundle(new, foreign)
    link = tmp_path / "link.app"
    link.symlink_to(foreign, target_is_directory=True)
    with pytest.raises(ValueError, match="符号链接"):
        app.replace_bundle(new, link)
    assert (foreign / "Contents/payload").read_text() == "old"


def test_signing_requires_an_unambiguous_development_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identities = f'1) {"A" * 40} "Apple Development: One"\n2) {"B" * 40} "Apple Development: Two"'
    monkeypatch.setattr(app, "run", lambda *args, **kwargs: identities)
    monkeypatch.delenv("SVC_SIGNING_IDENTITY", raising=False)
    with pytest.raises(ValueError, match="唯一"):
        app.signing_identity()
    monkeypatch.setenv("SVC_SIGNING_IDENTITY", "B" * 40)
    assert app.signing_identity() == "B" * 40
    monkeypatch.setenv("SVC_SIGNING_IDENTITY", "missing")
    with pytest.raises(ValueError):
        app.signing_identity()


def test_local_runtime_is_reused_only_for_matching_wheel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wheel = tmp_path / "fixture.whl"
    wheel.write_bytes(b"wheel")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    runtime = tmp_path / "Library/Application Support/SVC/runtimes" / digest[:20]
    (runtime / "bin").mkdir(parents=True)
    (runtime / "bin/svc").write_text("fixture")
    marker = runtime / ".svc-wheel-sha256"
    marker.write_text(digest)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert app.install_runtime(wheel) == runtime / "bin/svc"
    marker.write_text("wrong")
    with pytest.raises(ValueError, match="未完成"):
        app.install_runtime(wheel)


def assets(path: Path) -> Path:
    path.mkdir()
    manifest = {
        "version": "0.1.0",
        "revision": SHA,
        "architecture": "arm64",
        "signing": "ad-hoc",
        "notarized": False,
        "cli_wheel": "svc-17.0.0.whl",
        "cli_version": "17.0.0",
        "cli_result_schemas": app.CLI_RESULT_SCHEMAS,
    }
    (path / "release.json").write_text(json.dumps(manifest))
    for name in ["SVC-0.1.0-macos-arm64.zip", "svc-17.0.0.whl", "INSTALL.md"]:
        (path / name).write_text(name)
    (path / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256(file.read_bytes()).hexdigest()}  {file.name}\n"
            for file in sorted(path.iterdir())
        )
    )
    return path


def test_release_rejects_wrong_source_corruption_and_extra_assets(
    tmp_path: Path,
) -> None:
    directory = assets(tmp_path / "assets")
    assert len(release.verified_assets(directory, SHA)) == 5
    with pytest.raises(ValueError, match="commit 不一致"):
        release.verified_assets(directory, "b" * 40)
    extra = directory / "personal-settings.txt"
    extra.write_text("must not ship")
    with pytest.raises(ValueError, match="未声明"):
        release.verified_assets(directory, SHA)
    extra.unlink()
    (directory / "INSTALL.md").write_text("changed")
    with pytest.raises(ValueError, match="摘要不匹配"):
        release.verified_assets(directory, SHA)


def test_release_rejects_unsafe_checksum_paths(tmp_path: Path) -> None:
    directory = assets(tmp_path / "assets")
    (directory / "SHA256SUMS").write_text(f"{'a' * 64}  ../outside\n")
    with pytest.raises(ValueError, match="摘要条目"):
        release.verified_assets(directory, SHA)


@pytest.mark.parametrize("draft", [None, True, False])
def test_publish_recovers_draft_or_preserves_identical_published_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, draft: bool | None
) -> None:
    source = assets(tmp_path / "source")
    remote = tmp_path / "remote"
    remote.mkdir()
    notes = tmp_path / "CHANGELOG.md"
    notes.write_text("## [0.1.0] - 2026-10-26\n\n初版。\n")
    if draft is False:
        shutil.copytree(source, remote, dirs_exist_ok=True)
    elif draft is True:
        shutil.copy2(source / "INSTALL.md", remote / "INSTALL.md")
    state = {
        "draft": draft is not False,
        "tag_name": "macos-v0.1.0",
        "target_commitish": SHA,
        "assets": [{"name": p.name} for p in remote.iterdir()],
    }
    exists = draft is not None
    writes: list[str] = []

    def api(path: str) -> dict[str, object]:
        if "/git/ref/" in path:
            return {"object": {"type": "commit", "sha": SHA}}
        return state

    def gh(*args: str) -> str:
        nonlocal exists
        if args[1] == "view":
            assert args == (
                "release",
                "view",
                "macos-v0.1.0",
                "--repo",
                "owner/repo",
                "--json",
                "apiUrl",
            )
            if not exists:
                raise subprocess.CalledProcessError(1, args, stderr="release not found")
            return json.dumps(
                {"apiUrl": "https://api.github.com/repos/owner/repo/releases/123"}
            )
        action = args[1]
        if action == "download":
            destination = Path(args[args.index("--dir") + 1])
            destination.mkdir(exist_ok=True)
            names = (
                [args[args.index("--pattern") + 1]]
                if "--pattern" in args
                else [p.name for p in remote.iterdir()]
            )
            for name in names:
                shutil.copy2(remote / name, destination / name)
        elif action == "create":
            assert not exists
            assert args[args.index("--target") + 1] == SHA
            assert "--draft" in args
            exists = True
            writes.append(action)
        elif action == "upload":
            writes.append(action)
            shutil.copy2(Path(args[3]), remote / Path(args[3]).name)
        elif action == "edit":
            writes.append(action)
            state["draft"] = False
        else:
            pytest.fail(f"unexpected remote action: {args}")
        return ""

    monkeypatch.setattr(release, "optional_api", api)
    monkeypatch.setattr(release, "gh", gh)
    release.publish("owner/repo", source, SHA, notes)
    assert release.verified_assets(remote, SHA) == release.verified_assets(source, SHA)
    assert state["draft"] is False
    assert bool(writes) is (draft is not False)


def test_release_tag_cannot_move_to_another_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        release,
        "optional_api",
        lambda path: {"object": {"type": "commit", "sha": "b" * 40}},
    )
    with pytest.raises(ValueError, match="禁止覆盖"):
        release.validate_tag("owner/repo", "macos-v0.1.0", SHA)


@pytest.mark.parametrize(
    "message,missing",
    [("release not found", True), ("HTTP 401: bad credentials", False)],
)
def test_release_lookup_distinguishes_absence_from_access_failure(
    monkeypatch: pytest.MonkeyPatch, message: str, missing: bool
) -> None:
    def fail(*args: str) -> str:
        raise subprocess.CalledProcessError(1, args, stderr=message)

    monkeypatch.setattr(release, "gh", fail)
    if missing:
        assert release.find_release("owner/repo", "macos-v0.1.0") is None
    else:
        with pytest.raises(subprocess.CalledProcessError):
            release.find_release("owner/repo", "macos-v0.1.0")
