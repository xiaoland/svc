# Changelog

All notable changes to the Sustainable Vibe Coding Framework are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/). Releases use SVC Behavioral SemVer: MAJOR changes required obligations, defaults, authority, task semantics, required layout, or stable machine contracts; MINOR adds backward-compatible optional capability; PATCH restores or clarifies the existing protocol without changing those contracts.

## [Unreleased]

<!-- towncrier release notes start -->

### Added

- **Versioned consumption**: installable `sustainable-vibe-coding` distribution with a stable `svc` console command
- **Release manifest**: machine-readable artifact identity, file authority, target, action, digest or generator, version, and behavioral impact
- **Consumer state**: Generated `.svc/state.json` records installed provenance, managed digests, applied migrations, exact plan digest, and verification result
- **Safe migration engine**: default dry-run, exact plan-digest apply, adjacent sequential steps, immutable snapshot preconditions, shadow-tree postconditions, persistent commit journal, automatic same-process or next-invocation recovery, and stable JSON evidence
- **Migration fixtures**: clean v9.8 migration, Consumer-owned blockers, managed drift, stale plans, staged failure, rollback, and idempotent reapply

### Changed

- **Implementation taste**: clarified data-shape-first design judgment and measured optimization before adding clever algorithms or generalized machinery
- **Implementation taste surface**: condensed the document without changing its trigger or core authority, provenance, naming, data-shape, complexity, and verification principles
- **Minimal consumer kernel**: reduced the default durable shape to root instructions, one working protocol, implementation taste, and one product-truth document
- **Working protocol**: consolidated input lenses, owner resolution, working postures, the five-field task control surface, mutation permission, verification, and documentation quality under one canonical owner
- **Task lifecycle**: made task workspaces disposable under project-owned retention with no required README, archive, or deletion-time promotion review
- **Owner admission**: made Product TDD, Unit TDD, local instructions, Deployment, Alignment, and multi-repo explicitly pressure-driven instead of default placeholders
- **Monolith validation**: missing local Markdown paths and fragments now fail the build instead of being skipped
- **Consumer adoption**: replaced manual copy instructions with version-addressable `status`, `init`, and `migrate` commands
- **Version authority**: unified the framework and Python distribution at `10.0.0`
- **Consumer layout**: retained four durable knowledge documents and added Generated `.svc/state.json` as non-authoritative installation evidence

### Removed

- **Route and mode documents**: replaced the four input-route and four mode files with `docs/00-meta/working-protocol.md`
- **Duplicate framework surfaces**: removed the filesystem, ontology, promotion-map, migration-guide, and sequence documents after moving current claims to their canonical owners
- **Unsupported agent surfaces**: removed the stale repo skills and installable Codex agent definitions rather than maintaining divergent protocol copies

### Migration

For consumers based on v9.8, install the target CLI and plan the explicit source transition:

```text
svc migrate <repo> --from-version 9.8.0 --to 10.0.0
```

1. Inspect the dry-run blockers. v9.8 has no installed digests, so the CLI never silently removes unknown route, mode, or concepts files.
2. Update Consumer-owned root instructions to reference `working-protocol.md`, `implementation-taste.md`, and `docs/10-prd/README.md`; consolidate product truth at that path without surrendering consumer ownership.
3. Inspect and remove or relocate obsolete v9.8 protocol files. Preserve any still-useful local claim in its actual owner.
4. Rerun the migration plan. It recognizes the released v9.8 implementation-taste digest, refuses local managed drift, and installs the two v10 managed protocol files.
5. Apply only the new exact plan digest, then run `svc status <repo>` and require a healthy result.
6. Convert active task packets to Objective, Guardrails, Verification, Current Truth, and Next Step. Apply root retention directly; do not add archives or deletion-time promotion review.

## [9.8.0] - 2026-06-07

### Added

- **Agent-owned task workspaces**: task packets are now explicit task-local workspaces for volatile reasoning, exploration, evidence, and human-agent collaboration state
- **Progressive poly-file task packets**: task packets may start as single files and split into directories when collaboration pressure requires separate state, evidence, decisions, verification, or temporary work surfaces
- **Search isolation defaults**: ordinary source and durable-doc search now excludes volatile workspaces, generated output, dependencies, caches, and virtual environments by default
- **Implementation taste**: non-trivial code design and implementation changes now have language- and tech-stack-neutral guidance for SSoT, trust and provenance, durable semantic naming, and complexity ROI

### Changed

- **Task packet semantics**: task packets now preserve a compact human-inspectable control surface instead of behaving like append-only task notes
- **Mode composition semantics**: creative engineering is now explicit as a non-linear loop where design formation, verification preparation, implementation shape, execution, and diagnosis can reshape each other

## [9.5.0] - 2026-04-04

### Added

- **Typed input taxonomy**: every external perturbation is classified as Intent, Constraint, Reality, or Artifact before any durable update or code change
- **Minimal viable task protocol**: non-trivial task packets now require Objective & Hypothesis, Guardrails Touched, and Verification anchors
- **Progressive ontology system**: root AGENTS carries a cheat sheet while `00-meta/concepts.md` becomes the on-demand system dictionary
- **Mode overlay model**: Explore, Solidify, Execute, and Diagnose remain available as reusable SOPs and mind-patterns that can be revisited within the same task

### Changed

- **Dispatcher mental model**: routing now starts from input type and blast radius; Mode Dispatch remains as a secondary SOP layer instead of the sole front-door dispatcher
- **Business vocabulary boundary**: business terms move to `10-prd/glossary.md`, separate from framework ontology
- **Reality workflow hardening**: bug work stays evidence-first and records recurrence tripwires in local `AGENTS.md`
- **Task layer upgrade**: exploration fields are now optional scaffolding rather than mandatory ceremony

## [9.4.0] - 2026-04-04

### Changed

- **PRD restoration baseline**: PRD now follows one-way derivation from `_drivers/` to `behavior/` to `domain-structure/`
- **Claim-centered PRD**: major product claims now require intent, evaluation dimensions, evidence expectation, source rationale, and realization pointers
- **PRD purity boundary**: implementation details are explicitly delegated to Product TDD, Unit TDD, and Deployment layers

## [9.3.0] - 2026-04-04

### Added

- **Pacing Layers**: Isolate architectural structure (slow-moving) from tactical hazards (fast-moving) to maintain clarity across teams and time scales
- **Dispatcher Pattern**: Dynamically load mutually exclusive (MECE) workflows without bloating the context window

### Changed

- **Evidence-first diagnosis**: Strict read-only troubleshooting before any fix attempts

## [9.2.0]

### Added

- **Colocation principle**: How to colocate complexity-dissolving memory as close to the target code as possible to ensure agents automatically consume it

## [9.1.0]

### Added

- **Dynamic navigation framework**: How agents should dynamically navigate ambiguity without falling into rigid waterfall processes or chaotic guesswork

[Unreleased]: https://github.com/xiaoland/svc
[9.8.0]: https://github.com/xiaoland/svc/releases/tag/v9.8.0
[9.5.0]: https://github.com/xiaoland/svc/releases/tag/v9.5.0
[9.4.0]: https://github.com/xiaoland/svc/releases/tag/v9.4.0
[9.3.0]: https://github.com/xiaoland/svc/releases/tag/v9.3.0
[9.2.0]: https://github.com/xiaoland/svc/releases/tag/v9.2.0
[9.1.0]: https://github.com/xiaoland/svc/releases/tag/v9.1.0
