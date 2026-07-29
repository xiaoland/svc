# Hard-cut Migration Plan

The target model becomes active in one hard cut. Earlier slices may add tested
code or stabilize interfaces, but production remains on the prepared-source
workflow until that cut. No merged state may make both release models normal
publication paths.

## Execution Status — 2026-07-29

Slices 1, 2, and the source/workflow portion of Slice 4 are implemented and
locally verified in the uncommitted working tree. They are deliberately not a
production cutover: Slice 3's GitHub controls remain unchanged and require
Sir's separate external-mutation approval plus API readback before this source
change may merge. No tag, PyPI file, or GitHub Release was created.

On 2026-07-30 Sir authorized the controls and a real `v11.0.1` acceptance
release. Readback exposed the expected bootstrap constraint: the five stable
check names do not yet exist on `main`, so the controls cannot safely be
activated until a CI-name-only bootstrap PR has merged and produced those
checks. The execution order is therefore Slice 2 bootstrap, Slice 3 controls
and failing-probe evidence, then the Slice 4 hard cut and first protected tag.

## Slice 0 — Resolve the Projection Model — Complete

Resolved in [`slice-0-decisions.md`](slice-0-decisions.md):

- PDM-Backend native dynamic SCM versioning, exact backend pin, derived
  rehearsal/release override, and build-directory catalog projection;
- append-only Markdown fragments selected by tag range, deterministic
  same-slug MAJOR migration notes, frozen CHANGELOG, and GitHub Releases as the
  future human presentation;
- one tag-time build promoted through a checked bundle, with bounded Actions
  artifact retention, repository-wide release serialization, exact-subset
  recovery, and PyPI-first immutable GitHub Release finalization.

The comparable-project benchmark in
[`release-benchmark.md`](release-benchmark.md) confirmed that build-once
artifact handoff is the stable industry pattern, while PyPI/GitHub order and
release preparation vary. For SVC it keeps the protected tag trigger, rejects
source-preparation mutations and a persistent pre-PyPI draft, and adds an
explicit completed-predecessor check before build. The protected tag remains
the sole release approval; gates used before workflow-created tags in uv/Ruff
cannot be transplanted after SVC's authority tag without creating an abandoned
version state.

Slice 0 also found that repository rules, the release-environment tag policy,
and release immutability must precede the hard cut. The original
workflow-first/rules-second plan is superseded.

Exit: one version authority, one notes source, one artifact proof, the signed
projection matrix, and exact per-slice handshakes exist. No implementation or
external state changed.

## Slice 1 — Add the Dark Release Model — Locally Complete

Scope: `tools/release.py` and `tests/test_release.py`.

- Add pure/hermetic operations that accept an explicit candidate tag and
  commit without changing current commands used by production workflows.
- Resolve and peel the exact remote tag ref to one commit, accepting
  lightweight and annotated forms without treating annotation metadata or
  signatures as a second authority.
- Resolve the previous reachable release tag and require the candidate to be
  the exact next single Behavioral SemVer bump.
- Require that immediate predecessor to be the verified legacy cutover
  baseline or an exact-complete target-model release.
- Own `v11.0.0` as a reviewed historical planner constant that bounds the first
  append-only range without becoming a future version authority.
- Select newly added fragment paths from the tag range and reject modification,
  rename, deletion, or reuse of post-cutover fragments.
- Validate summaries and deterministic MAJOR migration-note paths.
- Generate deterministic notes and tag-bound release metadata.
- Classify named-bundle retention, PyPI none/exact-subset/all/mismatch states,
  and GitHub absent/draft-subset/published/mismatch states—including exact
  tag/commit/title/notes/assets—without mutation.
- Add fixture histories for fragment, `release:none`, migration, lightweight
  and annotated tags, non-commit/invalid tags, off-main, and source-race cases.

Exit: the target release planner and state classifiers pass hermetic tests, but
no production workflow invokes them and prepared-source release remains the
only live behavior.

## Slice 2 — Freeze the Admission Interface — Locally Complete

Scope: `.github/workflows/ci.yml`, `tests/test_workflows.py`, and task-local
repository-control payload/evidence.

- Give the Python, quality/architecture, distribution, and release-policy
  checks stable unique names that will not change at cutover.
- Keep pull-request and exact-main executions visible under the same trusted
  Actions app; retain full Git history where release qualification needs it.
- Prove the proposed branch rule names only checks that have succeeded on
  `main`.
- Prepare and read-only validate the exact `main`/`v*` ruleset,
  `release`-environment `type: tag, name: v*` policy, and
  release-immutability payloads.
- Do not activate rules or switch release semantics in this slice.

Exit: stable checks are green on `main`, the future rule payload names them
exactly, and the current release path still operates unchanged.

## Slice 3 — Enforce Admission and Publication Controls Before Cutover

External scope: GitHub `main` and `v*` rules, the `release` environment, and
repository release immutability. Task evidence records the exact request and
readback; no source file is a substitute for live settings.

1. activate the `main` rule/ruleset with PR-required admission and the stable
   checks from Slice 2;
2. verify force-push, branch deletion, and unintended bypass are disabled;
3. activate `v*` update/deletion protection while retaining authorized new-tag
   creation;
4. limit the existing `release` environment to matching `v*` tag refs while
   retaining no required reviewer;
5. enable repository release immutability for future releases;
6. read back every setting and verify check source/app identity;
7. prove a deliberately failing probe PR is blocked without merging it.

The old prepared-source release remains authoritative during this slice.
External mutation requires its own explicit Impact Handshake because a wrong
check name can lock `main`.

Exit: no unqualified commit can enter `main`, release tags cannot move or be
deleted, only matching tag refs can reach the publisher environment, future
published releases are immutable, and the protected cutover PR can still run
every required check.

## Slice 4 — Atomic Release-model Cutover — Locally Ready, Externally Blocked

This is one protected PR and one merge boundary.

Version and corpus projection:

- switch `pyproject.toml` to pinned backend-native dynamic versioning;
- make `pdm_build.py` project the resolved version and catalog under
  `context.build_dir`;
- make catalog/source fallback consume an explicit distribution projection;
- remove `src/manifest.json` and its stale owners;
- prove wheel-from-sdist retains exact version/catalog identity without SCM.

Release evidence and contributor contract:

- switch fragments to append-only tag-range semantics;
- enforce same-slug migration notes for MAJOR fragments;
- freeze CHANGELOG through v11.0.0 and remove Towncrier plus the now-empty
  release dependency group;
- update `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, and `src/index.md`.

Qualification and publication:

- make PR, exact-main, and tagged-source paths call the shared release
  qualification contract under the stable Slice 2 check names;
- make Publish's sole normal trigger `push.tags: ["v*"]`;
- serialize all normal and recovery work in one repository-wide
  `svc-publish` group with `cancel-in-progress: false`;
- require the immediate predecessor's exact completed external state before a
  candidate may build;
- retain only explicit-tag retry/recovery; probe candidate external state
  before build, allow a no-run empty rebuild or exact-complete durable
  verification, require the exact prior-run bundle ID for any incomplete
  state, and verify artifact existence plus expiry;
- build/smoke/seal/attest once and retain the named bundle with explicit
  `retention-days: 90`;
- verify or complete an exact PyPI subset from that bundle and perform bounded
  post-upload filename/hash readback;
- only after all-exact PyPI readback, create the immutable GitHub Release with
  manifest-enumerated assets, `--verify-tag`, exact title, and exact notes;
- recover an interrupted exact draft subset only from the same bundle and
  require tag/target commit/title/notes/assets all to match;
- distinguish 404 from auth, API, rate-limit, network, partial, and mismatch
  failures before mutation;
- delete `release-pr.yml`, `release-tag.yml`, prepared-source commands, release
  branch behavior, automatic tag creation, and normal-path dispatch.

Exit: the merge commit passes protected target qualification, exact-main CI is
green, and the repository contains only the tag-authoritative normal path. No
tag or external release is created by the merge.

## Slice 5 — Acceptance and First Real Release

- Run the full local and GitHub verification matrix.
- Read back repository rules and required-check app identity.
- Prove current `main` needs no preparation commit, fragment cleanup, static
  future version, or CHANGELOG update.
- With separate release authorization, create the first real eligible
  `vX.Y.Z` tag at a green `main` commit.
- Observe automatic qualification/build/publication, exact PyPI readback,
  immutable GitHub Release publication, and recovery from the named bundle
  without rebuilding.

No sacrificial PyPI version or production tag is implied by implementation
approval.

## Rollback Boundaries

- Before Slice 3, revert dark code or check-name changes without changing live
  release semantics.
- If Slice 3 rules are wrong, disable only the new rule after capturing API
  evidence; do not bypass checks by pushing release code directly.
- Slice 4 is an atomic source/workflow cut. Revert it only through the
  protected PR path; never restore both normal release paths.
- A draft left by interrupted one-call finalization is recovery state. It may
  be deleted only when no PyPI file exists and the exact failed attempt has
  been diagnosed. A pushed tag or uploaded PyPI file is irreversible release
  state, not a rollback mechanism.
- If the named original bundle expires while external state is incomplete,
  automatic recovery blocks; a rebuild is not an accepted rollback or repair.
- A pushed protected tag is a release commitment. It must be completed or
  recovered before any newer tag; it is never abandoned, moved, deleted, or
  reused as a rollback.
