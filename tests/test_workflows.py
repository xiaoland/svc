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


def test_ci_exposes_stable_pr_and_main_qualification_checks() -> None:
    text = workflow("ci.yml")
    assert "pull_request:" in text
    assert "push:" in text
    assert "branches: [main]" in text
    assert "contents: read" in text
    assert "contents: write" not in text

    for check_name in (
        "Python ${{ matrix.python-version }}",
        "Quality and architecture",
        "Distribution",
        "Release policy",
    ):
        assert text.count(f"name: {check_name}") == 1

    python = job(text, "python")
    assert 'python-version: ["3.11", "3.14"]' in text
    assert "pdm run test" in python

    for job_name in ("python", "quality", "distribution", "release-policy"):
        section = job(text, job_name)
        assert "persist-credentials: false" in section

    quality = job(text, "quality")
    install = "pdm install --frozen-lockfile -d -G quality"
    assert install in quality
    assert "pdm run lint-tests" in quality
    assert "pdm run typecheck" in quality
    assert "pdm run lint-imports" in quality
    assert "pdm run lint-workflows" in quality
    assert quality.index(install) < quality.index("pdm run lint-tests")
    assert quality.index("pdm run lint-tests") < quality.index("pdm run typecheck")
    assert quality.index("pdm run typecheck") < quality.index("pdm run lint-imports")
    assert quality.index("pdm run lint-imports") < quality.index("pdm run lint-workflows")

    distribution = job(text, "distribution")
    policy = job(text, "release-policy")
    for section in (distribution, policy):
        assert "fetch-depth: 0" in section
        assert "pdm run release target-qualify" in section
        assert "--commit \"$GITHUB_SHA\"" in section
        assert "--base \"origin/$BASE_REF\"" in section
        assert "--release-none" in section
        assert "pdm run release check-pr" not in section
        assert "pdm run release check-ci" not in section

    assert "PDM_BUILD_SCM_VERSION=" in distribution
    assert distribution.index("target-qualify") < distribution.index("pdm build")
    assert "pdm run build-monolith" in distribution
    assert "Smoke-test the installed wheel" in distribution
    assert "tools/accept_agent_thread.py" in distribution
    assert "--slice all" in distribution
    assert "--expected-sha256" in distribution
    assert "--wheelhouse /tmp/svc-wheelhouse" in distribution
    assert "svc lookup --name" in distribution
    assert "svc init" in distribution
    assert "svc status" in distribution


def test_legacy_release_workflows_and_normal_paths_are_absent() -> None:
    assert not (WORKFLOWS / "release-pr.yml").exists()
    assert not (WORKFLOWS / "release-tag.yml").exists()
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(WORKFLOWS.glob("*.yml"))
    )
    for legacy in (
        "branch=release/svc",
        "refs/heads/release/svc",
        "release prepare",
        "release tag-plan",
        "towncrier",
        "git tag ",
        "gh workflow run publish.yml",
    ):
        assert legacy not in text


def test_publish_has_one_tag_authoritative_writer_and_prebuild_recovery_gate() -> None:
    text = workflow("publish.yml")
    plan = job(text, "plan")
    bundle = job(text, "bundle")

    assert 'tags: ["v*"]' in text
    assert "branches:" not in text
    assert "workflow_dispatch:" in text
    assert "workflow_call:" not in text
    assert "Exact existing release tag to verify or recover" in text
    assert "Prior Publish run that owns the original bundle after external mutation" in text
    assert "group: svc-publish" in text
    assert "group: svc-publish-" not in text
    assert "cancel-in-progress: false" in text
    assert 'test "$GITHUB_REF" = "refs/tags/$tag"' in plan
    assert "bundle_run_id must be a positive Publish workflow run ID" in plan

    assert "fetch-depth: 0" in plan
    assert "persist-credentials: false" in plan
    assert "checks: read" in plan
    assert "Capture raw exact-main qualification evidence" in plan
    assert "COMMIT=$(git rev-parse HEAD)" in plan
    assert 'commit = os.environ["COMMIT"]' in plan
    assert 'commit = os.environ["GITHUB_SHA"]' not in plan
    assert '"runs": runs' in plan
    assert '"jobs_by_run": jobs_by_run' in plan
    assert '"check_runs": check_runs' in plan
    assert "actions/workflows/ci.yml/runs" in plan
    assert "filter=latest&per_page=100" in plan
    assert "--qualification-state qualification-state.json" in plan
    assert "target-plan" in plan
    assert "--main-ref origin/main" in plan
    assert "--remote origin" in plan
    assert "target-preflight" in plan
    assert plan.index("target-plan") < plan.index("target-preflight")
    assert '"predecessor": {' in plan
    assert '"candidate": {' in plan
    assert '"artifact": {"run": run, "artifacts": artifacts}' in plan
    assert 'run = json_observation(f"{api_root}/actions/runs/{prior}", github=True)' in plan
    assert (
        'f"{api_root}/actions/runs/{prior}/artifacts?per_page=100", github=True'
        in plan
    )
    assert '"asset_sha256"' in plan
    assert '"asset_content"' in plan
    assert '"svc-release-manifest.json"' in plan
    assert '"svc-release-metadata.json"' in plan
    assert '"expected"' not in plan
    assert '"decision" == "fail"' not in plan
    assert 'if [[ "$decision" == "fail" ]]' in plan
    assert "actions/download-artifact@" not in plan
    assert plan.index('run = json_observation(f"{api_root}/actions/runs/{prior}"') < (
        plan.index("target-preflight")
    )
    assert "svc-release-control-${{ github.run_id }}" in plan
    assert "release-plan.json" in plan
    assert "tools/release.py" in plan
    assert "steps.preflight.outputs.decision == 'requires-bundle'" in plan
    assert "retention-days: 1" in plan

    assert "needs.plan.outputs.decision == 'build'" in bundle
    assert "needs.plan.outputs.decision == 'requires-bundle'" in bundle
    assert "ref: ${{ needs.plan.outputs.commit }}" in bundle
    assert "ref: ${{ needs.plan.outputs.tag }}" not in bundle
    assert "Recheck the exact remote tag before build" in bundle
    assert 'test "$sha" = "$EXPECTED_COMMIT"' in bundle
    assert "target-plan" not in bundle
    assert "Download the current trusted verifier and plan" in bundle
    assert "Select the current trusted plan" in bundle
    assert "release-control/tools/release.py target-bundle" in bundle
    assert "release-control/tools/release.py target-verify-bundle" in bundle
    assert "dist/release/release-check.py" not in bundle
    assert bundle.index("Download the current trusted verifier and plan") < bundle.index(
        "Recover the original release bundle"
    )
    assert "target-bundle" in bundle
    assert "target-verify-bundle" in bundle
    assert bundle.count("pdm build") == 1
    assert "pdm run test" in bundle
    assert "pdm run lint-workflows" in bundle
    assert "pdm run build-monolith" in bundle
    assert "Smoke-test the exact release wheel" in bundle
    assert "tools/accept_agent_thread.py" in bundle
    assert "--slice all" in bundle
    assert "--expected-sha256" in bundle
    assert "--wheelhouse /tmp/svc-release-wheelhouse" in bundle
    assert "svc lookup --name" in bundle
    assert "svc init" in bundle
    assert "svc status" in bundle
    assert "actions/attest-build-provenance@" in bundle
    assert "Recover the original release bundle" in bundle
    assert "run-id: ${{ needs.plan.outputs.prior-run-id }}" in bundle
    assert "Selected bundle identity differs from the qualified tag" in bundle
    assert "actions/upload-artifact@" in bundle
    assert "name: svc-release-${{ needs.plan.outputs.tag }}" in bundle
    assert "retention-days: 90" in bundle
    assert "steps.upload.outputs.artifact-id" in bundle
    assert 'artifact["expires_at"]' in bundle
    assert "timedelta(days=89)" in bundle


def test_publish_promotes_only_the_checked_bundle_in_pypi_then_github_order() -> None:
    text = workflow("publish.yml")
    pypi = job(text, "publish-pypi")
    finalize = job(text, "finalize-github-release")

    # An explicit recovery dispatch can prove the immutable external release
    # complete without a retained Actions bundle.  Both mutation jobs must
    # terminate read-only instead of trying to download a bundle with an empty
    # source-run-id.
    assert "if: needs.plan.outputs.decision != 'exact-complete'" in pypi
    assert "if: needs.plan.outputs.decision != 'exact-complete'" in finalize

    assert "environment: release" in pypi
    assert "id-token: write" in pypi
    assert pypi.count("actions/download-artifact@") == 3
    assert "Download the current trusted verifier and plan" in pypi
    assert "release-control/tools/release.py target-verify-bundle" in pypi
    assert "release-control/tools/release.py target-pypi-plan" in pypi
    assert "release-control/tools/release.py target-stage-pypi" in pypi
    assert "dist/release/release-check.py" not in pypi
    assert pypi.index("Download the current trusted verifier and plan") < pypi.index(
        "Download this run's original bundle"
    )
    assert "target-verify-bundle" in pypi
    assert "target-pypi-plan" in pypi
    assert "target-stage-pypi" in pypi
    assert "Recheck the exact remote tag before PyPI mutation" in pypi
    assert 'test "$sha" = "$EXPECTED_COMMIT"' in pypi
    assert "--dist-dir dist/upload" in pypi
    assert "pypa/gh-action-pypi-publish@" in pypi
    assert "packages-dir: dist/upload/" in pypi
    assert "Publish only the missing original files" in pypi
    assert "Read PyPI back until every filename and hash is exact" in pypi
    assert '["ready_for_github"]' in pypi
    assert "for attempt in {1..12}" in pypi
    assert "actions/checkout@" not in pypi
    assert "pdm build" not in pypi
    assert "pdm run" not in pypi

    assert "needs: [plan, bundle, publish-pypi]" in finalize
    assert finalize.count("actions/download-artifact@") == 3
    assert "Download the current trusted verifier and plan" in finalize
    assert "release-control/tools/release.py target-verify-bundle" in finalize
    assert "release-control/tools/release.py target-github-plan" in finalize
    assert "dist/release/release-check.py" not in finalize
    assert finalize.index("Download the current trusted verifier and plan") < finalize.index(
        "Download this run's original bundle"
    )
    assert "target-verify-bundle" in finalize
    assert "target-github-plan" in finalize
    assert "Permit only absent or exact draft mutation" in finalize
    assert "steps.plan.outputs.action == 'create'" in finalize
    assert "steps.plan.outputs.action == 'resume-draft'" in finalize
    assert "Recheck the exact remote tag before GitHub mutation" in finalize
    assert 'test "$sha" = "$EXPECTED_COMMIT"' in finalize
    assert finalize.index("Recheck the exact remote tag before GitHub mutation") < finalize.index(
        "Create the immutable Release with every manifest asset"
    )
    assert 'gh release create "$TAG" "${assets[@]}"' in finalize
    assert "--verify-tag" in finalize
    assert '--title "$title"' in finalize
    assert '--notes-file "dist/release/$notes"' in finalize
    assert "gh release create" in finalize
    assert "gh release create \"$TAG\" --draft" not in finalize
    assert "gh release upload" in finalize
    assert 'gh release edit "$TAG" --draft=false' in finalize
    assert "--clobber" not in finalize
    assert '"resolved_tag_commit"' in finalize
    assert '"target_commitish"' not in finalize
    assert '"asset_sha256"' in finalize
    assert '"asset_content"' in finalize
    assert "Verify the exact immutable Release" in finalize
    assert 'if [[ "$action" == "verified" ]]' in finalize
    assert "actions/checkout@" not in finalize
    assert "pdm build" not in finalize

    assert text.index("  publish-pypi:") < text.index("  finalize-github-release:")
    assert "skip-existing" not in text
    assert "python dist/release/release-check.py" not in text
    assert "release-check.py bundle" not in text
    assert "release-check.py verify-bundle" not in text
