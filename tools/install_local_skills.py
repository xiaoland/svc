"""Activate a committed Skills snapshot for local Agent hosts."""

from __future__ import annotations

import argparse
import fcntl
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from tools.check_skills import SKILL_NAMES, check


def archive_skills(root: Path, revision: str, staging: Path) -> Path:
    archive = staging / "skills.tar"
    with archive.open("wb") as output:
        subprocess.run(
            (
                "git",
                "archive",
                revision,
                "--",
                *(f"corpus/{name}" for name in sorted(SKILL_NAMES)),
            ),
            cwd=root,
            check=True,
            stdout=output,
        )
    with tarfile.open(archive) as data:
        for member in data:
            parts = PurePosixPath(member.name).parts
            in_skills = parts == ("corpus",) or (
                len(parts) >= 2 and parts[0] == "corpus" and parts[1] in SKILL_NAMES
            )
            if (
                not in_skills
                or ".." in parts
                or not (member.isdir() or member.isfile())
            ):
                raise ValueError(
                    f"Skill 快照包含不支持的 Git 路径或文件类型：{member.name}"
                )
            destination = staging.joinpath(*parts)
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            contents = data.extractfile(member)
            assert contents is not None
            destination.parent.mkdir(parents=True, exist_ok=True)
            with contents, destination.open("xb") as output:
                shutil.copyfileobj(contents, output)
            if member.mode & 0o111:
                destination.chmod(0o755)
    corpus = staging / "corpus"
    check(corpus)
    return corpus


def snapshot_files(directory: Path) -> dict[Path, tuple[bytes, bool]]:
    files = {}
    for path in directory.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f"Skill 快照包含不支持的文件类型：{path}")
        if path.is_file():
            files[path.relative_to(directory)] = (
                path.read_bytes(),
                bool(path.stat().st_mode & 0o111),
            )
    return files


def install(root: Path, revision: str, store: Path, host: Path) -> str:
    revision = subprocess.check_output(
        ("git", "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}"),
        cwd=root,
        text=True,
    ).strip()
    store.mkdir(parents=True, exist_ok=True)
    with (store / ".install.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = store / "current"
        if current.exists() and not current.is_symlink():
            raise ValueError(f"现有路径不是试用快照链接：{current}")
        if current.is_symlink() and current.readlink().parent != Path("revisions"):
            raise ValueError(f"现有链接不指向试用快照：{current}")

        missing_links = []
        for name in sorted(SKILL_NAMES):
            link = host / name
            target = current / name
            record = host / ".svc" / f"{name}.json"
            if record.exists() or record.is_symlink():
                raise ValueError(f"先备份并移开旧版 CLI 安装记录：{record}")
            if link.is_symlink() and link.readlink() == target:
                continue
            if link.exists() or link.is_symlink():
                raise ValueError(f"先备份并移开已有 Skill 入口：{link}")
            missing_links.append((link, target))

        with tempfile.TemporaryDirectory(dir=store) as temp:
            staging = Path(temp)
            corpus = archive_skills(root, revision, staging)
            relative_snapshot = Path("revisions") / revision
            snapshot = store / relative_snapshot
            if snapshot.is_symlink():
                raise ValueError(f"现有快照路径是外部链接：{snapshot}")
            if snapshot.exists():
                if not snapshot.is_dir() or snapshot_files(snapshot) != snapshot_files(
                    corpus
                ):
                    raise ValueError(f"现有 Skills 快照与提交不同：{snapshot}")
            else:
                snapshot.parent.mkdir(exist_ok=True)
                corpus.rename(snapshot)

            host.mkdir(parents=True, exist_ok=True)
            next_current = staging / "current"
            next_current.symlink_to(relative_snapshot, target_is_directory=True)
            created = []
            try:
                for link, target in missing_links:
                    link.symlink_to(target, target_is_directory=True)
                    created.append(link)
                next_current.replace(current)
            except OSError:
                for link in created:
                    link.unlink()
                raise
    return revision


def main() -> int:
    parser = argparse.ArgumentParser(description="从本地 Git 提交安装或回退 SVC Skills")
    parser.add_argument(
        "revision", nargs="?", default="HEAD", help="本地 Git 引用或 SHA"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    store = (data / "svc/dogfood/skills").resolve()
    host = Path.home() / ".agents/skills"
    try:
        revision = install(root, args.revision, store, host)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"{exc}\n")
    print(f"源码提交 {revision}\nSkills 路径 {store / 'current'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
