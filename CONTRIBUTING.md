# Contributing to SVC

SVC is a source-first protocol. A contribution is complete when its behavioral impact, release note, and verification evidence are reviewable—not merely when code passes locally.

## Report Security Issues

Follow the [security policy](SECURITY.md) for suspected vulnerabilities. Do not
post exploitable details in a public issue or pull request.

## Set Up and Verify

Use Python 3.11 or newer and PDM:

```console
pdm install -d -G test -G quality
changie batch auto --dry-run
pdm run check-documents
pdm run lint-tests
pdm run typecheck
pdm run lint-imports
pdm run lint-workflows
pdm run test
pdm run build-monolith
pdm build
pdm run svc lookup --path sections/working-protocol.md
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

Release notes use Changie 1.25.1, installed separately from the Python
environment (for example, `go install github.com/miniscruff/changie@v1.25.1`).
Every user- or protocol-visible pull request runs `changie new` and selects
exactly one Behavioral SemVer kind:

```console
changie new
```

Use:

- `major` when required obligations, defaults, authority or permission boundaries, task-packet semantics, consumer layout, stable CLI/catalog contracts, or supported capabilities change incompatibly.
- `minor` for an optional backward-compatible capability or accepted-input expansion.
- `patch` for a correction or clarification that preserves declared protocol behavior.

Changie writes a tool-native YAML fragment under `changes/unreleased/`. Keep its
body concise and consumer-facing. Changes without user- or protocol-visible
release impact do not add a fragment. Do not edit the generated `CHANGELOG.md`
in a feature pull request.

Add packaged Markdown migration guidance under `src/migrations/` when consumers
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

1. Feature pull requests merge tool-native YAML fragments to
   `changes/unreleased/`.
2. A maintainer prepares a release with Changie 1.25.1:

   ```console
   version=$(changie next auto)
   changie batch "$version" --allow-no-changes=false \
     --move-dir "fragments/$version"
   pdm run build-release-projections
   changie merge
   ```

   The maintainer opens an ordinary release-preparation pull request containing
   the batch result and generated `CHANGELOG.md`.
3. Merging that generated changelog triggers the standard release workflow. The
   batched Changie version is the single release version: the workflow constructs
   its matching tag and PDM SCM package version, builds the distributions,
   installs and smoke-tests them, publishes through PyPI Trusted Publishing,
   and creates the GitHub Release from the generated notes.
