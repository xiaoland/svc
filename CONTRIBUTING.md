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
pdm build -p svc_cli
pdm run svc lookup --path task-packet/
```

Canonical framework sources live under `src/`. The installable package uses the
workspace member layout `svc_cli/src/svc_cli`, and its tests live under
`svc_cli/tests`. SVC's own durable Product, technical, and runtime truth lives
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
or protocol-visible pull request adds one concise Markdown fragment:

```console
printf '%s\n' 'Describe the user-visible change.' > .changes/123.added.md
```

Use the `added`, `changed`, `removed`, or `fixed` suffix. Choose the package
version with Behavioral SemVer:

- `major` when required obligations, defaults, authority or permission boundaries, task-packet semantics, consumer layout, stable CLI/catalog contracts, or supported capabilities change incompatibly.
- `minor` for an optional backward-compatible capability or accepted-input expansion.
- `patch` for a correction or clarification that preserves declared protocol behavior.

Changes without user- or protocol-visible impact do not add a fragment. Do not
edit the generated `CHANGELOG.md` in a feature pull request.

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

1. Feature pull requests merge Markdown fragments under `.changes/`.
2. A maintainer prepares a release PR by updating the static version in
   `svc_cli/pyproject.toml` and building the changelog:

   ```console
   pdm run towncrier build --version 15.0.0 --yes
   pdm run check
   ```

   The version passed to Towncrier must equal the package version. The maintainer
   opens an ordinary release-preparation pull request containing both changes.
3. Merging that generated changelog triggers the standard release workflow. The
   static package version is the single release version: the workflow validates
   the changelog, builds and smoke-tests the distributions once, creates the
   matching tag, publishes through PyPI Trusted Publishing, and creates the
   GitHub Release from the generated notes.
