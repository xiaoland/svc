from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAGMENT_RE = re.compile(
    r"^(?P<name>[a-z0-9][a-z0-9-]*)\.(?P<impact>major|minor|patch)\.md$"
)
VERSION_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
IMPACT_ORDER = {"patch": 0, "minor": 1, "major": 2}
RELEASE_BUNDLE_SCHEMA_VERSION = 1
RELEASE_BUNDLE_MANIFEST = "svc-release-manifest.json"
RELEASE_BUNDLE_CHECKER = "release-check.py"
RELEASE_BUNDLE_METADATA = "svc-release-metadata.json"
RELEASE_BUNDLE_NOTES = "RELEASE_NOTES.md"
RELEASE_BUNDLE_CHECKSUMS = "SHA256SUMS"
ZERO_KNOWN_ADOPTION_EXCEPTION = {
    "kind": "zero-known-adopted-consumers",
    "from_version": "10.0.0",
    "to_version": "10.0.1",
}


class ReleaseError(ValueError):
    pass


@dataclass(frozen=True)
class Fragment:
    path: Path
    impact: str
    summary: str


def parse_version(value: str) -> tuple[int, int, int]:
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise ReleaseError(f"Version must be stable SemVer: {value}")
    return tuple(int(match.group(name)) for name in ("major", "minor", "patch"))


def release_tag(version: str) -> str:
    parse_version(version)
    return f"v{version}"


def tag_version(tag: str) -> str:
    if not tag.startswith("v"):
        raise ReleaseError(f"Release tag must start with v: {tag}")
    version = tag.removeprefix("v")
    parse_version(version)
    if tag != release_tag(version):
        raise ReleaseError(f"Release tag must be canonical SemVer: {tag}")
    return version


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def distribution_files(directory: Path) -> list[Path]:
    files = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and (path.name.endswith(".whl") or path.name.endswith(".tar.gz"))
    )
    if not files:
        raise ReleaseError(f"No wheel or sdist in {directory}")
    return files


def bump(value: str, impact: str) -> str:
    major, minor, patch = parse_version(value)
    if impact == "major":
        return f"{major + 1}.0.0"
    if impact == "minor":
        return f"{major}.{minor + 1}.0"
    if impact == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ReleaseError(f"Unknown impact: {impact}")


def bump_impact(previous: str, current: str) -> str:
    before = parse_version(previous)
    after = parse_version(current)
    if after <= before:
        raise ReleaseError(f"Release version must increase: {previous} -> {current}")
    if after[0] > before[0] and after[1:] == (0, 0):
        return "major"
    if after[0] == before[0] and after[1] > before[1] and after[2] == 0:
        return "minor"
    if after[:2] == before[:2] and after[2] > before[2]:
        return "patch"
    raise ReleaseError(f"Version is not a single Behavioral SemVer bump: {previous} -> {current}")


def verify_version_exception(
    previous: str,
    current: str,
    impact: str,
    version_exception: object | None,
) -> None:
    """Verify SVC's single, immutable MAJOR-version exception."""
    if impact != "major":
        raise ReleaseError("Version exception is valid only for a MAJOR behavioral impact")
    if not isinstance(version_exception, dict):
        raise ReleaseError("MAJOR version exception requires a complete declaration")
    required = {
        *ZERO_KNOWN_ADOPTION_EXCEPTION,
        "one_time",
        "owner_assertion",
        "reason",
    }
    if set(version_exception) != required:
        raise ReleaseError("MAJOR version exception has missing or unknown fields")
    if any(
        version_exception[field] != value
        for field, value in ZERO_KNOWN_ADOPTION_EXCEPTION.items()
    ):
        raise ReleaseError("Only the 10.0.0 -> 10.0.1 zero-known-adopted-consumers exception is allowed")
    if version_exception["one_time"] is not True:
        raise ReleaseError("MAJOR version exception must declare one_time: true")
    for field in ("owner_assertion", "reason"):
        if not isinstance(version_exception[field], str) or not version_exception[field].strip():
            raise ReleaseError(f"MAJOR version exception requires a non-empty {field}")
    if (previous, current) != (
        ZERO_KNOWN_ADOPTION_EXCEPTION["from_version"],
        ZERO_KNOWN_ADOPTION_EXCEPTION["to_version"],
    ):
        raise ReleaseError("MAJOR version exception does not match the release versions")


def fragments(root: Path = ROOT) -> list[Fragment]:
    directory = root / "changes"
    found: list[Fragment] = []
    if not directory.exists():
        return found
    for path in sorted(directory.iterdir()):
        if path.name in {".gitkeep", "README.md"}:
            continue
        if not path.is_file():
            raise ReleaseError(f"Unexpected entry in changes/: {path.name}")
        match = FRAGMENT_RE.fullmatch(path.name)
        if not match:
            raise ReleaseError(f"Invalid change fragment name: {path.name}")
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            raise ReleaseError(f"Empty change fragment: {path.name}")
        summary = next(
            (
                line.lstrip("#-* ").strip()
                for line in content.splitlines()
                if line.strip()
            ),
            "",
        )
        if not summary:
            raise ReleaseError(f"Change fragment has no summary: {path.name}")
        found.append(Fragment(path, match.group("impact"), summary))
    return found


def maximum_impact(items: list[Fragment]) -> str:
    if not items:
        raise ReleaseError("No unconsumed change fragments")
    return max((item.impact for item in items), key=IMPACT_ORDER.__getitem__)


def load_manifest(root: Path = ROOT) -> dict[str, object]:
    manifest = json.loads((root / "src/manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 2:
        raise ReleaseError("src/manifest.json must use release metadata schema_version 2")
    return manifest


def project_version(root: Path = ROOT) -> str:
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    project = text.split("[project]", 1)[1].split("\n[", 1)[0]
    match = re.search(r'^version = "([^"]+)"$', project, flags=re.MULTILINE)
    if not match:
        raise ReleaseError("Missing [project] version")
    parse_version(match.group(1))
    return match.group(1)


def git_tags(root: Path = ROOT) -> list[str]:
    result = subprocess.run(
        ["git", "tag", "--list", "v[0-9]*"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    versions = []
    for tag in result.stdout.splitlines():
        try:
            parse_version(tag.removeprefix("v"))
        except ReleaseError:
            continue
        versions.append(tag.removeprefix("v"))
    return sorted(versions, key=parse_version)


def git_commit(reference: str, root: Path = ROOT) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", f"{reference}^{{commit}}"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        raise ReleaseError(f"Git reference does not resolve to a commit: {reference}") from error
    commit = result.stdout.strip()
    if not COMMIT_RE.fullmatch(commit):
        raise ReleaseError(f"Git reference did not resolve to a full commit SHA: {reference}")
    return commit


def tag_commit(tag: str, root: Path = ROOT) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        return None
    commit = result.stdout.strip()
    if not COMMIT_RE.fullmatch(commit):
        raise ReleaseError(f"Release tag did not resolve to a full commit SHA: {tag}")
    return commit


def release_plan(root: Path = ROOT) -> dict[str, object]:
    items = fragments(root)
    impact = maximum_impact(items)
    manifest = load_manifest(root)
    tags = git_tags(root)
    base = tags[-1] if tags else str(manifest["previous_version"])
    declared = str(manifest["svc_version"])
    calculated = bump(base, impact)
    release_policy = manifest.get("release_policy")
    has_version_exception = (
        isinstance(release_policy, dict) and "version_exception" in release_policy
    )
    version_exception = release_policy.get("version_exception") if has_version_exception else None
    if has_version_exception:
        if declared != base:
            raise ReleaseError("Version exception must be staged without pre-bumping release metadata")
        target = str(
            version_exception.get("to_version")
            if isinstance(version_exception, dict)
            else ""
        )
        verify_version_exception(base, target, impact, version_exception)
    else:
        target = declared if parse_version(declared) > parse_version(base) else calculated
    if target != calculated:
        if not has_version_exception:
            raise ReleaseError(
                f"Declared {target} does not match {impact} bump from {base}: {calculated}"
            )
    return {
        "base_version": base,
        "target_version": target,
        "impact": impact,
        "fragments": [item.path.name for item in items],
        "reasons": [item.summary for item in items],
    }


def verify_migration(
    previous: str,
    current: str,
    impact: str,
    migration_policy: object | None = None,
    root: Path = ROOT,
) -> None:
    if impact != "major":
        return
    if not isinstance(migration_policy, dict):
        raise ReleaseError("MAJOR release requires a packaged migration guide or explicit non-applicability")
    status = migration_policy.get("status")
    if status == "not-applicable":
        reason = migration_policy.get("reason")
        if isinstance(reason, str) and reason.strip():
            return
        raise ReleaseError("MAJOR migration non-applicability requires a concrete reason")
    if status == "guide":
        path = migration_policy.get("path")
        if not isinstance(path, str) or not path.startswith("migrations/") or not path.endswith(".md"):
            raise ReleaseError("MAJOR migration guide must name a Markdown path under src/migrations/")
        source = root / "src" / path
        if not source.is_file():
            raise ReleaseError(f"MAJOR migration guide does not exist: {path}")
        return
    raise ReleaseError("MAJOR migration policy must be guide or not-applicable")


def check(root: Path = ROOT) -> dict[str, object]:
    plan = release_plan(root)
    manifest = load_manifest(root)
    if project_version(root) != manifest["svc_version"]:
        raise ReleaseError("pyproject.toml and src/manifest.json versions disagree")
    declared = str(manifest["svc_version"])
    base = str(plan["base_version"])
    if declared == base:
        release_policy = manifest.get("release_policy", {})
        migration_policy = (
            release_policy.get("migration")
            if isinstance(release_policy, dict)
            else None
        )
        verify_migration(
            base,
            str(plan["target_version"]),
            str(plan["impact"]),
            migration_policy,
            root,
        )
        return plan
    if plan["target_version"] != manifest["svc_version"]:
        raise ReleaseError("Calculated target and release manifest version disagree")
    impact = manifest.get("behavioral_impact", {})
    if not isinstance(impact, dict) or impact.get("level") != plan["impact"]:
        raise ReleaseError("Release manifest impact does not match change fragments")
    if (
        bump_impact(str(manifest["previous_version"]), str(manifest["svc_version"]))
        != plan["impact"]
    ):
        raise ReleaseError("Release manifest versions violate Behavioral SemVer")
    verify_migration(
        str(manifest["previous_version"]),
        str(manifest["svc_version"]),
        str(plan["impact"]),
        impact.get("migration"),
        root,
    )
    return plan


def check_ci(root: Path = ROOT) -> dict[str, object]:
    return check(root) if fragments(root) else verify_prepared(root)


def check_pr(base: str, release_none: bool, root: Path = ROOT) -> dict[str, object]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    changed = {line for line in result.stdout.splitlines() if line}
    changed_fragments = {
        path
        for path in changed
        if path.startswith("changes/") and (root / path).is_file()
    }
    if changed_fragments:
        return check(root)
    if {"CHANGELOG.md", "src/manifest.json"} <= changed:
        return verify_prepared(root)
    if release_none:
        return {"release": "none", "changed": sorted(changed)}
    raise ReleaseError("Pull request requires a change fragment or explicit release:none decision")


def replace_project_version(path: Path, version: str) -> None:
    text = path.read_text(encoding="utf-8")
    head, project = text.split("[project]", 1)
    project_body, tail = project.split("\n[", 1)
    project_body, count = re.subn(
        r'^version = "[^"]+"$',
        f'version = "{version}"',
        project_body,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise ReleaseError("Could not update [project] version")
    path.write_text(head + "[project]" + project_body + "\n[" + tail, encoding="utf-8")


def prepare(root: Path = ROOT) -> dict[str, object]:
    plan = release_plan(root)
    manifest_path = root / "src/manifest.json"
    manifest = load_manifest(root)
    base_version = str(plan["base_version"])
    declared_version = str(manifest["svc_version"])
    predeclared_release = parse_version(declared_version) > parse_version(base_version)
    existing_impact = manifest.get("behavioral_impact")
    staged_policy = manifest.pop("release_policy", None)
    has_version_exception = (
        isinstance(staged_policy, dict) and "version_exception" in staged_policy
    )
    version_exception = staged_policy.get("version_exception") if has_version_exception else None
    manifest["previous_version"] = plan["base_version"]
    manifest["svc_version"] = plan["target_version"]
    impact_data: dict[str, object] = {"level": plan["impact"], "reasons": plan["reasons"]}
    if plan["impact"] == "major":
        if predeclared_release:
            if staged_policy is not None:
                raise ReleaseError("A predeclared MAJOR release must declare migration in behavioral_impact, not release_policy")
            migration_policy = (
                existing_impact.get("migration") if isinstance(existing_impact, dict) else None
            )
        else:
            migration_policy = (
                staged_policy.get("migration") if isinstance(staged_policy, dict) else None
            )
        verify_migration(
            base_version,
            str(plan["target_version"]),
            "major",
            migration_policy,
            root,
        )
        impact_data["migration"] = migration_policy
        if has_version_exception:
            verify_version_exception(
                base_version,
                str(plan["target_version"]),
                "major",
                version_exception,
            )
            impact_data["version_exception"] = version_exception
    else:
        if staged_policy is not None:
            raise ReleaseError("release_policy is valid only while staging a pending MAJOR release")
        impact_data["migration"] = {
            "status": "not-applicable",
            "reason": f"{str(plan['impact']).upper()} releases do not require consumer migration guidance.",
        }
    manifest["behavioral_impact"] = impact_data
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    replace_project_version(root / "pyproject.toml", str(plan["target_version"]))
    subprocess.run(
        [
            sys.executable,
            "-m",
            "towncrier",
            "build",
            "--yes",
            "--version",
            str(plan["target_version"]),
        ],
        cwd=root,
        check=True,
    )
    changelog_path = root / "CHANGELOG.md"
    changelog = changelog_path.read_text(encoding="utf-8")
    link = (
        f'[{plan["target_version"]}]: '
        f'https://github.com/xiaoland/svc/releases/tag/v{plan["target_version"]}'
    )
    if link not in changelog:
        changelog_path.write_text(
            changelog.rstrip() + "\n" + link + "\n", encoding="utf-8"
        )
    subprocess.run(["pdm", "lock", "-d", "-G", ":all"], cwd=root, check=True)
    verify_prepared(root)
    return plan


def verify_prepared(root: Path = ROOT) -> dict[str, object]:
    remaining = fragments(root)
    if remaining:
        raise ReleaseError("Prepared release still contains change fragments")
    manifest = load_manifest(root)
    if "release_policy" in manifest:
        raise ReleaseError("Prepared release metadata must not retain a staging release_policy")
    previous = str(manifest["previous_version"])
    current = str(manifest["svc_version"])
    if project_version(root) != current:
        raise ReleaseError("pyproject.toml and src/manifest.json versions disagree")
    impact_data = manifest.get("behavioral_impact", {})
    if not isinstance(impact_data, dict) or impact_data.get("level") not in IMPACT_ORDER:
        raise ReleaseError("Release manifest has no valid behavioral impact")
    impact = str(impact_data["level"])
    version_exception = impact_data.get("version_exception")
    if version_exception is None:
        if bump_impact(previous, current) != impact:
            raise ReleaseError("Prepared version violates Behavioral SemVer")
    else:
        verify_version_exception(previous, current, impact, version_exception)
    reasons = impact_data.get("reasons")
    if (
        not isinstance(reasons, list)
        or not reasons
        or not all(isinstance(reason, str) and reason.strip() for reason in reasons)
    ):
        raise ReleaseError("Release manifest requires non-empty behavioral reasons")
    verify_migration(previous, current, impact, impact_data.get("migration"), root)
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## [{current}]" not in changelog:
        raise ReleaseError(f"CHANGELOG.md has no {current} release section")
    release_link = f"[{current}]: https://github.com/xiaoland/svc/releases/tag/v{current}"
    if release_link not in changelog:
        raise ReleaseError(f"CHANGELOG.md has no canonical release link for {current}")
    return {"previous_version": previous, "version": current, "impact": impact}


def tag_plan(commit: str, root: Path = ROOT) -> dict[str, object]:
    """Classify one prepared merge commit for idempotent tag creation."""
    expected_commit = git_commit(commit, root)
    if git_commit("HEAD", root) != expected_commit:
        raise ReleaseError("Release tag source must be checked out at the requested commit")
    prepared = verify_prepared(root)
    version = str(prepared["version"])
    tag = release_tag(version)
    existing = tag_commit(tag, root)
    if existing is not None:
        if existing != expected_commit:
            raise ReleaseError(
                f"Release tag {tag} points to {existing}, not requested commit {expected_commit}"
            )
        return {
            "needed": False,
            "reason": "tag-already-created",
            "tag": tag,
            "version": version,
            "commit": expected_commit,
        }
    tags = git_tags(root)
    if tags and parse_version(version) <= parse_version(tags[-1]):
        raise ReleaseError("Prepared version is not newer than the latest release tag")
    return {"needed": True, "tag": tag, "version": version, "commit": expected_commit}


def verify_tag(tag: str, commit: str, root: Path = ROOT) -> dict[str, object]:
    """Bind a checked-out prepared source, its version tag, and one commit."""
    version = tag_version(tag)
    expected_commit = git_commit(commit, root)
    if git_commit("HEAD", root) != expected_commit:
        raise ReleaseError("Release source is not checked out at the requested tag commit")
    resolved_tag = tag_commit(tag, root)
    if resolved_tag is None:
        raise ReleaseError(f"Release tag does not exist: {tag}")
    if resolved_tag != expected_commit:
        raise ReleaseError(
            f"Release tag {tag} resolves to {resolved_tag}, not requested commit {expected_commit}"
        )
    prepared = verify_prepared(root)
    if str(prepared["version"]) != version:
        raise ReleaseError(
            f"Release tag {tag} does not match prepared package version {prepared['version']}"
        )
    return {"tag": tag, "version": version, "commit": expected_commit}


def _bundle_path(bundle_dir: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ReleaseError("Release bundle path must be a non-empty string")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != relative:
        raise ReleaseError(f"Release bundle path must be a safe POSIX relative path: {relative}")
    return bundle_dir / path


def _sorted_unique_strings(value: object, description: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ReleaseError(f"Release bundle {description} must be a non-empty string list")
    if value != sorted(set(value)):
        raise ReleaseError(f"Release bundle {description} must be sorted and unique")
    return value


def verify_release_bundle(
    bundle_dir: Path, tag: str | None = None
) -> dict[str, object]:
    """Validate a portable release bundle without consulting source checkout state."""
    manifest_path = bundle_dir / RELEASE_BUNDLE_MANIFEST
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseError(f"Could not read release bundle manifest: {manifest_path}") from error
    expected_fields = {
        "schema_version",
        "tag",
        "commit",
        "version",
        "distributions",
        "release_assets",
        "notes",
        "checker",
        "files",
        "checksum",
    }
    if not isinstance(payload, dict) or set(payload) != expected_fields:
        raise ReleaseError("Release bundle manifest has missing or unknown fields")
    if payload["schema_version"] != RELEASE_BUNDLE_SCHEMA_VERSION:
        raise ReleaseError("Release bundle manifest has an unsupported schema version")
    manifest_tag = payload["tag"]
    if not isinstance(manifest_tag, str):
        raise ReleaseError("Release bundle manifest tag must be a string")
    version = tag_version(manifest_tag)
    if payload["version"] != version:
        raise ReleaseError("Release bundle manifest tag and version disagree")
    if tag is not None:
        tag_version(tag)
        if tag != manifest_tag:
            raise ReleaseError(f"Release bundle is for {manifest_tag}, not requested tag {tag}")
    commit = payload["commit"]
    if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
        raise ReleaseError("Release bundle manifest commit must be a full SHA-1")
    distributions = _sorted_unique_strings(payload["distributions"], "distributions")
    release_assets = _sorted_unique_strings(payload["release_assets"], "release assets")
    notes = payload["notes"]
    checker = payload["checker"]
    _bundle_path(bundle_dir, notes)
    _bundle_path(bundle_dir, checker)
    if not isinstance(notes, str) or notes != RELEASE_BUNDLE_NOTES:
        raise ReleaseError("Release bundle notes path is invalid")
    if not isinstance(checker, str) or checker != RELEASE_BUNDLE_CHECKER:
        raise ReleaseError("Release bundle checker path is invalid")
    raw_files = payload["files"]
    if not isinstance(raw_files, dict) or not raw_files:
        raise ReleaseError("Release bundle manifest files must be a non-empty object")
    files: dict[str, str] = {}
    for relative, digest in raw_files.items():
        _bundle_path(bundle_dir, relative)
        if not isinstance(relative, str) or not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise ReleaseError("Release bundle manifest contains an invalid file digest")
        files[relative] = digest
    if set(files) != set(distributions) | {RELEASE_BUNDLE_METADATA, notes, checker}:
        raise ReleaseError("Release bundle manifest file set is incomplete or has unknown entries")
    if any(
        not relative.startswith("python/")
        or not (relative.endswith(".whl") or relative.endswith(".tar.gz"))
        for relative in distributions
    ):
        raise ReleaseError("Release bundle distributions must be wheel or sdist files under python/")
    checksum = payload["checksum"]
    if not isinstance(checksum, dict) or set(checksum) != {"path", "sha256"}:
        raise ReleaseError("Release bundle checksum declaration is invalid")
    checksum_path = checksum["path"]
    checksum_digest = checksum["sha256"]
    _bundle_path(bundle_dir, checksum_path)
    if (
        checksum_path != RELEASE_BUNDLE_CHECKSUMS
        or not isinstance(checksum_digest, str)
        or not SHA256_RE.fullmatch(checksum_digest)
    ):
        raise ReleaseError("Release bundle checksum declaration is invalid")
    expected_assets = sorted(
        set(distributions)
        | {RELEASE_BUNDLE_METADATA, checksum_path, RELEASE_BUNDLE_MANIFEST}
    )
    if release_assets != expected_assets:
        raise ReleaseError("Release bundle release asset set is incomplete or has unknown entries")
    expected_files = set(files) | {checksum_path, RELEASE_BUNDLE_MANIFEST}
    actual_files = {
        path.relative_to(bundle_dir).as_posix()
        for path in bundle_dir.rglob("*")
        if path.is_file()
    }
    if actual_files != expected_files:
        raise ReleaseError("Release bundle has missing or unexpected files")
    for relative, digest in files.items():
        if sha256_file(_bundle_path(bundle_dir, relative)) != digest:
            raise ReleaseError(f"Release bundle digest differs: {relative}")
    checksum_file = _bundle_path(bundle_dir, checksum_path)
    if sha256_file(checksum_file) != checksum_digest:
        raise ReleaseError("Release bundle checksum file digest differs")
    expected_checksum_content = "".join(
        f"{files[relative]}  {relative}\n" for relative in sorted(files)
    )
    if checksum_file.read_text(encoding="utf-8") != expected_checksum_content:
        raise ReleaseError("Release bundle checksum file does not match the manifest")
    return {
        "tag": manifest_tag,
        "commit": commit,
        "version": version,
        "distributions": distributions,
        "assets": release_assets,
        "notes": notes,
        "files": files,
    }


def create_release_bundle(
    tag: str,
    commit: str,
    dist_dir: Path,
    bundle_dir: Path,
    root: Path = ROOT,
) -> dict[str, object]:
    """Create one manifest-bound release bundle from verified tagged source."""
    release = verify_tag(tag, commit, root)
    source_distributions = distribution_files(dist_dir)
    if bundle_dir.exists() and any(bundle_dir.iterdir()):
        raise ReleaseError(f"Release bundle directory must be empty: {bundle_dir}")
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle_distributions = bundle_dir / "python"
    bundle_distributions.mkdir()
    distribution_paths: list[str] = []
    for source in source_distributions:
        destination = bundle_distributions / source.name
        shutil.copy2(source, destination)
        distribution_paths.append(destination.relative_to(bundle_dir).as_posix())
    metadata_path = bundle_dir / RELEASE_BUNDLE_METADATA
    shutil.copy2(root / "src/manifest.json", metadata_path)
    notes_path = bundle_dir / RELEASE_BUNDLE_NOTES
    notes_path.write_text(str(release_notes(root)["notes"]) + "\n", encoding="utf-8")
    checker_path = bundle_dir / RELEASE_BUNDLE_CHECKER
    shutil.copy2(Path(__file__).resolve(), checker_path)
    files = {
        relative: sha256_file(_bundle_path(bundle_dir, relative))
        for relative in sorted(
            [*distribution_paths, RELEASE_BUNDLE_METADATA, RELEASE_BUNDLE_NOTES, RELEASE_BUNDLE_CHECKER]
        )
    }
    checksum_path = bundle_dir / RELEASE_BUNDLE_CHECKSUMS
    checksum_path.write_text(
        "".join(f"{files[relative]}  {relative}\n" for relative in sorted(files)),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": RELEASE_BUNDLE_SCHEMA_VERSION,
        "tag": release["tag"],
        "commit": release["commit"],
        "version": release["version"],
        "distributions": sorted(distribution_paths),
        "release_assets": sorted(
            [
                *distribution_paths,
                RELEASE_BUNDLE_METADATA,
                RELEASE_BUNDLE_CHECKSUMS,
                RELEASE_BUNDLE_MANIFEST,
            ]
        ),
        "notes": RELEASE_BUNDLE_NOTES,
        "checker": RELEASE_BUNDLE_CHECKER,
        "files": files,
        "checksum": {
            "path": RELEASE_BUNDLE_CHECKSUMS,
            "sha256": sha256_file(checksum_path),
        },
    }
    (bundle_dir / RELEASE_BUNDLE_MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return verify_release_bundle(bundle_dir, tag)


def _pypi_file_plan(version: str, local: dict[str, str]) -> dict[str, object]:
    url = f"https://pypi.org/pypi/sustainable-vibe-coding/{version}/json"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            remote_data = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {"needed": True, "version": version, "expected": sorted(local)}
        raise ReleaseError(f"PyPI query failed: HTTP {error.code}") from error
    if not isinstance(remote_data, dict) or not isinstance(remote_data.get("urls", []), list):
        raise ReleaseError("PyPI query returned an invalid release response")
    remote = {}
    for item in remote_data.get("urls", []):
        if not isinstance(item, dict):
            raise ReleaseError("PyPI query returned an invalid release file")
        filename = item.get("filename")
        digests = item.get("digests")
        digest = digests.get("sha256") if isinstance(digests, dict) else None
        if not isinstance(filename, str) or not isinstance(digest, str):
            raise ReleaseError("PyPI query returned an invalid release file")
        remote[filename] = digest
    missing = sorted(set(local) - set(remote))
    mismatched = sorted(
        name for name in local.keys() & remote.keys() if local[name] != remote[name]
    )
    if missing or mismatched:
        raise ReleaseError(
            f"PyPI release is partial or differs: missing={missing}, "
            f"mismatched={mismatched}"
        )
    return {"needed": False, "version": version, "verified": sorted(local)}


def pypi_plan(dist_dir: Path, root: Path = ROOT) -> dict[str, object]:
    version = str(load_manifest(root)["svc_version"])
    local = {path.name: sha256_file(path) for path in distribution_files(dist_dir)}
    return _pypi_file_plan(version, local)


def pypi_bundle_plan(bundle_dir: Path, tag: str) -> dict[str, object]:
    bundle = verify_release_bundle(bundle_dir, tag)
    files = bundle["files"]
    distributions = bundle["distributions"]
    if not isinstance(files, dict) or not isinstance(distributions, list):
        raise ReleaseError("Release bundle verification returned an invalid file plan")
    local = {Path(relative).name: str(files[relative]) for relative in distributions}
    if len(local) != len(distributions):
        raise ReleaseError("Release bundle has duplicate distribution filenames")
    plan = _pypi_file_plan(str(bundle["version"]), local)
    return {**plan, "tag": bundle["tag"]}


def release_notes(root: Path = ROOT) -> dict[str, object]:
    version = str(load_manifest(root)["svc_version"])
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(
        rf"^## \[{re.escape(version)}\].*?(?=^## \[|\Z)",
        changelog,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise ReleaseError(f"CHANGELOG.md has no {version} release notes")
    return {"version": version, "notes": match.group(0).strip()}


def required_option(value: str | Path | None, option: str) -> str | Path:
    if value is None or value == "":
        raise ReleaseError(f"{option} is required")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plan and verify SVC Behavioral SemVer releases."
    )
    parser.add_argument(
        "command",
        choices=(
            "check",
            "check-ci",
            "check-pr",
            "plan",
            "prepare",
            "verify-prepared",
            "tag-plan",
            "verify-tag",
            "bundle",
            "verify-bundle",
            "pypi-plan",
            "notes",
        ),
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    parser.add_argument("--bundle-dir", type=Path)
    parser.add_argument("--tag")
    parser.add_argument("--commit")
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--release-none", action="store_true")
    args = parser.parse_args(argv)
    try:
        commands = {
            "check": check,
            "check-ci": check_ci,
            "check-pr": lambda: check_pr(args.base, args.release_none),
            "plan": release_plan,
            "prepare": prepare,
            "verify-prepared": verify_prepared,
            "tag-plan": lambda: tag_plan(
                str(required_option(args.commit, "--commit"))
            ),
            "verify-tag": lambda: verify_tag(
                str(required_option(args.tag, "--tag")),
                str(required_option(args.commit, "--commit")),
            ),
            "bundle": lambda: create_release_bundle(
                str(required_option(args.tag, "--tag")),
                str(required_option(args.commit, "--commit")),
                args.dist_dir,
                Path(required_option(args.bundle_dir, "--bundle-dir")),
            ),
            "verify-bundle": lambda: verify_release_bundle(
                Path(required_option(args.bundle_dir, "--bundle-dir")),
                str(required_option(args.tag, "--tag")),
            ),
            "pypi-plan": lambda: (
                pypi_bundle_plan(
                    Path(required_option(args.bundle_dir, "--bundle-dir")),
                    str(required_option(args.tag, "--tag")),
                )
                if args.bundle_dir is not None
                else pypi_plan(args.dist_dir)
            ),
            "notes": release_notes,
        }
        result = commands[args.command]()
    except (OSError, ReleaseError, subprocess.CalledProcessError) as error:
        print(f"release: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=None if args.json else 2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
