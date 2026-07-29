from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"


def workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def job(text: str, name: str) -> str:
    match = re.search(
        rf"^  {re.escape(name)}:\n(?P<body>.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"missing job {name}"
    return match.group(0)


def test_ci_is_read_only_locks_before_install_and_smokes_the_embedded_runtime_wheel() -> None:
    text = workflow("ci.yml")
    install = "pdm install --frozen-lockfile -d -G release -G test"
    assert "contents: read" in text
    assert 'python-version: ["3.11", "3.14"]' in text
    assert "pdm lock --check" in text
    assert install in text
    assert text.index("pdm lock --check") < text.index(install)
    assert "pdm run lint-tests" in text
    assert text.index(install) < text.index("pdm run lint-tests") < text.index("pdm run test")
    assert "pdm run release check-pr" in text
    assert "release:none" in text
    assert "pdm build" in text
    assert "svc lookup --name" in text
    assert "svc init" in text
    assert "svc migrate" not in text
    assert "contents: write" not in text
    for job_name in ("test", "typecheck", "distribution"):
        section = job(text, job_name)
        assert "persist-credentials: false" in section

    quality = job(text, "typecheck")
    install = "pdm install --frozen-lockfile -d -G quality"
    assert install in quality
    assert "pdm run typecheck" in quality
    assert "pdm run lint-imports" in quality
    assert "pdm run lint-workflows" in quality
    assert quality.index(install) < quality.index("pdm run typecheck")
    assert quality.index("pdm run typecheck") < quality.index("pdm run lint-imports") < quality.index("pdm run lint-workflows")


def test_release_pr_uses_builtin_token_and_prepares_a_checked_lockfile() -> None:
    text = workflow("release-pr.yml")
    assert "contents: write" in text
    assert "pull-requests: write" in text
    assert "token: ${{ github.token }}" in text
    assert "GH_TOKEN: ${{ github.token }}" in text
    assert "pdm run release prepare" in text
    prepared = text.index("pdm run release prepare")
    lock_check = text.index("pdm lock --check", prepared)
    resync = text.index("pdm install --frozen-lockfile -d -G release -G test", prepared)
    test = text.index("pdm run test", prepared)
    assert prepared < lock_check
    assert lock_check < resync
    assert resync < test
    assert "migration guidance" in text
    assert "git add -A" in text
    assert "Release preparation changed an unexpected path" in text
    assert "git add CHANGELOG.md changes" not in text
    assert 'gh pr list --head "$branch" --base main --state open' in text
    assert 'gh pr edit "$existing_pr"' in text
    assert 'gh pr view "$branch"' not in text
    assert "gh pr create" in text
    assert "actions/create-github-app-token@" not in text
    assert "RELEASE_APP_ID" not in text
    assert "RELEASE_APP_PRIVATE_KEY" not in text
    assert "secrets." not in text
    assert "vars." not in text
    assert "gh release create" not in text
    assert "gh-action-pypi-publish" not in text


def test_release_tag_binds_only_a_merged_release_candidate_to_its_merge_sha() -> None:
    text = workflow("release-tag.yml")
    assert "pull_request:" in text
    assert "branches: [main]" in text
    assert "types: [closed]" in text
    assert "github.event.pull_request.merged == true" in text
    assert "github.event.pull_request.head.ref == 'release/svc'" in text
    assert "github.event.pull_request.merge_commit_sha" in text
    assert "workflow_dispatch:" in text
    assert "commit:" in text
    assert "required: true" in text
    assert "ref: ${{ steps.target.outputs.commit }}" in text
    assert 'git merge-base --is-ancestor "$commit" origin/main' in text
    assert "pdm lock --check" in text
    assert 'pdm run release tag-plan --commit "$COMMIT" --json' in text
    assert 'git tag -a "$tag" -m "SVC $version" "$COMMIT"' in text
    assert 'git fetch --force origin "refs/tags/$tag:refs/tags/$tag"' in text
    assert 'pdm run release verify-tag --tag "$tag" --commit "$COMMIT" --json' in text
    publish = job(text, "publish")
    assert "actions: write" in publish
    assert "GH_TOKEN: ${{ github.token }}" in publish
    assert 'gh workflow run publish.yml --repo "$GITHUB_REPOSITORY" --ref "$TAG" -f tag="$TAG"' in publish
    assert "publish-plan" not in text
    assert "resume-draft" not in text


def test_publish_is_tag_bound_builds_once_and_hands_the_bundle_to_downstream_jobs() -> None:
    text = workflow("publish.yml")
    build = job(text, "build")
    pypi = job(text, "publish-pypi")
    finalize = job(text, "finalize-github-release")

    assert 'tags: ["v*"]' in text
    assert "branches: [main]" not in text
    assert "workflow_dispatch:" in text
    assert "workflow_call:" not in text
    assert "tag:" in text
    assert "required: true" in text
    assert "environment: release" in pypi
    assert "id-token: write" in pypi
    assert "ref: ${{ steps.target.outputs.tag }}" in build
    assert 'git rev-parse "$TAG^{commit}"' in build
    assert 'git merge-base --is-ancestor "$commit" origin/main' in build
    assert "pdm lock --check" in build
    assert "pdm install --frozen-lockfile -d -G release -G test" in build
    assert build.index("pdm lock --check") < build.index("pdm install --frozen-lockfile -d -G release -G test")
    assert "pdm run release verify-tag" in build
    assert "pdm run test" in build
    assert "pdm run build-monolith" in build
    assert build.count("pdm build") == 1
    assert "pdm run release bundle" in build
    assert "actions/attest-build-provenance@" in build
    assert "actions/upload-artifact@" in build
    assert "svc-release-${{ steps.target.outputs.tag }}" in build

    assert "actions/download-artifact@" in pypi
    assert "release-check.py verify-bundle" in pypi
    assert "release-check.py pypi-plan" in pypi
    assert "pypa/gh-action-pypi-publish@" in pypi
    assert "packages-dir: dist/release/python/" in pypi
    assert "actions/checkout@" not in pypi
    assert "pdm build" not in pypi
    assert "pdm run" not in pypi

    assert "actions/download-artifact@" in finalize
    assert "release-check.py verify-bundle" in finalize
    assert 'gh release create "$TAG" --draft --verify-tag' in finalize
    assert 'gh release edit "$TAG" --draft=false' in finalize
    assert 'gh release view "$TAG" --json isDraft,name,body' in finalize
    assert "Existing GitHub Release title or notes differ" in finalize
    assert "manifest-bound asset" in finalize
    assert 'cmp "$local"' in finalize
    assert "actions/checkout@" not in finalize
    assert "pdm build" not in finalize
    assert text.index("  publish-pypi:") < text.index("  finalize-github-release:")
    assert "publish-plan" not in text
    assert "resume-tag" not in text
    assert "resume-draft" not in text
    assert "skip-existing" not in text
    assert "gh api" not in text
