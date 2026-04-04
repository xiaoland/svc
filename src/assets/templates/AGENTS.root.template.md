# AGENTS.md (Root Template)

> Introduce the product / project / repository briefly.

## Respository Layout

> Only the crucial part.

```text
<!-- File tree, expand most 3 layers -->
```

## Techinical Overview

> Tech stacks; tooling; development environment setup (prefer CONTRIBUTING.md)

## Documentation

Read following documents when needed and keep them current:

- [Docs Policy](./docs/00-meta): notes for doc-system ownership and promotion rules.
- [PRD](./docs/10-prd): product truths and domain split.
- [Product TDD](./docs/20-product-tdd): cross-unit technical realization.
- [Unit TDD](./docs/30-unit-tdd): unit-local contracts and verification.
- [Deployment](./docs/40-deployment): runtime and operational truth.
- [Tasks](./tasks): volatile planning, investigation, and result workspace; procedural and non-authoritative.
- [Local AGENTS](./**/*/AGENTS.md): When touching a directory, recursively inspect that directory and parents for local AGENTS.md. Local constraints are additive and may override generic defaults for that subtree. Add local `AGENTS.md` under complex modules when local constraints are needed.

> When implementation reveals reusable knowledge, promote it into durable docs.

## Operating Model

1. Classify the request into one mode: A, B, C, or D.
2. Load the corresponding SOP from docs/00-meta/.
3. Execute the SOP.

### Mode Selection Guide

- Mode A (Explore): vague or unknown causality
- Mode B (Solidify): converging from ambiguity to durable truth
- Mode C (Execute): specific change with known causality
- Mode D (Diagnose): anomaly, outage, crash, or unclear runtime failure

## Global Coding Guidelines

- Less is more; quality over quantity; high cohesion and low coupling.
- Establish invariants at system boundaries and rely on them internally.
- Prefer abstraction only when duplication or patterns become clear.
- Source files should stay under 300 lines where practical.