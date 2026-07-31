"""Static ownership for canonical repository policy that does not belong to pytest.

The checker deliberately has no YAML dependency. GitHub workflows are also
validated as YAML by zizmor in the same quality job; this gate constrains
their canonical source shape with indentation-aware workflow/job blocks and
stable command or data-flow tokens. It does not claim to be a general YAML
parser. PDM, zizmor, and the compiler remain the owners of their own concerns.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class PolicyViolation(ValueError):
    """Raised when a repository policy is not satisfied."""


@dataclass(frozen=True)
class SourceLine:
    number: int
    indent: int
    content: str


class WorkflowDocument:
    """Small structural view over the subset of YAML needed by policy.

    It intentionally does not claim to be a YAML parser.  Block boundaries
    follow YAML's indentation rule, while scalar and expression values stay
    opaque strings.  This keeps the checker stdlib-only and avoids coupling it
    to a third-party parser's interpretation of GitHub's ``on`` key.
    """

    def __init__(self, path: Path):
        self.path = path
        try:
            self.lines = tuple(self._read(path))
        except (OSError, UnicodeDecodeError) as error:
            raise PolicyViolation(f"cannot read workflow {path}: {error}") from error

    @staticmethod
    def _read(path: Path) -> Iterable[SourceLine]:
        for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            content = raw.lstrip()
            if not content or content.startswith("#"):
                continue
            indent = len(raw) - len(content)
            yield SourceLine(number, indent, content)

    def block(self, key: str, *, indent: int = 0) -> tuple[SourceLine, ...]:
        """Return a mapping block, including its header, or an empty tuple."""

        header = f"{key}:"
        for index, line in enumerate(self.lines):
            if line.indent != indent or not (
                line.content == header or line.content.startswith(header + " ")
            ):
                continue
            block: list[SourceLine] = [line]
            for child in self.lines[index + 1 :]:
                if child.indent <= indent:
                    break
                block.append(child)
            return tuple(block)
        return ()

    def jobs(self) -> dict[str, tuple[SourceLine, ...]]:
        jobs = self.block("jobs")
        result: dict[str, tuple[SourceLine, ...]] = {}
        for index, line in enumerate(jobs[1:], 1):
            if line.indent != 2 or not line.content.endswith(":"):
                continue
            name = line.content[:-1]
            block: list[SourceLine] = [line]
            for child in jobs[index + 1 :]:
                if child.indent <= 2:
                    break
                block.append(child)
            result[name] = tuple(block)
        return result

    @staticmethod
    def text(block: Iterable[SourceLine]) -> str:
        return "\n".join(line.content for line in block)


def _fail(policy: str, detail: str) -> None:
    raise PolicyViolation(f"{policy}: {detail}")


def _require(policy: str, condition: bool, detail: str) -> None:
    if not condition:
        _fail(policy, detail)


def _require_line(policy: str, block: Iterable[SourceLine], expected: str) -> None:
    _require(
        policy,
        any(line.content == expected or line.content.startswith(expected + " ") for line in block),
        f"missing `{expected}`",
    )


def _require_markers(policy: str, block: Iterable[SourceLine], markers: Iterable[str]) -> None:
    text = WorkflowDocument.text(block)
    for marker in markers:
        _require(policy, marker in text, f"missing semantic marker `{marker}`")


def _require_order(policy: str, block: Iterable[SourceLine], markers: Iterable[str]) -> None:
    text = WorkflowDocument.text(block)
    cursor = -1
    for marker in markers:
        position = text.find(marker, cursor + 1)
        _require(policy, position >= 0, f"missing ordered marker `{marker}`")
        _require(policy, position >= cursor, f"marker `{marker}` is out of order")
        cursor = position


def check_pyproject_policy(path: Path) -> None:
    """Own the exact SCM/PDM projection contract."""

    policy = "SCM/PDM projection"
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        _fail(policy, f"cannot read TOML: {error}")

    project = data.get("project", {})
    _require(policy, project.get("dynamic") == ["version"], "project.dynamic must be ['version']")
    _require(policy, "version" not in project, "project.version must remain SCM-dynamic")
    _require(
        policy,
        data.get("build-system", {}).get("requires") == ["pdm-backend==2.4.9"],
        "build backend must be pinned to pdm-backend==2.4.9",
    )
    expected = {
        "source": "scm",
        "tag_filter": "v[0-9]*.[0-9]*.[0-9]*",
        "tag_regex": r"^v(?P<version>(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*))$",
        "version_format": "pdm_build:format_scm_version",
        "fallback_version": "0.0.0",
    }
    _require(
        policy,
        data.get("tool", {}).get("pdm", {}).get("version") == expected,
        "tool.pdm.version must use the strict SCM projection",
    )


def check_ci_workflow(path: Path) -> None:
    """Own CI trigger, quality, and installed-acceptance invariants (W1)."""

    policy = "workflow W1 (CI quality)"
    document = WorkflowDocument(path)
    trigger = document.block("on")
    permissions = document.block("permissions")
    _require_markers(policy, trigger, ("pull_request:", "push:", "branches: [main]"))
    _require_markers(policy, permissions, ("contents: read",))
    _require(policy, "contents: write" not in WorkflowDocument.text(permissions), "workflow permissions must be read-only")

    jobs = document.jobs()
    required_jobs = {
        "python": "name: Python ${{ matrix.python-version }}",
        "quality": "name: Quality and architecture",
        "distribution": "name: Distribution",
        "release-policy": "name: Release policy",
    }
    for name, display_name in required_jobs.items():
        _require(policy, name in jobs, f"required job `{name}` is missing")
        _require_line(policy, jobs[name], display_name)
        _require_line(policy, jobs[name], "persist-credentials: false")
    _require(
        policy,
        "contents: write" not in WorkflowDocument.text(document.lines),
        "workflow permissions must remain read-only",
    )

    python = jobs["python"]
    _require_markers(policy, python, ('python-version: ["3.11", "3.14"]', "pdm run test"))

    quality = jobs["quality"]
    _require_order(
        policy,
        quality,
        (
            "pdm install --frozen-lockfile -d -G quality",
            "pdm run check-documents",
            "pdm run check-repository-policy",
            "pdm run lint-tests",
            "pdm run typecheck",
            "pdm run lint-imports",
            "pdm run lint-workflows",
        ),
    )

    distribution = jobs["distribution"]
    _require_order(
        policy,
        distribution,
        (
            "pdm run release target-qualify",
            "pdm build",
            "pdm run build-monolith",
            "tools/accept_agent_thread.py",
        ),
    )
    _require_markers(
        policy,
        distribution,
        (
            "fetch-depth: 0",
            '--commit "$GITHUB_SHA"',
            '--base "origin/$BASE_REF"',
            "--release-none",
            "PDM_BUILD_SCM_VERSION=",
            "--slice all",
            "--expected-sha256",
            "--wheelhouse /tmp/svc-wheelhouse",
            "svc lookup --name",
            "svc init",
            "svc status",
        ),
    )
    release_policy = jobs["release-policy"]
    _require_markers(
        policy,
        release_policy,
        (
            "fetch-depth: 0",
            "pdm run release target-qualify",
            '--commit "$GITHUB_SHA"',
            '--base "origin/$BASE_REF"',
            "--release-none",
        ),
    )


def check_legacy_workflow_policy(workflows: Path) -> None:
    """Own absence of retired release workflows and command paths (W2)."""

    policy = "workflow W2 (retired release paths)"
    _require(policy, not (workflows / "release-pr.yml").exists(), "release-pr.yml must not exist")
    _require(policy, not (workflows / "release-tag.yml").exists(), "release-tag.yml must not exist")
    forbidden = (
        "branch=release/svc",
        "refs/heads/release/svc",
        "release prepare",
        "release tag-plan",
        "towncrier",
        "git tag ",
        "gh workflow run publish.yml",
        "pdm run release check-pr",
        "pdm run release check-ci",
    )
    workflow_files = sorted((*workflows.glob("*.yml"), *workflows.glob("*.yaml")))
    for path in workflow_files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            _fail(policy, f"cannot read {path.name}: {error}")
        for marker in forbidden:
            _require(policy, marker not in text, f"retired marker `{marker}` remains in {path.name}")


def check_publish_plan_policy(path: Path) -> None:
    """Own tag authority, serialization, and pre-build qualification (W3)."""

    policy = "workflow W3 (publish qualification)"
    document = WorkflowDocument(path)
    trigger = document.block("on")
    concurrency = document.block("concurrency")
    _require_markers(policy, trigger, ('push:', 'tags: ["v*"]', "workflow_dispatch:"))
    _require(policy, "branches:" not in WorkflowDocument.text(trigger), "publish must be tag-triggered, not branch-triggered")
    _require(policy, "workflow_call:" not in WorkflowDocument.text(trigger), "publish must not be callable as a reusable workflow")
    _require_markers(policy, concurrency, ("group: svc-publish", "cancel-in-progress: false"))

    jobs = document.jobs()
    _require(policy, "plan" in jobs and "bundle" in jobs, "plan and bundle jobs are required")
    _require_order(policy, document.block("jobs"), ("plan:", "bundle:"))
    plan = jobs["plan"]
    _require_markers(
        policy,
        plan,
        (
            'test "$GITHUB_REF" = "refs/tags/$tag"',
            "fetch-depth: 0",
            "persist-credentials: false",
            "actions/workflows/ci.yml/runs",
            "qualification-state.json",
            "COMMIT=$(git rev-parse HEAD)",
            'commit = os.environ["COMMIT"]',
            "target-plan",
            "--main-ref origin/main",
            "--remote origin",
            "target-preflight",
            'if [[ "$decision" == "fail" ]]',
        ),
    )
    _require(
        policy,
        'commit = os.environ["GITHUB_SHA"]' not in WorkflowDocument.text(plan),
        "qualification must bind the checked-out commit rather than event metadata",
    )
    _require_order(policy, plan, ("target-plan", "target-preflight"))
    bundle = jobs["bundle"]
    _require_markers(
        policy,
        bundle,
        (
            "needs.plan.outputs.decision == 'build'",
            "needs.plan.outputs.decision == 'requires-bundle'",
            "ref: ${{ needs.plan.outputs.commit }}",
            "svc-release-control-${{ github.run_id }}",
            "release-control/release-plan.json",
            "run-id: ${{ needs.plan.outputs.prior-run-id }}",
            "gh api \"repos/$GITHUB_REPOSITORY/git/ref/tags/$TAG\"",
            "test \"$sha\" = \"$EXPECTED_COMMIT\"",
            "plan_file=release-control/release-plan.json",
            "release-control/tools/release.py target-bundle",
            "release-control/tools/release.py target-verify-bundle",
            "pdm build",
            "pdm run test",
            "pdm run lint-workflows",
            "pdm run build-monolith",
            "--slice all",
            "--expected-sha256",
            "actions/attest-build-provenance@",
            "name: svc-release-${{ needs.plan.outputs.tag }}",
            "steps.upload.outputs.artifact-id",
            'artifact["expires_at"]',
            "retention-days: 90",
        ),
    )
    _require(policy, "ref: ${{ needs.plan.outputs.tag }}" not in WorkflowDocument.text(bundle), "bundle must checkout the qualified commit")
    _require(
        policy,
        WorkflowDocument.text(bundle).count("pdm build") == 1,
        "the qualified bundle must be built exactly once",
    )
    _require(policy, "target-plan" not in WorkflowDocument.text(bundle), "bundle must use the trusted plan without replanning")
    _require(
        policy,
        "dist/release/release-check.py" not in WorkflowDocument.text(bundle),
        "bundle must not execute a verifier supplied by the bundle",
    )
    _require_order(policy, bundle, ("svc-release-control-${{ github.run_id }}", "run-id: ${{ needs.plan.outputs.prior-run-id }}"))
    _require(policy, "target-verify-bundle" in WorkflowDocument.text(bundle), "bundle identity must be verified before promotion")


def check_publish_mutation_policy(path: Path) -> None:
    """Own checked-bundle-only external mutation ordering and safeguards (W4)."""

    policy = "workflow W4 (publish mutation)"
    document = WorkflowDocument(path)
    jobs = document.jobs()
    _require(policy, "publish-pypi" in jobs and "finalize-github-release" in jobs, "mutation jobs are required")
    pypi = jobs["publish-pypi"]
    github = jobs["finalize-github-release"]
    _require_order(policy, document.block("jobs"), ("publish-pypi:", "finalize-github-release:"))

    _require_markers(
        policy,
        pypi,
        (
            "if: needs.plan.outputs.decision != 'exact-complete'",
            "needs: [plan, bundle]",
            "environment: release",
            "id-token: write",
            "svc-release-control-${{ github.run_id }}",
            "if: needs.bundle.outputs.source-run-id == github.run_id",
            "run-id: ${{ needs.bundle.outputs.source-run-id }}",
            "release-control/tools/release.py target-verify-bundle",
            "gh api \"repos/$GITHUB_REPOSITORY/git/ref/tags/$TAG\"",
            "release-control/tools/release.py target-pypi-plan",
            "release-control/tools/release.py target-stage-pypi",
            "pypa/gh-action-pypi-publish@",
            "packages-dir: dist/upload/",
            "ready_for_github",
        ),
    )
    pypi_text = WorkflowDocument.text(pypi)
    _require(policy, "actions/checkout@" not in pypi_text, "PyPI mutation must not checkout or rebuild")
    _require(policy, "pdm build" not in pypi_text and "pdm run" not in pypi_text, "PyPI mutation must use the retained bundle")
    _require(policy, "dist/release/release-check.py" not in pypi_text, "PyPI must use the current trusted verifier")

    _require_markers(
        policy,
        github,
        (
            "if: needs.plan.outputs.decision != 'exact-complete'",
            "needs: [plan, bundle, publish-pypi]",
            "svc-release-control-${{ github.run_id }}",
            "if: needs.bundle.outputs.source-run-id == github.run_id",
            "run-id: ${{ needs.bundle.outputs.source-run-id }}",
            "release-control/tools/release.py target-verify-bundle",
            "gh api \"repos/$GITHUB_REPOSITORY/git/ref/tags/$TAG\"",
            "release-control/tools/release.py target-github-plan",
            "gh release create",
            "--verify-tag",
            "gh release upload",
            "gh release edit",
            '"resolved_tag_commit"',
            '"asset_sha256"',
            '"asset_content"',
        ),
    )
    github_text = WorkflowDocument.text(github)
    _require(policy, "actions/checkout@" not in github_text, "GitHub mutation must not checkout or rebuild")
    _require(policy, "pdm build" not in github_text and "pdm run" not in github_text, "GitHub mutation must use the retained bundle")
    _require(policy, "dist/release/release-check.py" not in github_text, "GitHub must use the current trusted verifier")
    _require(policy, "id-token: write" not in github_text, "trusted publisher identity is reserved for PyPI")
    _require(
        policy,
        "--clobber" not in WorkflowDocument.text(document.lines),
        "GitHub asset mutation must not clobber existing files",
    )
    _require(policy, "environment: release" not in github_text, "release environment is reserved for PyPI publisher")


def check_repository_policy(root: Path) -> None:
    """Run every repository policy gate against ``root``."""

    root = root.resolve()
    check_pyproject_policy(root / "pyproject.toml")
    workflows = root / ".github" / "workflows"
    check_ci_workflow(workflows / "ci.yml")
    check_legacy_workflow_policy(workflows)
    check_publish_plan_policy(workflows / "publish.yml")
    check_publish_mutation_policy(workflows / "publish.yml")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check SVC repository static policy.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        check_repository_policy(args.root)
    except PolicyViolation as error:
        print(f"repository policy failed: {error}", file=sys.stderr)
        return 1
    print(f"Repository policy passed for {args.root.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
