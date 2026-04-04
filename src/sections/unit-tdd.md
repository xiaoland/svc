# Unit TDD and Local Context

v9.3 uses pacing layers to separate logical design from physical placement.

## 9.1 Unit TDD (30-unit-tdd) -> Structure

- Role: logical architecture of a complex unit
- Stability: survives directory refactors
- Contents: cross-submodule constraints, internal technology choices, high-level naming

## 9.2 Local Context (src/**/AGENTS.md) -> Stuff

- Role: colocated tactical memory at the danger zone
- When to create: non-obvious state ownership, concurrency risk, subtle failure semantics, repeated regressions
- Contents: inviolable invariants, authority paths, hazards, local mapping handles

## Related Assets

- [Local AGENTS Template](../assets/templates/AGENTS.local.template.md)
- [Pacing Layers Map](../assets/mappings/pacing-layers-map.md)
