"""Build and verify packaged JSON Schemas for core SVC CLI output."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from svc_cli.output_schema import OUTPUT_SCHEMA_KEYS, generate_output_schema


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / "svc_cli" / "data" / "output-schemas"


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


def _git_show(ref: str, relative: str) -> bytes | None:
    completed = subprocess.run(
        ("git", "show", f"{ref}:{relative}"),
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    return completed.stdout if completed.returncode == 0 else None


def _changed_major_fragment(ref: str) -> bool:
    completed = subprocess.run(
        ("git", "diff", "--name-only", ref, "--", "changes/unreleased"),
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    for relative in completed.stdout.splitlines():
        path = ROOT / relative
        if not path.is_file():
            continue
        value: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        if (
            isinstance(value, dict)
            and value.get("component") == "cli"
            and value.get("kind") == "major"
        ):
            return True
    return False


def compare_ref(ref: str) -> list[str]:
    """Return compatibility failures relative to a Git ref."""

    changed_existing: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for key in OUTPUT_SCHEMA_KEYS:
        relative = f"svc_cli/data/output-schemas/{key}.json"
        previous_bytes = _git_show(ref, relative)
        if previous_bytes is None:
            continue
        current = generate_output_schema(key)
        previous = json.loads(previous_bytes)
        if previous != current:
            changed_existing.append((key, previous, current))
    if not changed_existing:
        return []

    failures: list[str] = []
    if not _changed_major_fragment(ref):
        failures.append(
            "output schema changed without a changed component=cli, kind=major "
            "fragment under changes/unreleased"
        )
    for key, previous, current in changed_existing:
        before = previous.get("x-svc-result-schema-version")
        after = current.get("x-svc-result-schema-version")
        if not isinstance(before, int) or not isinstance(after, int) or after <= before:
            failures.append(
                f"{key} output schema changed without advancing its result schema version"
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
    if args.compare_ref:
        failures = compare_ref(args.compare_ref)
        for failure in failures:
            print(failure)
        if failures:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
