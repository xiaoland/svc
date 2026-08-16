from __future__ import annotations

import json
from pathlib import Path

import pytest

from svc_cli.config import parse_project_config
from svc_cli.errors import SvcError
from svc_cli.upgrade import apply_upgrade, plan_upgrade


def write_legacy(
    root: Path,
    *,
    baseline: str = "10.0.1",
    multiple_profiles: bool = False,
    local: bool = False,
) -> bytes:
    profiles: dict[str, object] = {
        "local": {
            "targets": {
                "web": {
                    "probe": {
                        "kind": "exec",
                        "argv": ["check", "${dev.profile}", "${dev.instance}"],
                    },
                    "provision": {"kind": "manual"},
                }
            }
        }
    }
    if multiple_profiles:
        profiles["shared"] = {
            "targets": {
                "database": {
                    "probe": {"kind": "tcp", "host": "127.0.0.1", "port": 5432},
                    "provision": {"kind": "manual"},
                }
            }
        }
    value = {
        "schema_version": 2,
        "svc_version": baseline,
        "dev": {"profile": "local", "profiles": profiles},
        "run": {"check": {"argv": ["pdm", "run", "test"]}},
    }
    content = (json.dumps(value, indent=2) + "\n").encode()
    (root / "svc.json").write_bytes(content)
    if local:
        (root / "svc.local.json").write_text(
            json.dumps(
                {
                    "dev": {
                        "profiles": {
                            "local": {
                                "targets": {"web": {"access": ["http://web.localhost"]}}
                            }
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
    return content


def test_targetless_upgrade_selects_config_then_hands_off_to_corpus(
    tmp_path: Path,
) -> None:
    write_legacy(tmp_path, local=True)

    plan = plan_upgrade(tmp_path)

    assert plan.target == "config"
    assert plan.status == "migration-required"
    assert [mutation.path for mutation in plan.mutations] == [
        "svc.json",
        "svc.local.json",
    ]
    assert len(plan.remaining_targets) == 1
    remaining = plan.remaining_targets[0]
    assert remaining.target == "corpus"
    assert remaining.status == "pending"
    assert remaining.from_version == "10.0.1"
    assert remaining.to_version == "12.0.0"
    assert plan.digest is not None

    receipt = apply_upgrade(plan, plan.digest)

    assert receipt.status == "applied"
    assert receipt.migration.disposition == "caller-asserted"
    transformed = parse_project_config((tmp_path / "svc.json").read_bytes())
    assert transformed.corpus_version == "10.0.1"
    assert transformed.dev is not None
    assert tuple(transformed.dev.targets) == ("web",)
    assert "local" in transformed.dev.targets["web"].probe.argv
    assert json.loads((tmp_path / "svc.local.json").read_bytes())["schema_version"] == 3

    corpus = plan_upgrade(tmp_path)
    assert corpus.target == "corpus"
    assert corpus.status == "migration-required"
    assert corpus.details.corpus is not None
    assert corpus.details.corpus.from_version == "10.0.1"
    assert corpus.details.corpus.releases is not None
    assert len(corpus.details.corpus.releases) == 4
    assert corpus.digest is not None

    corpus_receipt = apply_upgrade(corpus, corpus.digest)
    assert corpus_receipt.remaining_targets == ()
    assert (
        parse_project_config((tmp_path / "svc.json").read_bytes()).corpus_version
        == "12.0.0"
    )
    assert plan_upgrade(tmp_path).target is None
    assert plan_upgrade(tmp_path).status == "noop"


def test_config_upgrade_blocks_lossy_profile_selection_but_corpus_is_independent(
    tmp_path: Path,
) -> None:
    before = write_legacy(tmp_path, multiple_profiles=True)

    config = plan_upgrade(tmp_path, "config")
    assert config.status == "blocked"
    assert config.digest is None
    assert config.mutations == ()
    assert config.blockers[0].code == "multiple-dev-profiles"

    corpus = plan_upgrade(tmp_path, "corpus")
    assert corpus.status == "migration-required"
    assert corpus.digest is not None
    apply_upgrade(corpus, corpus.digest)
    after = (tmp_path / "svc.json").read_bytes()
    assert after == before.replace(b'"10.0.1"', b'"12.0.0"', 1)
    assert json.loads(after)["dev"]["profiles"]["shared"]


def test_upgrade_digest_rejection_does_not_disclose_a_replacement(
    tmp_path: Path,
) -> None:
    write_legacy(tmp_path)
    plan = plan_upgrade(tmp_path, "config")

    with pytest.raises(SvcError) as raised:
        apply_upgrade(plan, "0" * 64)

    assert raised.value.code == "plan-digest-mismatch"
    assert "expected" not in raised.value.details
    assert raised.value.details["repository_effect"] == "none"
    assert json.loads((tmp_path / "svc.json").read_bytes())["schema_version"] == 2


def test_corpus_plan_references_guides_and_does_not_bind_project_documents(
    tmp_path: Path,
) -> None:
    (tmp_path / "svc.json").write_text(
        '{"schema_version":3,"corpus_version":"11.0.1"}\n',
        encoding="utf-8",
    )
    plan = plan_upgrade(tmp_path, "corpus")
    corpus = plan.details.corpus
    assert corpus is not None and corpus.releases is not None
    guides = corpus.releases[0].guides
    assert guides is not None

    assert plan.status == "migration-required"
    assert [guide.path for guide in guides] == [
        "migrations/agent-analysis-query-read.md",
        "migrations/agent-task-performance-analysis.md",
        "migrations/local-trust-boundary.md",
    ]
    digest = plan.digest
    assert digest is not None
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "prd.md").write_text("migrated by Agent\n", encoding="utf-8")

    apply_upgrade(plan_upgrade(tmp_path, "corpus"), digest)
    assert (tmp_path / "docs" / "prd.md").read_text(
        encoding="utf-8"
    ) == "migrated by Agent\n"


def test_off_chain_corpus_baseline_blocks_without_guessing(
    tmp_path: Path,
) -> None:
    (tmp_path / "svc.json").write_text(
        json.dumps({"schema_version": 3, "corpus_version": "9.0.0"}),
        encoding="utf-8",
    )

    plan = plan_upgrade(tmp_path, "corpus")

    assert plan.status == "blocked"
    assert plan.blockers[0].code == "unsupported-corpus-baseline"
    assert plan.mutations == ()
