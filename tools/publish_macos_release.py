"""Publish an immutable, source-bound macOS preview from verified CI assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from tools.release_notes import release_section
from tools.macos_app import CLI_RESULT_SCHEMAS


def gh(*args: str) -> str:
    return subprocess.check_output(
        ["gh", *args], text=True, stderr=subprocess.PIPE
    ).strip()


def optional_api(path: str) -> dict[str, Any] | None:
    result = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if result.returncode:
        if "HTTP 404" in result.stderr:
            return None
        raise RuntimeError(result.stderr)
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError("GitHub 返回了非对象结果")
    return value


def verified_assets(directory: Path, revision: str) -> dict[str, str]:
    if re.fullmatch(r"[a-f0-9]{40}", revision) is None:
        raise ValueError("发布 revision 必须是完整 commit SHA")
    manifest = json.loads((directory / "release.json").read_text())
    if manifest.get("cli_result_schemas") != CLI_RESULT_SCHEMAS:
        raise ValueError("配套 CLI schema 清单不匹配")
    if re.fullmatch(r"\d+\.\d+\.\d+", manifest.get("cli_version", "")) is None:
        raise ValueError("配套 CLI 版本无效")
    if manifest["revision"] != revision:
        raise ValueError("发布制品与目标 commit 不一致，或来自脏工作区")
    if manifest["signing"] != "ad-hoc" or manifest["notarized"] is not False:
        raise ValueError("此发布器仅接受已声明的未公证开发预览")
    if re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"]) is None:
        raise ValueError("无效发布版本")
    hashes: dict[str, str] = {}
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        if (
            Path(name).name != name
            or name in hashes
            or re.fullmatch(r"[a-f0-9]{64}", digest) is None
        ):
            raise ValueError("无效或重复的附件摘要条目")
        path = directory / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"附件摘要不匹配：{name}")
        hashes[name] = digest
    expected = {
        f"SVC-{manifest['version']}-macos-{manifest['architecture']}.zip",
        manifest["cli_wheel"],
        "release.json",
        "INSTALL.md",
    }
    if set(hashes) != expected or {p.name for p in directory.iterdir()} != expected | {
        "SHA256SUMS"
    }:
        raise ValueError("附件缺失或存在未声明的附件")
    hashes["SHA256SUMS"] = hashlib.sha256(
        (directory / "SHA256SUMS").read_bytes()
    ).hexdigest()
    return hashes


def validate_tag(repo: str, tag: str, revision: str) -> None:
    ref = optional_api(f"repos/{repo}/git/ref/tags/{tag}")
    if ref is None:
        return
    target = ref["object"]
    if target["type"] == "tag":
        annotated = optional_api(f"repos/{repo}/git/tags/{target['sha']}")
        if annotated is None:
            raise ValueError("发布 tag 对象不存在")
        target = annotated["object"]
    if target["type"] != "commit" or target["sha"] != revision:
        raise ValueError("发布 tag 已指向其他 commit，禁止覆盖")


def find_release(repo: str, tag: str) -> dict[str, Any] | None:
    # gh resolves pending draft tags through GraphQL, then exposes their exact REST ID.
    try:
        metadata = json.loads(
            gh("release", "view", tag, "--repo", repo, "--json", "apiUrl")
        )
    except subprocess.CalledProcessError as error:
        if (
            error.returncode == 1
            and "release not found" in (error.stderr or "").lower()
        ):
            return None
        raise
    return optional_api(metadata["apiUrl"])


def publish(repo: str, directory: Path, revision: str, changelog: Path) -> None:
    hashes = verified_assets(directory, revision)
    manifest = json.loads((directory / "release.json").read_text())
    version = manifest["version"]
    tag = f"macos-v{version}"
    notes = release_section(changelog.read_text(), version)
    validate_tag(repo, tag, revision)
    release = find_release(repo, tag)
    with tempfile.TemporaryDirectory(prefix="svc-release-") as temporary:
        root = Path(temporary)
        if release is None:
            notes_path = root / "notes.md"
            notes_path.write_text(
                notes
                + "\n开发预览：ad-hoc 签名，未公证。安装与信任边界见附件 INSTALL.md。\n"
            )
            gh(
                "release",
                "create",
                tag,
                "--repo",
                repo,
                "--target",
                revision,
                "--draft",
                "--prerelease",
                "--title",
                f"SVC macOS {version} · 开发预览",
                "--notes-file",
                str(notes_path),
            )
            release = find_release(repo, tag)
        if release is None:
            raise ValueError("无法读取创建的 release")
        validate_tag(repo, tag, revision)
        if release["draft"] and release["target_commitish"] != revision:
            raise ValueError("已有草稿的目标 commit 不一致，禁止发布")
        existing = {asset["name"] for asset in release["assets"]}
        if existing - set(hashes):
            raise ValueError("Release 有未声明附件，禁止静默修改")
        for name, expected in hashes.items():
            if name in existing:
                gh(
                    "release",
                    "download",
                    tag,
                    "--repo",
                    repo,
                    "--pattern",
                    name,
                    "--dir",
                    str(root),
                )
                if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
                    raise ValueError(f"已上传附件内容不同，禁止覆盖：{name}")
            elif release["draft"]:
                gh("release", "upload", tag, str(directory / name), "--repo", repo)
            else:
                raise ValueError(f"已发布 release 缺少附件，禁止修改：{name}")
        verification = root / "verify"
        gh("release", "download", tag, "--repo", repo, "--dir", str(verification))
        verified_assets(verification, revision)
        if release["draft"]:
            gh(
                "release",
                "edit",
                tag,
                "--repo",
                repo,
                "--draft=false",
                "--prerelease",
                "--latest=false",
            )
        print(f"https://github.com/{repo}/releases/tag/{tag}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--changelog", type=Path, default=Path("MACOS_CHANGELOG.md"))
    args = parser.parse_args()
    publish(args.repo, args.artifacts, args.revision, args.changelog)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
