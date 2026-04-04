# Migration Guidance

## v9.1 -> v9.2

1. Add closest-to-target consumption logic to root AGENTS.md.
2. Move tactical component memory from 30-unit-tdd into src/<module>/AGENTS.md where appropriate.

## v9.2 -> v9.3

1. Create docs/00-meta and extract mode A/B/C instructions into dedicated files.
2. Refactor root AGENTS.md into a minimal dispatcher.
3. Add mode-d-diagnose.md with strict read-only and telemetry-first constraints.
4. Restore 30-unit-tdd for macro-level logical constraints, while keeping local AGENTS for micro tactical hazards.

## v9.3 -> v9.4

1. Restructure PRD from flat files to one-way derivation folders: `_drivers/`, `behavior/`, `domain-structure/`.
2. Replace `product-claims.md` with `behavior/claims.md` using claim-centered evaluation blocks.
3. Move vocabulary ownership from generic `glossary.md` into `domain-structure/vocabulary-and-lifecycle.md`.
4. Enforce PRD layer purity: move mechanism ordering, topology, wire internals, and local contracts into 20/30/40 layers.

### Related Assets

- [Root AGENTS Template](../assets/templates/AGENTS.root.template.md)
- [Mode D SOP Template](../assets/templates/mode-d-diagnose.template.md)
