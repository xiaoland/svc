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
- `docs/00-meta/implementation-taste.md`: load for non-trivial code design or implementation changes that shape structure, boundaries, data shape, authority flow, durable naming, abstraction, or complexity budget.
- `docs/10-prd/`: product truths and business glossary.
- `docs/15-alignment/`: optional coordination grammar for repeated drift, ambiguous targeting, or risky mutation; load only when MVT is not enough to constrain the work safely.
- `docs/20-product-tdd/`: cross-unit technical realization.
- `docs/30-unit-tdd/`: unit-local contracts and verification.
- `docs/40-deployment/`: runtime and operational truth.
- `tasks/`: agent-owned, task-local workspace for volatile planning, investigation, diagnostics, artifacts, evidence, and collaboration state; procedural and non-authoritative.
- `**/*/AGENTS.md`: when touching a directory, recursively inspect that directory and parents for local AGENTS.md. Local constraints are additive and may override generic defaults for that subtree. Add local `AGENTS.md` under complex modules when local constraints or tripwires are needed.

> When implementation reveals reusable knowledge, promote it into durable docs.
> If the repo uses a topology extension, add that extension's read paths and SOPs locally instead of bloating the default template.

## Operating Model

1. Classify the request as Intent, Constraint, Reality, or Artifact.
2. Identify the owning layer and open or update a task packet for non-trivial work.
3. Keep the task packet current when discussion, exploration, implementation friction, or verification changes the working state.
4. Choose the active mode for this slice of work: Explore, Solidify, Execute, or Diagnose.
5. Load only the route doc, mode SOP, and governing anchors needed for this work.
   - For non-trivial code design or implementation changes, load `docs/00-meta/implementation-taste.md`.
6. Search source and durable docs with volatile workspaces excluded by default.
7. Expand into alignment substrate fields only when MVT is not enough to constrain mutation safely.
8. Load topology-extension guidance only when the repo shape actually requires it.
9. Execute and verify.
10. Re-enter a different mode if the evidence state changes.
11. Promote only stable truths after verification.

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

- creative engineering is non-linear; do not model work as design -> code -> verify
- prepare verification shape as soon as a design claim is stable enough, and let it constrain Execute
- do not assume one task equals one mode
- switch modes when evidence or clarity changes
- mode selection never overrides durable ownership

Task packet guidance:

- task packets are agent-owned and may be updated, split, and reorganized by the agent inside the task boundary
- keep each packet human-agent-collaboration-oriented: readable, inspectable, and steerable by the human
- preserve a compact control surface with objective, guardrails, verification, current understanding, and next step
- split by collaboration pressure rather than by a fixed folder scheme
- keep volatile packet content out of durable docs until it passes the promotion test

Search guidance:

- when searching source or durable docs, exclude `tasks/`, `temp/`, generated output, dependency folders, virtual environments, and tool caches by default
- search those locations only when the task explicitly targets them or when recovering/reviewing task evidence

## Negotiation Triggers

Pause and ask for human input when any of these happen:

- the requested change conflicts with an existing product claim or technical contract
- blast radius crosses multiple durable owners and the correct owner is unclear
- a shortcut would damage readability, maintainability, or an explicit guardrail
- evidence is insufficient for a bug fix or architectural decision

## Global Coding Guidelines

- Preserve SSoT for durable facts, state, relationships, and decisions.
- Treat cross-boundary values by provenance: authority fact, reference, command or proposal, user-authored value, or derived projection.
- Name durable semantics directly and consistently.
- Spend complexity only for clear return; avoid premature optimization, premature abstraction, and over-application of OOP or design patterns.
