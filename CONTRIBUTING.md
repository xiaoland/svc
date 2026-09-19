# Contributing to SVC

SVC is a source-first protocol. A contribution is complete when its behavioral impact, release note, and verification evidence are reviewable—not merely when code passes locally.

## Report Security Issues

Follow the [security policy](SECURITY.md) for suspected vulnerabilities. Do not
post exploitable details in a public issue or pull request.

## Set Up and Verify

Use Python 3.11 or newer and PDM 2.28 or newer:

```console
pdm install -d -G test -G quality
pdm run check
pdm build -p cli
pdm run svc lookup --path task-packet/
```

Canonical framework sources live under `corpus/`. The installable package uses the
workspace member layout `cli/src/svc_cli`, and its tests live under
`cli/tests`. SVC's own durable Product, technical, and runtime truth lives
under `docs/`; it is not packaged as Agent guidance.

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

Release notes use Towncrier from the PDM quality dependency group. Every user-
visible CLI or Corpus change adds one concise fragment to its owning product:

```console
printf '%s\n' 'Describe the CLI change.' > .changes/cli/123.added.md
printf '%s\n' 'Describe the Corpus change.' > .changes/corpus/123.added.md
```

Use the `added`, `changed`, `removed`, or `fixed` suffix. Choose the package
version with Behavioral SemVer:

- `major` when required obligations, defaults, authority or permission boundaries, task-packet semantics, consumer layout, stable CLI/catalog contracts, or supported capabilities change incompatibly.
- `minor` for an optional backward-compatible capability or accepted-input expansion.
- `patch` for a correction or clarification that preserves declared protocol behavior.

Changes without user-visible impact do not add a fragment. A change affecting
both products adds one fragment to each queue. Do not edit generated changelogs
in a feature pull request. `CHANGELOG.md` remains the shared history from before
the release streams were separated.

Add packaged Markdown migration guidance under `corpus/migrations/` when consumers
need release-specific steps or judgment. Migration notes are optional guidance;
SVC does not maintain a generic consumer-file migration graph.

## Release Boundary

`main` is SVC's only integration and release source. Do not create or target a
long-lived `develop` or release branch. Every admitted `main` commit has passed
the required CI checks and is eligible for a future release.

Maintainers configure these boundaries before the first release:

- Protect `main` with PR-only admission, the required CI checks, no
  force-push/deletion, and an explicit narrow bypass policy.
- Configure PyPI Trusted Publishing for the standard release workflow.
- Protect workflow-created release tags from update and deletion.

The release flow is intentionally sequenced:

1. Feature pull requests merge Markdown fragments under `.changes/cli/` or
   `.changes/corpus/`. A feature pull request that changes packaged Corpus
   content also advances `corpus/version.json` and its migration index; the
   repository check requires the content and Corpus version to move together.
2. A maintainer prepares a CLI release PR by updating the static version in
   `cli/pyproject.toml` and building its changelog:

   ```console
   pdm run towncrier build --config towncrier.cli.toml --version 15.0.0 --yes
   pdm run check
   ```

   The version must equal the package version. Merging `CLI_CHANGELOG.md`
   validates and publishes the accepted wheel under `cli-v<version>`.
3. A Corpus release PR uses the Corpus version already accepted with the
   feature changes and consumes its fragment queue:

   ```console
   pdm run towncrier build --config towncrier.corpus.toml --version 15.0.0 --yes
   pdm run check
   ```

   Merging `CORPUS_CHANGELOG.md` creates `corpus-v<version>` and its GitHub
   Release without publishing PyPI. A later CLI release carries that Corpus in
   its wheel; when immediate PyPI delivery is required, prepare both releases in
   the same PR.
