from __future__ import annotations

from pathlib import Path

import pytest
from svc_cli.catalog import parse_version_index
from tools.build_release_projections import (
    apply_projection,
    build_release_projections,
    read_fragment,
    validate_corpus_change,
)


def _fragment(
    component: str,
    migration: str,
    *,
    kind: str = "patch",
    guidance: str = "",
) -> str:
    return f"""kind: {kind}
component: {component}
body: A release fact.
custom:
  Migration: {migration}
  FromSchema: ""
  ToSchema: ""
  Guidance: |-
{chr(10).join(f"    {line}" for line in guidance.splitlines())}
time: 2026-08-08T00:00:00Z
"""


def test_release_projection_preserves_static_migration_index(tmp_path: Path) -> None:
    unreleased = tmp_path / "changes/unreleased"
    unreleased.mkdir(parents=True)
    (unreleased / "corpus.yaml").write_text(
        _fragment("corpus", "not-required"),
        encoding="utf-8",
    )
    migration_index = tmp_path / "src/migrations/index.md"
    migration_index.parent.mkdir(parents=True)
    migration_index.write_text("# Migration Index\n", encoding="utf-8")

    apply_projection(tmp_path, check=False)
    apply_projection(tmp_path, check=True)

    assert migration_index.read_text(encoding="utf-8") == "# Migration Index\n"


def test_cli_only_package_release_does_not_advance_corpus_version(
    tmp_path: Path,
) -> None:
    corpus = tmp_path / "changes/fragments/v10.0.2/corpus-release.yaml"
    corpus.parent.mkdir(parents=True)
    corpus.write_text(_fragment("corpus", "not-required"), encoding="utf-8")
    cli = tmp_path / "changes/fragments/v10.0.3/cli-only.yaml"
    cli.parent.mkdir(parents=True)
    cli.write_text(_fragment("cli", "not-applicable"), encoding="utf-8")
    (tmp_path / "changes/unreleased").mkdir(parents=True)

    index = parse_version_index(build_release_projections(tmp_path).version_index)

    assert index.corpus_version == "10.0.2"
    assert len(index.releases) == 1


def test_fragment_validation_rejects_missing_corpus_migration_disposition(
    tmp_path: Path,
) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text(
        _fragment("corpus", "not-applicable"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="migration disposition"):
        read_fragment(path, "unreleased/broken")


@pytest.mark.parametrize(
    ("changed", "base", "current", "error"),
    (
        (False, "12.0.0", "12.0.0", None),
        (True, "12.0.0", "12.0.1", None),
        (True, "12.0.0", "12.0.0", "changed without advancing"),
        (False, "12.0.0", "12.0.1", "advanced without a substantive"),
    ),
)
def test_corpus_change_and_release_advancement_must_agree(
    changed: bool, base: str, current: str, error: str | None
) -> None:
    if error:
        with pytest.raises(ValueError, match=error):
            validate_corpus_change(
                substantive_change=changed,
                base_version=base,
                current_version=current,
            )
        return
    validate_corpus_change(
        substantive_change=changed,
        base_version=base,
        current_version=current,
    )
