# AGENTS.md (Root Template)

> Introduce the product / project / repository briefly.

## Repository Layout

> Only the crucial part.

```text
<!-- File tree, expand at most 3 layers -->
```

## Technical Overview

> Tech stacks, tooling, and development environment setup (prefer CONTRIBUTING.md for setup detail).

## Minimal Cheat Sheet

- Unit: a logical technical boundary; not the same thing as a folder.
- PRD (`docs/10-prd/`): owns business intent and observable behavior only.
- Product TDD (`docs/20-product-tdd/`): owns cross-unit technical contracts and topology.
- Unit TDD (`docs/30-unit-tdd/`): owns a unit's internal logic architecture and internal contracts.

## Documentation

Read the following documents when needed and keep them current:

- `docs/00-meta/`: typed input protocols, mode SOPs, and framework ontology.
- `docs/00-meta/concepts.md`: load only when boundary language is unclear.
- `docs/10-prd/`: product truths and business glossary.
- `docs/20-product-tdd/`: cross-unit technical realization.
- `docs/30-unit-tdd/`: unit-local contracts and verification.
- `docs/40-deployment/`: runtime and operational truth.
- `tasks/`: volatile planning, investigation, diagnostics, and artifact workspace; procedural and non-authoritative.
- `**/*/AGENTS.md`: when touching a directory, recursively inspect that directory and parents for local AGENTS.md. Local constraints are additive and may override generic defaults for that subtree. Add local `AGENTS.md` under complex modules when local constraints or tripwires are needed.

> When implementation reveals reusable knowledge, promote it into durable docs.

## Operating Model

1. Classify the request as Intent, Constraint, Reality, or Artifact.
2. Identify the owning layer and open a task packet for non-trivial work.
3. Choose the active mode for this slice of work: Explore, Solidify, Execute, or Diagnose.
4. Load only the route doc, mode SOP, and governing anchors needed for this work.
5. Execute and verify.
6. Re-enter a different mode if the evidence state changes.
7. Promote only stable truths after verification.

### Typed Input Guide

- Intent: the business wants new behavior, scope, or policy. Update PRD first.
- Constraint: business behavior is stable, but technical or environment boundaries changed. Update Product TDD or Unit TDD.
- Reality: runtime truth disagrees with expectation. Diagnose with evidence first, then add recurrence tripwires near code if needed.
- Artifact: produce a bounded intermediate deliverable. Keep it tactical unless reuse is proven.

### Mode Guide

- Explore: map unknowns, alternatives, and assumptions.
- Solidify: restate findings into explicit claims, contracts, or decisions.
- Execute: implement a clear, verified change.
- Diagnose: investigate mismatches between expected and observed reality.

Mode guidance:

- do not assume one task equals one mode
- switch modes when evidence or clarity changes
- mode selection never overrides durable ownership

## Negotiation Triggers

Pause and ask for human input when any of these happen:

- the requested change conflicts with an existing product claim or technical contract
- blast radius crosses multiple durable owners and the correct owner is unclear
- a shortcut would damage readability, maintainability, or an explicit guardrail
- evidence is insufficient for a bug fix or architectural decision

## Global Coding Guidelines

- Less is more; quality over quantity; high cohesion and low coupling.
- Establish invariants at system boundaries and rely on them internally.
- Prefer abstraction only when duplication or patterns become clear.
- Source files should stay under 300 lines where practical.
