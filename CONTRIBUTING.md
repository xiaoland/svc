# Contributing to SVC

SVC is a source-first protocol. A contribution is complete when its behavioral impact, migration obligation, and verification evidence are reviewable—not merely when code passes locally.

## Set Up and Verify

Use Python 3.11 or newer and PDM:

```console
pdm install -d -G release
pdm run test
pdm run build-monolith
pdm build
pdm run svc lookup --name 'sections/working-protocol\\.md'
```

Canonical framework sources live under `src/`. Do not edit `build/monolith.md`; regenerate it with `pdm run build-monolith`.

## Commit Messages

Use this grammar:

```text
feat|fix|ref|docs|chore(<scope>): <imperative summary>
```

Keep the first line concise. Add body bullets when they preserve expensive context, constraints, or verification results.

Accepted examples:

```text
feat(lookup): add an optional local corpus capability
docs(protocol): define project adoption authority
ref(cli): isolate packaged resource lookup
```

Rejected examples include `update files` (no type, scope, or intent), `feat: migration` (no scope), and `fix(cli): fixed status` (not imperative).

Commit type is navigation metadata. It never determines release impact or the next version.

## Declare Behavioral Impact

Every user- or protocol-visible pull request adds one Markdown fragment:

```text
changes/<issue-or-pr>.major.md
changes/<issue-or-pr>.minor.md
changes/<issue-or-pr>.patch.md
```

Use:

- `major` when required obligations, defaults, authority or permission boundaries, task-packet semantics, consumer layout, stable CLI/catalog contracts, or supported capabilities change incompatibly.
- `minor` for an optional backward-compatible capability or accepted-input expansion.
- `patch` for a correction or clarification that preserves declared protocol behavior.

The fragment contains one concise, consumer-facing statement. Use the issue or pull-request number when one exists; a short lowercase identifier is acceptable before a number exists. Contributor-internal changes may omit a fragment only when the pull request explicitly records `release:none`.

Validate fragments and inspect the calculated version without changing files:

```console
pdm run release check
pdm run release plan
pdm run towncrier build --draft --version 10.0.0
```

Towncrier renders release notes. The repository release planner—not commit prefixes—takes the maximum fragment impact, applies SVC Behavioral SemVer, and verifies version and migration-guidance obligations. A MAJOR release must declare either a packaged Markdown guide under `src/migrations/` or an explicit `not-applicable` reason; it never registers a consumer-file migration graph.

For an already predeclared MAJOR release, the declaration lives in `behavioral_impact.migration`. When a MAJOR is still only a pending fragment, stage the declaration under a top-level `release_policy.migration` object in `src/manifest.json`; `release prepare` transfers it into the prepared release metadata and removes the staging field. This prevents an old release's migration rationale from silently becoming the next release's rationale.

## Release Boundary

`main` is SVC's only integration and release source. Do not create or target a long-lived `develop` branch. Feature branches merge into `main`; `release/svc` is an automation-owned, short-lived release-candidate branch, never a second integration line.

Maintainers configure these boundaries before the first release:

- Enable **Allow GitHub Actions to create and approve pull requests** in the repository's Actions settings. The Release PR job uses only its built-in, short-lived `GITHUB_TOKEN`, explicitly scoped to `contents: write` and `pull-requests: write`; ordinary workflows may retain a read-only default token.
- Protected GitHub environment `release`, which gates publication.
- PyPI Trusted Publisher for project `sustainable-vibe-coding`, repository `xiaoland/svc`, workflow `publish.yml`, and environment `release`.

The release flow is intentionally sequenced:

1. A feature PR declares Behavioral SemVer with a fragment, or records `release:none`, then merges to `main`.
2. The Release PR workflow consumes pending fragments and creates or updates `release/svc` with `GITHUB_TOKEN`. Its opened or updated pull-request workflows wait for a maintainer with write access to select **Approve workflows to run**; then review its version, changelog, migration declaration, release reasons, lockfile, and CI together.
3. Merging that Release PR prepares the candidate. Publish approval in the protected `release` environment builds and attests the wheel and sdist, creates `v<version>` and a draft GitHub Release, publishes those same artifacts to PyPI through Trusted Publishing, then publishes the GitHub Release.

The GitHub Release is the completion checkpoint, not the tag. If a publish is interrupted, run `Publish` with `workflow_dispatch` only after diagnosing the state: an absent tag creates a release from `main`; a tag without a Release rebuilds that tag; a draft Release verifies and reuses its immutable uploaded assets. A published Release is left unchanged.
