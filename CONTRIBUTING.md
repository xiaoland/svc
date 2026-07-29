# Contributing to SVC

SVC is a source-first protocol. A contribution is complete when its behavioral impact, migration obligation, and verification evidence are reviewable—not merely when code passes locally.

## Set Up and Verify

Use Python 3.11 or newer and PDM:

```console
pdm install -d -G test -G quality
pdm run lint-tests
pdm run typecheck
pdm run lint-imports
pdm run lint-workflows
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

After a fragment has merged, its path is a release-evidence ledger entry: do
not modify, rename, delete, or reuse it. The candidate tag's range from the
previous strict release tag selects only newly added fragment paths. A range
with no fragment is an internal-only PATCH release; `release:none` contributes
no release reason, but never opts a commit out of qualification.

A MAJOR fragment additionally owns one non-empty, same-slug migration note at
`src/migrations/<issue-or-pr>.md`. It gives migration steps or explicitly says
why no Consumer action applies. The note is packaged with the corpus; SVC does
not maintain a generic consumer-file migration graph.

Validate an exact PR or main candidate without changing source files:

```console
pdm run release target-qualify --commit HEAD --base origin/main
pdm run release target-qualify --commit HEAD
```

The repository release planner—not commit prefixes—takes the maximum fragment
impact, applies SVC Behavioral SemVer, verifies the exact next single bump,
and derives deterministic release notes from the tag range. The strict tag is
the version authority; no static project version, source manifest, or
CHANGELOG entry declares a future release.

## Release Boundary

`main` is SVC's only integration and release source. Do not create or target a
long-lived `develop` or release branch. Every admitted `main` commit has passed
the stable Python, quality/architecture, distribution, and release-policy
checks and is eligible for one valid future tag.

Maintainers configure these boundaries before the first release:

- Protect `main` with PR-only admission, the four stable qualification checks,
  no force-push/deletion, and an explicit narrow bypass policy.
- Protect `v*` tags from update/deletion; only the intended maintainer path
  may create a new matching tag. Lightweight and annotated forms are both
  accepted, but the remote ref must peel to exactly one commit.
- Configure the `release` environment with no required reviewer and its sole
  custom deployment policy `v*`; the protected tag is the release approval.
- PyPI Trusted Publisher for project `sustainable-vibe-coding`, repository `xiaoland/svc`, workflow `publish.yml`, and environment `release`.
- Enable repository release immutability before the first target-model release.

The release flow is intentionally sequenced:

1. A feature PR declares Behavioral SemVer with a fragment, or records `release:none`, then merges to `main`.
2. An authorized maintainer pushes one unused strict `vX.Y.Z` tag at the
   qualified commit. The tag and its peeled commit start Publish automatically;
   there is no release-preparation PR, automatic tag, source rewrite, or later
   human gate.
3. Publish verifies the tag, exact predecessor completion, and candidate
   external state; it then builds and smokes wheel/sdist once, seals a
   manifest-bound bundle, and retains it as a named 90-day Actions artifact.
4. Publish completes only missing exact PyPI files from that bundle, reads all
   PyPI hashes back, then creates one immutable GitHub Release with every
   manifest asset and `--verify-tag`.

The GitHub Release is the completion checkpoint, not the tag. A recovery must
name the exact tag. Before any external mutation, an empty candidate may build
again and an exact-complete immutable release may verify and succeed. Once any
PyPI file or GitHub draft exists, recovery must name and reuse the original
bundle; a missing, expired, or deleted artifact blocks rather than rebuilding.
An incomplete tag must recover before a newer tag may publish.
