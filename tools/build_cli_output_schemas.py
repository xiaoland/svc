"""Build and verify packaged JSON Schemas for core SVC CLI output."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tomllib
from pathlib import Path

from svc_cli.output_schema import OUTPUT_SCHEMA_KEYS, generate_output_schema


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / "cli" / "src" / "svc_cli" / "data" / "output-schemas"
SCHEMA_REPOSITORY_PREFIX = "cli/src/svc_cli/data/output-schemas"
LEGACY_SCHEMA_REPOSITORY_PREFIX = "svc_cli/src/svc_cli/data/output-schemas"


def _encoded(key: str) -> bytes:
    return (
        json.dumps(
            generate_output_schema(key),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def build(*, check: bool) -> list[str]:
    changed: list[str] = []
    for key in OUTPUT_SCHEMA_KEYS:
        path = SCHEMA_ROOT / f"{key}.json"
        expected = _encoded(key)
        actual = path.read_bytes() if path.is_file() else None
        if actual == expected:
            continue
        changed.append(path.relative_to(ROOT).as_posix())
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
    return changed


def _package_version() -> tuple[int, int, int]:
    raw = (ROOT / "cli/pyproject.toml").read_bytes()
    version = tomllib.loads(raw.decode())["project"].get("version")
    if not isinstance(version, str):
        raise ValueError("package version is not static")
    parts = version.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise ValueError(f"invalid package version: {version}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def _schema_at_ref(ref: str, key: str) -> dict[str, object] | None:
    for prefix in (SCHEMA_REPOSITORY_PREFIX, LEGACY_SCHEMA_REPOSITORY_PREFIX):
        previous = subprocess.run(
            ("git", "show", f"{ref}:{prefix}/{key}.json"),
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        if previous.returncode == 0:
            return json.loads(previous.stdout)
    return None


def _latest_cli_release() -> tuple[str, tuple[int, int, int]] | None:
    tags = subprocess.run(
        ("git", "tag", "--list", "v[0-9]*", "cli-v[0-9]*"),
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout.splitlines()
    releases = []
    for tag in tags:
        match = re.fullmatch(
            r"(?:cli-)?v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", tag
        )
        if match:
            releases.append((tag, (int(match[1]), int(match[2]), int(match[3]))))
    return max(releases, key=lambda release: release[1]) if releases else None


def compare_ref(ref: str) -> list[str]:
    failures = []
    result_schema_advanced = False
    for key in OUTPUT_SCHEMA_KEYS:
        before = _schema_at_ref(ref, key)
        if before is None:
            continue
        after = generate_output_schema(key)
        if before == after:
            continue
        old_version = before.get("x-svc-result-schema-version")
        new_version = after.get("x-svc-result-schema-version")
        if (
            not isinstance(old_version, int)
            or not isinstance(new_version, int)
            or new_version <= old_version
        ):
            failures.append(
                f"{key} output changed without advancing x-svc-result-schema-version"
            )
        else:
            result_schema_advanced = True
    published = _latest_cli_release() if result_schema_advanced else None
    if published is not None and _package_version()[0] <= published[1][0]:
        # A release job may compare the tagged target with an older branch baseline.
        # Only changes beyond the published schemas spend a new package major.
        if any(
            _schema_at_ref(published[0], key) != generate_output_schema(key)
            for key in OUTPUT_SCHEMA_KEYS
        ):
            failures.append(
                "result schema advancement requires a package major advancement"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--compare-ref")
    args = parser.parse_args()

    changed = build(check=args.check)
    if args.check and changed:
        for path in changed:
            print(f"outdated generated output schema: {path}")
        return 1
    compare = args.compare_ref or os.environ.get("SVC_BASE_REF")
    if compare:
        failures = compare_ref(compare)
        for failure in failures:
            print(failure)
        if failures:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
