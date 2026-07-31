from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from tools.repository_policy import (
    PolicyViolation,
    check_ci_workflow,
    check_legacy_workflow_policy,
    check_publish_mutation_policy,
    check_publish_plan_policy,
)


def write_fixture(root: Path, name: str, content: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")
    return path


def ci_fixture() -> str:
    return """
    name: CI
    on:
      pull_request:
      push:
        branches: [main]
    permissions:
      contents: read
    jobs:
      python:
        name: Python ${{ matrix.python-version }}
        persist-credentials: false
        python-version: ["3.11", "3.14"]
        run: pdm run test
      quality:
        name: Quality and architecture
        persist-credentials: false
        run: |
          pdm install --frozen-lockfile -d -G quality
          pdm run check-documents
          pdm run check-repository-policy
          pdm run lint-tests
          pdm run typecheck
          pdm run lint-imports
          pdm run lint-workflows
      distribution:
        name: Distribution
        persist-credentials: false
        fetch-depth: 0
        run: |
          args=(--commit "$GITHUB_SHA" --base "origin/$BASE_REF" --release-none)
          pdm run release target-qualify "${args[@]}"
          echo PDM_BUILD_SCM_VERSION=1.2.3
          pdm build
          pdm run build-monolith
          python tools/accept_agent_thread.py --slice all --expected-sha256 x --wheelhouse /tmp/svc-wheelhouse
          svc lookup --name x
          svc init repo
          svc status repo
      release-policy:
        name: Release policy
        persist-credentials: false
        fetch-depth: 0
        run: pdm run release target-qualify --commit "$GITHUB_SHA" --base "origin/$BASE_REF" --release-none
    """


def publish_fixture() -> str:
    return """
    name: Publish
    on:
      push:
        tags: ["v*"]
      workflow_dispatch:
    permissions:
      contents: read
    concurrency:
      group: svc-publish
      cancel-in-progress: false
    jobs:
      plan:
        run: |
          test "$GITHUB_REF" = "refs/tags/$tag"
          fetch-depth: 0
          persist-credentials: false
          actions/workflows/ci.yml/runs
          qualification-state.json
          COMMIT=$(git rev-parse HEAD)
          commit = os.environ["COMMIT"]
          target-plan
          --main-ref origin/main
          --remote origin
          target-preflight
          if [[ "$decision" == "fail" ]]; then exit 1; fi
      bundle:
        run: |
          needs.plan.outputs.decision == 'build'
          needs.plan.outputs.decision == 'requires-bundle'
          ref: ${{ needs.plan.outputs.commit }}
          svc-release-control-${{ github.run_id }}
          release-control/release-plan.json
          run-id: ${{ needs.plan.outputs.prior-run-id }}
          gh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$TAG"
          test "$sha" = "$EXPECTED_COMMIT"
          plan_file=release-control/release-plan.json
          release-control/tools/release.py target-bundle
          release-control/tools/release.py target-verify-bundle
          pdm build
          pdm run test
          pdm run lint-workflows
          pdm run build-monolith
          --slice all --expected-sha256 x
          actions/attest-build-provenance@v2
          name: svc-release-${{ needs.plan.outputs.tag }}
          steps.upload.outputs.artifact-id
          artifact["expires_at"]
          retention-days: 90
    """


def mutation_fixture() -> str:
    return """
    name: Publish
    jobs:
      publish-pypi:
        if: needs.plan.outputs.decision != 'exact-complete'
        needs: [plan, bundle]
        environment: release
        id-token: write
        run: |
          svc-release-control-${{ github.run_id }}
          if: needs.bundle.outputs.source-run-id == github.run_id
          run-id: ${{ needs.bundle.outputs.source-run-id }}
          release-control/tools/release.py target-verify-bundle
          gh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$TAG"
          release-control/tools/release.py target-pypi-plan
          release-control/tools/release.py target-stage-pypi
          pypa/gh-action-pypi-publish@v1
          packages-dir: dist/upload/
          ready_for_github
      finalize-github-release:
        if: needs.plan.outputs.decision != 'exact-complete'
        needs: [plan, bundle, publish-pypi]
        run: |
          svc-release-control-${{ github.run_id }}
          if: needs.bundle.outputs.source-run-id == github.run_id
          run-id: ${{ needs.bundle.outputs.source-run-id }}
          release-control/tools/release.py target-verify-bundle
          gh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$TAG"
          release-control/tools/release.py target-github-plan
          gh release create --verify-tag
          gh release upload
          gh release edit
          "resolved_tag_commit"
          "asset_sha256"
          "asset_content"
          Verify the exact immutable Release
    """


def test_ci_checker_accepts_fixture_and_rejects_quality_regression(tmp_path: Path) -> None:
    path = write_fixture(tmp_path, "ci.yml", ci_fixture())
    check_ci_workflow(path)

    path.write_text(path.read_text(encoding="utf-8").replace("pdm run check-documents\n", ""), encoding="utf-8")
    with pytest.raises(PolicyViolation, match="check-documents"):
        check_ci_workflow(path)


def test_legacy_workflow_checker_rejects_retired_path_fixture(tmp_path: Path) -> None:
    write_fixture(tmp_path, "ci.yml", "name: CI\n")
    check_legacy_workflow_policy(tmp_path)

    write_fixture(tmp_path, "release-pr.yml", "name: retired\nrun: release prepare\n")
    with pytest.raises(PolicyViolation, match="release-pr.yml"):
        check_legacy_workflow_policy(tmp_path)


def test_publish_qualification_checker_rejects_tag_checkout_fixture(tmp_path: Path) -> None:
    path = write_fixture(tmp_path, "publish.yml", publish_fixture())
    check_publish_plan_policy(path)

    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "ref: ${{ needs.plan.outputs.commit }}", "ref: ${{ needs.plan.outputs.tag }}"
        ),
        encoding="utf-8",
    )
    with pytest.raises(PolicyViolation, match="commit"):
        check_publish_plan_policy(path)


def test_publish_mutation_checker_rejects_clobber_fixture(tmp_path: Path) -> None:
    path = write_fixture(tmp_path, "publish.yml", mutation_fixture())
    check_publish_mutation_policy(path)

    path.write_text(path.read_text(encoding="utf-8") + "\n--clobber\n", encoding="utf-8")
    with pytest.raises(PolicyViolation, match="clobber"):
        check_publish_mutation_policy(path)
