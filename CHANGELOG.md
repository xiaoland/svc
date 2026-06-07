# Changelog

All notable changes to the Sustainable Vibe Coding Framework are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Agent-owned task workspaces**: task packets are now explicit task-local workspaces for volatile reasoning, exploration, evidence, and human-agent collaboration state
- **Progressive poly-file task packets**: task packets may start as single files and split into directories when collaboration pressure requires separate state, evidence, decisions, verification, or temporary work surfaces
- **Search isolation defaults**: ordinary source and durable-doc search now excludes volatile workspaces, generated output, dependencies, caches, and virtual environments by default

### Changed

- **Task packet semantics**: task packets now preserve a compact human-inspectable control surface instead of behaving like append-only task notes

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

[Unreleased]: https://github.com/yourusername/svc
[9.5.0]: https://github.com/yourusername/svc/releases/tag/v9.5.0
[9.4.0]: https://github.com/yourusername/svc/releases/tag/v9.4.0
[9.3.0]: https://github.com/yourusername/svc/releases/tag/v9.3.0
[9.2.0]: https://github.com/yourusername/svc/releases/tag/v9.2.0
[9.1.0]: https://github.com/yourusername/svc/releases/tag/v9.1.0
