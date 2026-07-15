# Changelog

All notable changes to the Sustainable Vibe Coding Framework are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/). Releases use SVC Behavioral SemVer: MAJOR changes required obligations, defaults, authority, task semantics, required layout, or stable machine contracts; MINOR adds backward-compatible optional capability; PATCH restores or clarifies the existing protocol without changing those contracts.

## [Unreleased]

<!-- towncrier release notes start -->

## [10.0.0] - 2026-07-15

### Behavioral breaking changes

- Replace copied SVC-managed documents and the consumer-file migration engine with a packaged on-demand corpus, plan-first project adoption, and explicit migration guidance for Consumer-owned material. (`v10`)


### Added

- **Packaged SVC corpus**: the installable `sustainable-vibe-coding` distribution ships the canonical Markdown corpus with a deterministic path catalog and local `svc lookup` command
- **Project adoption**: plan-first `svc init`, `svc status`, and `svc adopt` establish `svc.json`, a Codex operational skill, and bounded navigation anchors without taking ownership of project documentation
- **Self-update boundary**: `svc self-update` plans and applies only a supported current-interpreter pip update, separately from project adoption
- **Codex skill integration**: initialization installs `.agents/skills/svc/SKILL.md`, which teaches command selection and safe use without duplicating SVC guidance

### Changed

- **Consumer contract**: SVC guidance is queried from the installed corpus on demand instead of copied into consumer repositories
- **Repository topology**: `src/` is now canonical SVC content only; `svc_cli/` holds runtime code and `tools/` holds build/release tooling
- **Release metadata**: `src/manifest.json` records corpus version, Behavioral SemVer impact, and migration-guide policy rather than a consumer-file inventory
- **Major-release guidance**: future major releases require a packaged migration guide or explicit non-applicability declaration, while consumers retain the judgment and writes for their own material

### Removed

- **Managed-document installer**: SVC-managed consumer copies, `.svc/state.json`, digest tracking, consumer-file migration graph, and `svc migrate`
- **Ambiguous source layout**: Python runtime and build tools no longer live below canonical `src/`

### Migration

This is the first unreleased v10 release shape. No v10 package, tag, or GitHub Release exists, so there is no published v10 consumer state to migrate. Future published major releases provide lookup migration guidance for Consumer-owned material before `svc adopt` records the new baseline.

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
[10.0.0]: https://github.com/xiaoland/svc/releases/tag/v10.0.0
