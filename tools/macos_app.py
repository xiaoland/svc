"""Build, sign, install and archive the native SVC application."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from tools.release_notes import release_section

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ID = "dev.svc.menubar"
DEFAULT_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


def run(*args: str, capture: bool = False) -> str:
    result = subprocess.run(
        args, cwd=ROOT, check=True, text=True, capture_output=capture
    )
    return result.stdout.strip() if capture else ""


def version() -> str:
    value = (ROOT / "macos/VERSION").read_text().strip()
    if (
        re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value)
        is None
    ):
        raise ValueError("macos/VERSION 必须为 major.minor.patch")
    return value


def signing_identity() -> str:
    override = os.environ.get("SVC_SIGNING_IDENTITY")
    identities = run(
        "security", "find-identity", "-v", "-p", "codesigning", capture=True
    )
    candidates = re.findall(r'([A-F0-9]{40}) "(Apple Development:[^"]+)"', identities)
    if override:
        selected = [sha for sha, name in candidates if override in (sha, name)]
    else:
        selected = [sha for sha, _ in candidates]
    if len(selected) != 1:
        raise ValueError(
            "需要唯一 Apple Development 签名身份，或设置 SVC_SIGNING_IDENTITY 选择已有身份"
        )
    return selected[0]


def bundle_info(path: Path) -> dict[str, object]:
    if path.is_symlink():
        raise ValueError(f"拒绝替换符号链接：{path}")
    with (path / "Contents/Info.plist").open("rb") as stream:
        info = plistlib.load(stream)
    if info.get("CFBundleIdentifier") != BUNDLE_ID:
        raise ValueError(f"不是 SVC 应用：{path}")
    return info


def verify(path: Path) -> None:
    bundle_info(path)
    run("codesign", "--verify", "--strict", str(path))


def build(profile: str, output: Path, cli: str = "") -> Path:
    release = profile == "release"
    identity = "-" if release else signing_identity()
    configuration = "release" if release else "debug"
    revision = run("git", "rev-parse", "HEAD", capture=True)
    dirty = bool(run("git", "status", "--porcelain", capture=True))
    build_number = run(
        "git", "rev-list", "--first-parent", "--count", "HEAD", capture=True
    )
    run("swift", "build", "--package-path", str(ROOT / "macos"), "-c", configuration)
    binary_dir = Path(
        run(
            "swift",
            "build",
            "--package-path",
            str(ROOT / "macos"),
            "-c",
            configuration,
            "--show-bin-path",
            capture=True,
        )
    )
    output.mkdir(parents=True, exist_ok=True)
    bundle = output / "SVC.app"
    with tempfile.TemporaryDirectory(prefix=".svc-build-", dir=output) as temporary:
        prepared = Path(temporary) / "SVC.app"
        executable = prepared / "Contents/MacOS/SVCMenuBar"
        executable.parent.mkdir(parents=True)
        shutil.copy2(binary_dir / "SVCMenuBar", executable)
        if release:
            run("xcrun", "strip", "-S", str(executable))
        resources = prepared / "Contents/Resources"
        resources.mkdir()
        shutil.copy2(ROOT / "LICENSE", resources / "LICENSE")
        info = {
            "CFBundleExecutable": "SVCMenuBar",
            "CFBundleIdentifier": BUNDLE_ID,
            "CFBundleName": "SVC",
            "CFBundleDisplayName": "SVC",
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": version(),
            "CFBundleVersion": build_number,
            "LSMinimumSystemVersion": "14.0",
            "NSPrincipalClass": "NSApplication",
            "LSUIElement": True,
            "SVCSourceRevision": revision + ("-dirty" if dirty else ""),
            "SVCBuildProfile": profile,
            "SVCDefaultCLIPath": "" if release else cli,
            "SVCDefaultSearchPath": DEFAULT_PATH
            if release
            else os.environ.get("PATH", DEFAULT_PATH),
        }
        with (prepared / "Contents/Info.plist").open("wb") as stream:
            plistlib.dump(info, stream)
        run(
            "codesign",
            "--force",
            "--sign",
            identity,
            "--options",
            "runtime",
            "--timestamp=none",
            str(prepared),
        )
        verify(prepared)
        replace_bundle(prepared, bundle)
    return bundle


def replace_bundle(prepared: Path, destination: Path) -> None:
    """Keep the old bundle recoverable until the installed replacement verifies."""
    verify(prepared)
    if destination.exists() or destination.is_symlink():
        bundle_info(destination)
    stage = Path(tempfile.mkdtemp(prefix=".svc-replace-", dir=destination.parent))
    candidate = stage / "new.app"
    backup = stage / "old.app"
    try:
        shutil.copytree(prepared, candidate, symlinks=True)
        verify(candidate)
        had_previous = destination.exists()
        try:
            if had_previous:
                destination.rename(backup)
            candidate.rename(destination)
            verify(destination)
        except BaseException:
            try:
                if backup.exists():
                    if destination.exists():
                        destination.rename(stage / "failed.app")
                    backup.rename(destination)
                elif not had_previous and destination.exists():
                    destination.rename(stage / "failed.app")
            except OSError as error:
                raise ValueError(f"安装恢复失败，旧应用保留在：{backup}") from error
            raise
        else:
            if backup.exists():
                shutil.rmtree(backup)
    finally:
        if not backup.exists():
            shutil.rmtree(stage)


def stop_application() -> None:
    def running() -> bool:
        return (
            subprocess.run(
                ["pgrep", "-x", "SVCMenuBar"], capture_output=True
            ).returncode
            == 0
        )

    if not running():
        return
    deadline = time.monotonic() + 30
    try:
        subprocess.run(
            ["/usr/bin/osascript", "-e", f'tell application id "{BUNDLE_ID}" to quit'],
            check=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError("SVC 退出超时，保留原安装；操作结束后可再次安装") from error
    while running():
        if time.monotonic() >= deadline:
            raise ValueError("SVC 仍有服务操作进行中，保留原安装；操作结束后可再次安装")
        time.sleep(0.25)


def build_wheel(output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    run("pdm", "build", "-p", "cli", "--no-sdist", "--no-clean", "--dest", str(output))
    wheels = list(output.glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError("配套 CLI 输出目录必须恰好包含一个 wheel")
    return wheels[0]


def install_runtime(wheel: Path) -> Path:
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    root = Path.home() / "Library/Application Support/SVC/runtimes" / digest[:20]
    executable = root / "bin/svc"
    marker = root / ".svc-wheel-sha256"
    if (
        marker.is_file()
        and marker.read_text().strip() == digest
        and executable.is_file()
    ):
        return executable
    if root.exists():
        raise ValueError(f"发现未完成的 CLI 环境，请先检查：{root}")
    root.parent.mkdir(parents=True, exist_ok=True)
    try:
        run(sys.executable, "-m", "venv", str(root))
        run(
            str(root / "bin/python"),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            str(wheel),
        )
        schema = json.loads(
            run(str(executable), "dev", "status", "--json-schema", capture=True)
        )
        if schema.get("x-svc-result-schema-version") != 3:
            raise ValueError("配套 CLI 的 dev-status schema 不是 3")
        marker.write_text(digest + "\n")
        return executable
    except BaseException:
        shutil.rmtree(root)
        raise


def install(destination: Path, launch: bool) -> Path:
    # A fixed source timestamp lets app-only iterations reuse the exact same CLI wheel/runtime.
    os.environ.setdefault(
        "SOURCE_DATE_EPOCH", run("git", "log", "-1", "--format=%ct", capture=True)
    )
    with tempfile.TemporaryDirectory(prefix="svc-cli-wheel-") as temporary:
        cli = install_runtime(build_wheel(Path(temporary)))
    bundle = build("local", ROOT / "dist/macos/local", str(cli))
    verify(bundle)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        bundle_info(destination)
    stop_application()
    replace_bundle(bundle, destination)
    if launch:
        run("/usr/bin/open", "-g", str(destination), "--args", "--background")
    return destination


def check_release(require_clean: bool = False) -> str:
    value = version()
    release_section((ROOT / "MACOS_CHANGELOG.md").read_text(), value)
    if require_clean and run("git", "status", "--porcelain", capture=True):
        raise ValueError("发布只接受干净且已提交的源码")
    return value


def archive(output: Path, require_clean: bool) -> None:
    value = check_release(require_clean)
    os.environ.setdefault(
        "SOURCE_DATE_EPOCH", run("git", "log", "-1", "--format=%ct", capture=True)
    )
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("发布输出目录必须为空，避免混入历史附件")
    with tempfile.TemporaryDirectory(prefix="svc-macos-release-") as temporary:
        bundle = build("release", Path(temporary))
        epoch = int(os.environ["SOURCE_DATE_EPOCH"])
        for member in [*bundle.rglob("*"), bundle]:
            os.utime(member, (epoch, epoch), follow_symlinks=False)
        name = f"SVC-{value}-macos-{platform.machine()}.zip"
        run(
            "/usr/bin/ditto",
            "-c",
            "-k",
            "--norsrc",
            "--noextattr",
            "--noqtn",
            "--keepParent",
            str(bundle),
            str(output / name),
        )
        info = bundle_info(bundle)
    wheel = build_wheel(output)
    manifest = {
        "version": value,
        "revision": info["SVCSourceRevision"],
        "build": info["CFBundleVersion"],
        "architecture": platform.machine(),
        "signing": "ad-hoc",
        "notarized": False,
        "cli_wheel": wheel.name,
        "dev_status_schema": 3,
    }
    (output / "release.json").write_text(json.dumps(manifest, indent=2) + "\n")
    shutil.copy2(ROOT / "macos/INSTALL.md", output / "INSTALL.md")
    assets = sorted(output.iterdir())
    (output / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
            for path in assets
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("version")
    build_command = commands.add_parser("build")
    build_command.add_argument(
        "--profile", choices=["local", "release"], default="local"
    )
    build_command.add_argument("--cli", default="")
    build_command.add_argument("--output", type=Path, default=ROOT / "dist/SVC-build")
    install_command = commands.add_parser("install")
    install_command.add_argument(
        "--destination", type=Path, default=Path("/Applications/SVC.app")
    )
    install_command.add_argument("--launch", action="store_true")
    check = commands.add_parser("check")
    check.add_argument("--require-clean", action="store_true")
    package = commands.add_parser("archive")
    package.add_argument("--output", type=Path, required=True)
    package.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "version":
            print(version())
        elif args.command == "check":
            print(check_release(args.require_clean))
        elif args.command == "build":
            print(build(args.profile, args.output.resolve(), args.cli))
        elif args.command == "install":
            print(install(args.destination.absolute(), args.launch))
        else:
            archive(args.output.resolve(), args.require_clean)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"SVC macOS: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
