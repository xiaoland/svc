# Unit TDD and Local Context

Use pacing layers to separate logical design from physical placement.

## 9.1 Unit TDD (30-unit-tdd) -> Structure

- Role: logical architecture of a complex unit
- Stability: survives directory refactors
- Contents: cross-submodule constraints, internal technology choices, high-level naming, internal contracts
- Ontology note: a Unit is a logical technical boundary, not a folder name

Unit TDD is the default durable destination when a Constraint input is local to one unit but too important to leave only in code comments or task packets.

## 9.2 Quick Boundary Check

Use Unit TDD when all are true:

- one unit can change this truth without forcing another unit to update
- the truth describes internals, naming, storage, sequencing, or internal contracts of that unit
- any external dependency is already represented by a Product TDD contract

Minimal examples:

- one service's internal DB table naming -> Unit TDD
- payload format between two services -> Product TDD

The rule is the same in mono-repo and multi-repo. Multi-repo only makes wrong placement easier to notice.

## 9.3 Local Context (src/**/AGENTS.md) -> Stuff

- Role: colocated tactical memory at the danger zone
- When to create: non-obvious state ownership, concurrency risk, subtle failure semantics, repeated regressions, fragile integration seams
- Contents: inviolable invariants, authority paths, hazards, local mapping handles, recurrence tripwires

## 9.4 Reality Route Tripwire Rule

When Reality work reveals a fragile seam:

1. Diagnose with evidence first.
2. Fix the code only after the cause is justified.
3. Add or update the nearest local `AGENTS.md` with a tripwire if future agents could easily repeat the same mistake.

A good tripwire records:

- what symptom signals the seam is being violated
- which shortcut is forbidden
- which test, assertion, log, or check should catch recurrence early

## Related Assets

- [Local AGENTS Template](../assets/templates/AGENTS.local.template.md)
- [Pacing Layers Map](../assets/mappings/durable-destination-map.md)
