"""CLI release compatibility exercised against real Git history and package files."""

import json
import subprocess
from pathlib import Path

import pytest

from svc_cli.output_schema import OUTPUT_SCHEMA_KEYS, generate_output_schema
from tools import build_cli_output_schemas as schemas


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True, stderr=subprocess.DEVNULL
    ).strip()


@pytest.mark.parametrize(
    "package_major,published_major,published_matches,advance_schema,accepted",
    [
        (15, 14, False, True, True),
        (15, 15, False, True, False),
        (15, 15, True, True, True),
        (15, 14, False, False, False),
    ],
    ids=[
        "draft-evolution",
        "published-major-reuse",
        "tagged-target",
        "unchanged-schema-version",
    ],
)
def test_schema_release_policy_uses_published_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    package_major: int,
    published_major: int,
    published_matches: bool,
    advance_schema: bool,
    accepted: bool,
) -> None:
    git(tmp_path, "init", "-q")
    current = {key: generate_output_schema(key) for key in OUTPUT_SCHEMA_KEYS}
    schema_dir = tmp_path / "cli/src/svc_cli/data/output-schemas"
    schema_dir.mkdir(parents=True)
    for key, value in current.items():
        prior = json.loads(json.dumps(value))
        if key == "init":
            prior["$defs"]["InitPlanOutput"]["properties"]["plan_digest"] = {
                "type": "integer"
            }
            if advance_schema:
                prior["x-svc-result-schema-version"] -= 1
        (schema_dir / f"{key}.json").write_text(json.dumps(prior))
    package = tmp_path / "cli/pyproject.toml"
    package.write_text('[project]\nversion = "15.0.0"\n')
    git(tmp_path, "add", ".")
    git(
        tmp_path,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "Unpublished baseline",
    )
    baseline = git(tmp_path, "rev-parse", "HEAD")
    # Numeric ordering, legacy tag names, and rejected release streams are inputs,
    # not substitutions for the implementation's release-selection function.
    for tag in ("v14.0.0", "cli-v14.9.0", "cli-v14.10.0"):
        git(tmp_path, "tag", tag)
    if published_matches:
        for key, value in current.items():
            (schema_dir / f"{key}.json").write_text(json.dumps(value))
        git(tmp_path, "add", ".")
        git(
            tmp_path,
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "Published target",
        )
    git(tmp_path, "tag", f"cli-v{published_major}.20.0")
    for tag in ("corpus-v99.0.0", "cli-v16.0.0-rc1"):
        git(tmp_path, "tag", tag)
    package.write_text(f'[project]\nversion = "{package_major}.0.0"\n')
    monkeypatch.setattr(schemas, "ROOT", tmp_path)

    assert bool(schemas.compare_ref(baseline)) is not accepted
