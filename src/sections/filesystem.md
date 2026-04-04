# Minimal Filesystem

The framework should start minimal and expand only with real pressure.

## Minimal Form

Use this form as the default startup shape.

- Root AGENTS.md as dispatcher
- docs/00-meta/ for dynamic protocols
- docs/10-prd/ for product truth
- tasks/ as entropy buffer

```text
/
|-- AGENTS.md
|-- docs/
|   |-- 00-meta/
|   |   |-- mode-a-explore.md
|   |   |-- mode-b-solidify.md
|   |   |-- mode-c-execute.md
|   |   `-- mode-d-diagnose.md
|   `-- 10-prd/
`-- tasks/
```

## Expanded Form

Expand only when complexity justifies additional durable memory.

- docs/15-alignment/
- docs/20-product-tdd/
- docs/30-unit-tdd/
- docs/40-deployment/
- src/**/AGENTS.md for local tactical hazards

Under docs/10-prd/, use the v9.4 PRD shape:

- _drivers/ as upstream pressure sources
- behavior/ as core product commitments
- domain-structure/ as derived semantic stabilization

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
        |-- AGENTS.md             # for local tactical hazards
        ...
```

```text
docs/10-prd/
|-- index.md
|-- _drivers/
|-- behavior/
`-- domain-structure/
```

