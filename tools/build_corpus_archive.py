"""Build and validate the reproducible Corpus Skills release archive."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import zipfile
from pathlib import Path

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


def _zip(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    return output.getvalue()


def _artifacts(
    version: str, revision: str, source: dict[str, bytes]
) -> dict[str, bytes]:
    artifacts: dict[str, bytes] = {}
    entries = []
    for name in sorted(SKILL_NAMES):
        prefix = f"corpus/{name}/"
        files = {
            path.removeprefix("corpus/"): content
            for path, content in source.items()
            if path.startswith(prefix)
        }
        filename = f"{name}-{version}.zip"
        raw = _zip(files)
        artifacts[filename] = raw
        entries.append(
            {
                "name": name,
                "path": name,
                "files": {
                    path.removeprefix(f"{name}/"): _sha256(content)
                    for path, content in sorted(files.items())
                },
                "archive": filename,
                "archive_sha256": _sha256(raw),
            }
        )
    catalog = {
        "schema_version": 2,
        "version": version,
        "repository": CORPUS_REPOSITORY,
        "revision": revision,
        "skills": entries,
    }
    artifacts[f"svc-skills-{version}.json"] = (
        json.dumps(catalog, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    for name, raw in tuple(artifacts.items()):
        artifacts[f"{name}.sha256"] = f"{_sha256(raw)}  {name}\n".encode()
    return artifacts


def _write_once(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(
                f"Refusing to overwrite different release artifact: {path}"
            )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def validate_artifacts(
    root: Path, directory: Path, expected_revision: str | None = None
) -> None:
    version = read_corpus_version(root / "pyproject.toml")
    catalog_path = directory / f"svc-skills-{version}.json"
    try:
        catalog = json.loads(catalog_path.read_bytes())
        revision = _revision(root, expected_revision or catalog["revision"])
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid Skills release catalog: {catalog_path}") from error
    source = _source_files(root)
    _assert_revision_sources(root, revision, source)
    expected = _artifacts(version, revision, source)
    if {path.name for path in directory.iterdir()} != set(expected):
        raise ValueError(
            "Release directory must contain exactly six Skill ZIPs, a catalog, and their checksums"
        )
    for filename, raw in expected.items():
        if (directory / filename).read_bytes() != raw:
            raise ValueError(
                f"Release artifact differs from the source contract: {filename}"
            )


def build(root: Path, output: Path, revision: str | None = None) -> tuple[Path, ...]:
    """Build only standalone Skill ZIPs and their shared provenance catalog."""
    _assert_clean_source(root)
    version = read_corpus_version(root / "pyproject.toml")
    resolved_revision = _revision(root, revision)
    source = _source_files(root)
    _assert_revision_sources(root, resolved_revision, source)
    artifacts = _artifacts(version, resolved_revision, source)
    for filename, raw in artifacts.items():
        _write_once(output / filename, raw)
    validate_artifacts(root, output, resolved_revision)
    return tuple(output / filename for filename in artifacts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Dedicated release artifact directory",
    )
    parser.add_argument("--revision")
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    for path in build(args.root, args.output_dir, args.revision):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
