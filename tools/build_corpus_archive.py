"""Build and validate the reproducible Corpus Skills release archive."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

from tools.check_skills import SKILL_NAMES, check
from tools.corpus import CORPUS_REPOSITORY, read_corpus_version


_SHA = re.compile(r"[0-9a-f]{40}")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _revision(root: Path, value: str | None) -> str:
    head = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if value is None:
        value = head
    if _SHA.fullmatch(value) is None:
        raise ValueError(f"Archive revision must be a full commit SHA: {value!r}")
    if value != head:
        raise ValueError(f"Archive revision must equal HEAD: {value} != {head}")
    return value


def _source_files(root: Path) -> dict[str, bytes]:
    check(root / "corpus", root / "LICENSE", root / "cli" / "LICENSE")
    files: dict[str, bytes] = {}
    for name in sorted(SKILL_NAMES):
        skill_root = root / "corpus" / name
        for path in sorted(skill_root.rglob("*")):
            if path.is_symlink() or not path.is_file():
                if path.is_symlink():
                    raise ValueError(f"Corpus archive cannot contain symlinks: {path}")
                continue
            relative = path.relative_to(root).as_posix()
            files[relative] = path.read_bytes()
    for path in sorted(root.glob("LICENSE*")):
        if path.is_file() and not path.is_symlink():
            files[path.name] = path.read_bytes()
    return files


def _assert_clean_source(root: Path) -> None:
    source_paths = ["pyproject.toml", "corpus"] + [
        path.name for path in root.glob("LICENSE*") if path.is_file()
    ]
    changed = subprocess.run(
        ("git", "diff", "--quiet", "HEAD", "--", *source_paths),
        cwd=root,
        check=False,
    )
    if changed.returncode != 0:
        raise ValueError(
            "Release source is modified; commit pyproject.toml and corpus first"
        )
    untracked = subprocess.run(
        ("git", "ls-files", "--others", "--exclude-standard", "--", *source_paths),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    if untracked:
        raise ValueError(f"Release source has untracked files: {', '.join(untracked)}")


def _assert_revision_sources(
    root: Path, revision: str, files: dict[str, bytes]
) -> None:
    paths = {**files, "pyproject.toml": (root / "pyproject.toml").read_bytes()}
    for path, content in paths.items():
        result = subprocess.run(
            ("git", "show", f"{revision}:{path}"),
            cwd=root,
            check=False,
            capture_output=True,
        )
        if result.returncode != 0 or result.stdout != content:
            raise ValueError(f"Release source does not match git {revision}: {path}")


def _manifest(version: str, revision: str, files: dict[str, bytes]) -> bytes:
    skills = []
    for name in sorted(SKILL_NAMES):
        prefix = f"corpus/{name}/"
        members = {
            path.removeprefix(prefix): _sha256(content)
            for path, content in sorted(files.items())
            if path.startswith(prefix)
        }
        skills.append({"name": name, "path": f"corpus/{name}", "files": members})
    value = {
        "schema_version": 1,
        "version": version,
        "repository": CORPUS_REPOSITORY,
        "revision": revision,
        "skills": skills,
    }
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def _zip(files: dict[str, bytes], manifest: bytes) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        members = {**files, "manifest.json": manifest}
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, members[name])
    return output.getvalue()


def _write_once(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(
                f"Refusing to overwrite different release artifact: {path}"
            )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def validate_archive(
    root: Path, archive_path: Path, expected_revision: str | None = None
) -> None:
    version = read_corpus_version(root / "pyproject.toml")
    source = _source_files(root)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Corpus archive contains duplicate paths")
            if any(
                not name
                or name.startswith("/")
                or "\\" in name
                or ".." in PurePosixPath(name).parts
                for name in names
            ):
                raise ValueError("Corpus archive contains an unsafe path")
            manifest = json.loads(archive.read("manifest.json"))
            if not isinstance(manifest, dict) or set(manifest) != {
                "schema_version",
                "version",
                "repository",
                "revision",
                "skills",
            }:
                raise ValueError("Corpus archive manifest has unsupported fields")
            if (
                manifest["schema_version"] != 1
                or not isinstance(manifest["version"], str)
                or manifest["version"] != version
                or not isinstance(manifest["repository"], str)
                or not isinstance(manifest["revision"], str)
                or not isinstance(manifest["skills"], list)
                or len(manifest["skills"]) != len(SKILL_NAMES)
            ):
                raise ValueError("Corpus archive manifest version is not current")
            if manifest["repository"] != CORPUS_REPOSITORY:
                raise ValueError("Corpus archive manifest repository is incorrect")
            revision = _revision(root, expected_revision or manifest["revision"])
            if manifest["revision"] != revision:
                raise ValueError(
                    "Corpus archive revision does not match the requested source"
                )
            _assert_revision_sources(root, revision, source)
            listed: dict[str, bytes] = {}
            listed_names: set[str] = set()
            for skill in manifest["skills"]:
                if not isinstance(skill, dict) or set(skill) != {
                    "name",
                    "path",
                    "files",
                }:
                    raise ValueError(
                        "Corpus archive Skill entry has unsupported fields"
                    )
                name = skill["name"]
                path = skill["path"]
                files = skill["files"]
                if (
                    name not in SKILL_NAMES
                    or path != f"corpus/{name}"
                    or not isinstance(files, dict)
                ):
                    raise ValueError("Corpus archive Skill entry is invalid")
                if name in listed_names:
                    raise ValueError("Corpus archive lists a Skill more than once")
                listed_names.add(name)
                for relative, digest in files.items():
                    if (
                        not isinstance(relative, str)
                        or not relative
                        or PurePosixPath(relative).is_absolute()
                        or ".." in PurePosixPath(relative).parts
                        or not isinstance(digest, str)
                        or not re.fullmatch(r"[0-9a-f]{64}", digest)
                    ):
                        raise ValueError("Corpus archive file manifest is invalid")
                    archive_name = f"{path}/{relative}"
                    content = archive.read(archive_name)
                    if _sha256(content) != digest:
                        raise ValueError(
                            f"Corpus archive hash mismatch: {archive_name}"
                        )
                    listed[archive_name] = content
            if listed_names != SKILL_NAMES:
                raise ValueError("Corpus archive does not list exactly the six Skills")
            expected = {**source, "manifest.json": archive.read("manifest.json")}
            if set(names) != set(source) | {"manifest.json"}:
                raise ValueError(
                    "Corpus archive contains files outside the release contract"
                )
            if listed != {
                path: content
                for path, content in source.items()
                if path.startswith("corpus/")
            }:
                raise ValueError(
                    "Corpus archive manifest does not describe the source Skills"
                )
            for path, content in expected.items():
                if archive.read(path) != content:
                    raise ValueError(f"Corpus archive differs from source: {path}")
    except (KeyError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        raise ValueError(f"Invalid Corpus archive: {archive_path}") from error


def build(
    root: Path, output: Path, checksum: Path | None = None, revision: str | None = None
) -> tuple[Path, Path]:
    _assert_clean_source(root)
    version = read_corpus_version(root / "pyproject.toml")
    resolved_revision = _revision(root, revision)
    files = _source_files(root)
    _assert_revision_sources(root, resolved_revision, files)
    manifest = _manifest(version, resolved_revision, files)
    archive = _zip(files, manifest)
    checksum_path = checksum or output.with_name(output.name + ".sha256")
    checksum_content = f"{_sha256(archive)}  {output.name}\n".encode()
    _write_once(output, archive)
    _write_once(checksum_path, checksum_content)
    validate_archive(root, output, resolved_revision)
    return output, checksum_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checksum", type=Path)
    parser.add_argument("--revision")
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    output, checksum = build(args.root, args.output, args.checksum, args.revision)
    print(output)
    print(checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
