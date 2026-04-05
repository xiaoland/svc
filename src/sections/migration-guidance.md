# Migration Guidance

## v9.1 -> v9.2

1. Add closest-to-target consumption logic to root AGENTS.md.
2. Move tactical component memory from `30-unit-tdd` into `src/<module>/AGENTS.md` where appropriate.

## v9.2 -> v9.3

1. Create `docs/00-meta` and extract mode A/B/C instructions into dedicated files.
2. Refactor root AGENTS.md into a minimal dispatcher.
3. Add `mode-d-diagnose.md` with strict read-only and telemetry-first constraints.
4. Restore `30-unit-tdd` for macro-level logical constraints, while keeping local AGENTS for micro tactical hazards.

## v9.3 -> v9.4

1. Restructure PRD from flat files to one-way derivation folders: `_drivers/`, `behavior/`, `domain-structure/`.
2. Replace `product-claims.md` with `behavior/claims.md` using claim-centered evaluation blocks.
3. Move vocabulary ownership from generic `glossary.md` into `domain-structure/vocabulary-and-lifecycle.md`.
4. Enforce PRD layer purity: move mechanism ordering, topology, wire internals, and local contracts into 20/30/40 layers.

## v9.4 -> v9.5

1. Replace mode-only front-door dispatch in root AGENTS.md with typed input classification: Intent, Constraint, Reality, Artifact.
2. Keep Mode Dispatch as reusable SOPs, but decouple it from task ownership and linear one-task-one-mode assumptions.
3. Combine `docs/00-meta/input-*.md` with `docs/00-meta/mode-*.md` plus `docs/00-meta/concepts.md`.
4. Upgrade task notes into MVT task packets with mandatory anchors and optional exploration scaffolding.
5. Move business vocabulary ownership from `10-prd/domain-structure/vocabulary-and-lifecycle.md` to `10-prd/glossary.md`.
6. Require Reality workflows to stay evidence-first and record recurrence tripwires in the nearest local `AGENTS.md` when warranted.

### Related Assets

- [Root AGENTS Template](../assets/templates/AGENTS.root.template.md)
- [Task Packet Template](../assets/templates/task-packet.template.md)
- [Concept Dictionary Template](../assets/templates/concepts.template.md)
