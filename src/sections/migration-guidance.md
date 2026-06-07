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

## v9.5 -> v9.6

1. Keep mono-repo as the default startup shape and default cognitive model.
2. Add multi-repo only as a pressure-driven topology extension when shared truth no longer fits one repo cleanly.
3. Move Hub/Spoke, shared mounts, source-first mutation, and freshness rules into that optional extension instead of default templates.
4. Keep the 20/30 boundary sharp in both topologies: cross-unit contracts stay in Product TDD; one-unit internals stay in Unit TDD or local `AGENTS.md`.
5. Use a dedicated shared-doc skill to absorb submodule safety complexity when the multi-repo extension is active.

## v9.6 -> v9.7

1. Rename Alignment Pack to Alignment Substrate to emphasize a reusable coordination grammar rather than a static document bundle.
2. Treat alignment as seven coordination primitives: object, address, operation, invariants, state/context, evidence, and protocol.
3. Prefer calculable maps from stable code anchors over hand-maintained static surface maps.
4. Express alignment requests as declarative `From -> To` state diffs instead of mixed imperative instructions.
5. Bind operation verbs to verification contracts and require a pre-execution impact handshake before non-local durable mutations.

## v9.7 -> v9.8

1. Treat task packets as agent-owned, task-local workspaces rather than only task files.
2. Keep every packet human-agent-collaboration-oriented: readable, inspectable, and steerable by the human.
3. Preserve a compact control surface with MVT anchors, current understanding, and next step.
4. Allow single-file packets to grow into packet directories when collaboration pressure requires separation of state, history, evidence, decisions, temporary work, or verification.
5. Exclude volatile task workspaces, generated output, dependencies, caches, and virtual environments from ordinary source and durable-doc search by default.
6. Add `docs/00-meta/implementation-taste.md` as the durable source for language- and tech-stack-neutral implementation taste.
7. Load implementation taste for non-trivial code design or implementation changes that shape structure, boundaries, data shape, authority flow, durable naming, abstraction, or complexity budget.
8. Keep implementation taste out of individual mode ownership: modes consume it as hooks, while the Meta Engine owns the non-linear design, verification, execution, and diagnosis loop.
9. Update root AGENTS coding guidance to preserve SSoT, classify cross-boundary value provenance, name durable semantics directly, and spend complexity only for clear return.
10. Treat over-applied OOP, design patterns, generality, and premature optimization or abstraction as complexity-budget failures unless their return is proven.

### Related Assets

- [Root AGENTS Template](../assets/templates/AGENTS.root.template.md)
- [Implementation Taste](implementation-taste.md)
- [Task Packet Template](../assets/templates/task-packet.template.md)
- [Concept Dictionary Template](../assets/templates/concepts.template.md)
