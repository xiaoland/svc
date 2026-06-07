# Minimal Filesystem

The framework should start minimal and expand only with real pressure.

Single-repo remains the default startup shape. Topology extensions should be added only when one product truly outgrows one codebase or one worktree.

## Minimal Form

Use this form as the default startup shape.

- Root AGENTS.md as a typed dispatcher plus ontology cheat sheet
- docs/00-meta/ for input routes, mode SOPs, and the on-demand concept dictionary
- docs/10-prd/ for product truth and business glossary
- tasks/ as the agent-owned, task-local workspace

```text
/
|-- AGENTS.md
|-- docs/
|   |-- 00-meta/
|   |   |-- input-intent.md
|   |   |-- input-constraint.md
|   |   |-- input-reality.md
|   |   |-- input-artifact.md
|   |   |-- mode-a-explore.md
|   |   |-- mode-b-solidify.md
|   |   |-- mode-c-execute.md
|   |   |-- mode-d-diagnose.md
|   |   `-- concepts.md
|   `-- 10-prd/
|       |-- index.md
|       `-- glossary.md
`-- tasks/
```

## Expanded Single-Repo Form

Expand only when complexity justifies additional durable memory.

- docs/15-alignment/
- docs/20-product-tdd/
- docs/30-unit-tdd/
- docs/40-deployment/
- src/**/AGENTS.md for local tactical hazards and recurrence tripwires

Under docs/10-prd/, use this shape:

- `_drivers/` as upstream pressure sources
- `behavior/` as core product commitments
- `domain-structure/` as derived semantic stabilization
- `glossary.md` as the business-owned vocabulary boundary

```text
/
|-- AGENTS.md
|-- docs/
|   |-- 00-meta/
|   |-- 10-prd/
|   |-- 15-alignment/
|   |-- 20-product-tdd/
|   |-- 30-unit-tdd/
|   `-- 40-deployment/
|-- tasks/
`-- src/
    `-- a-module/
        |-- AGENTS.md             # for local tactical hazards and tripwires
        ...
```

```text
docs/10-prd/
|-- index.md
|-- glossary.md
|-- _drivers/
|-- behavior/
`-- domain-structure/
```

Notes:

- `docs/00-meta/concepts.md` owns framework ontology only.
- `docs/10-prd/glossary.md` owns business/domain language only.
- Input route docs and mode SOPs are orthogonal: route decides ownership, mode decides how to work.
- Task packet shapes are flexible, but every non-trivial packet must keep a compact control surface with MVT anchors.
- A packet may start as `tasks/<task-id>.md`; when it grows beyond a compact control surface, prefer `tasks/<task-id>/packet.md` with supporting files split by collaboration pressure.
- Use `work/` inside a task directory for task-local scratch artifacts when needed; do not create root-level scratch files for bounded exploration.

## Optional Topology Extensions

The startup shapes above remain the default mono-repo model.

If one product spans multiple repositories and shared truth would otherwise be copied or drift, add a topology extension rather than replacing the default model wholesale.

For the multi-repo variant, see [Optional Multi-Repo Extension](multi-repo.md).
