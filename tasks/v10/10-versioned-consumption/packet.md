# Versioned Consumption

- **Objective**: Replace manual document copying with a reliably distributable, version-addressable SVC CLI, explicit artifact authority, safe executable migrations, and a reviewable release protocol from change fragment through GitHub Release and Python installation.
- **Guardrails**:
  - Keep the distribution name `sustainable-vibe-coding`, executable `svc`, and Python import namespace distinct; rename the package to `svc_cli`, not generic `cli`.
  - Keep GitHub Releases as the canonical release record and PyPI as the pip-compatible installation registry. Do not represent GitHub Packages as a PyPI registry.
  - Defer GHCR until a real OCI or container consumer justifies the additional artifact, permissions, and verification surface.
  - Towncrier fragments declare release impact; commit messages improve history navigation but never determine Behavioral SemVer.
  - Build release artifacts once and promote the exact same wheel/sdist and digests across attestation, GitHub Release, and PyPI.
  - Keep publication protected, idempotent, provenance-bearing, and separately authorized. Do not create a branch, tag, release, registry package, GitHub App, or external environment without explicit authority.
  - Do not use sub-agents for this task.
- **Verification**:
  - Existing manifest/state/migration fixtures remain green after the package rename.
  - Contribution checks prove valid commit examples, Towncrier fragment policy, maximum-impact version calculation, migration obligations, and release-plan consistency.
  - Pull-request CI tests supported Python versions, builds the distribution, installs the wheel in a clean environment, and exercises init/status/migrate.
  - Release automation creates or updates one reviewable Release PR, synchronizes version/manifest/Changelog/lock state, and consumes only included fragments.
  - A protected publish dry-run proves one-build promotion, artifact hashes, attestation inputs, tag/version agreement, GitHub Release assets, PyPI Trusted Publishing configuration, retry/idempotency, and zero GHCR publication.
- **Current Truth**:
  - The local `10.0.0` consumption and migration slice is implemented and verified; see [`design.md`](design.md) and [`verification.md`](verification.md).
  - The Python package is `src/svc_cli/` with console entry `svc_cli.cli:main`; the distribution and executable remain `sustainable-vibe-coding` and `svc`.
  - Distribution is named `sustainable-vibe-coding`; the short PyPI project name `svc` is already owned by another project.
  - GitHub Packages does not provide a pip-compatible PyPI registry. The approved topology is GitHub Releases for canonical release assets plus PyPI for normal Python installation.
  - CI, Release PR, and protected publish workflows now exist under `.github/workflows/`; no Git tag, branch, GitHub Release, or Python distribution was created or published.
  - Towncrier fragments, the repository release planner, and `CONTRIBUTING.md` now own change declaration, Behavioral SemVer calculation, migration enforcement, and contribution guidance.
  - The detailed implementation sequence and external prerequisites are in [`release-plan.md`](release-plan.md).
- **Next Step**: Review the implemented local release protocol and verification evidence. External GitHub/PyPI configuration and first publication remain a separate, explicitly authorized slice.

## Supporting Material

- Protocol design: [`design.md`](design.md)
- Existing implementation proof: [`verification.md`](verification.md)
- Distribution and release plan: [`release-plan.md`](release-plan.md)
