# PRD

## Core Thesis

PRD owns product intent and observable behavior. It is the default durable destination for Intent inputs.

PRD must follow this absolute rule:

- PRD is not upstream domain-driven.
- PRD is driven by market, business, constraint, and operational pressures.
- Domain boundaries are derived inside PRD as a semantic stabilizer, not a prerequisite.
- Business vocabulary lives in `10-prd/glossary.md`, not in framework meta docs.

This prevents premature hardening around domain models and keeps product intent grounded in real pressure signals.

## One-way Derivation Structure

PRD must use a one-way derivation flow:

- Drivers -> Behavior and Claims -> Domain Structure

```text
10-prd/
|-- index.md
|-- glossary.md
|-- _drivers/
|   |-- market-and-user-pressures.md
|   |-- business-and-service-objectives.md
|   |-- hard-constraints.md
|   `-- operational-realities.md
|-- behavior/
|   |-- claims.md
|   |-- capabilities.md
|   |-- workflows.md
|   |-- rules-and-invariants.md
|   `-- scope.md
`-- domain-structure/
    |-- derived-boundaries.md
    `-- cross-domain-interactions.md
```

## Layer Dependency Rule

- `_drivers/` is always upstream. Every product decision must trace back to pressure signals in this layer.
- `behavior/` is the core of PRD. It defines externally committed product behavior.
- `domain-structure/` is derived only. It may organize boundaries and semantic interactions, but must not push new obligations back into `_drivers/` or `behavior/`.
- `glossary.md` stabilizes business language for the product layer. It must not redefine framework ontology.

## Intent Route Contract

When work is classified as Intent:

1. Check whether existing product claims would be broken, weakened, or superseded.
2. Update the relevant drivers and behavior docs before changing technical realization docs.
3. Link downstream realization only after product truth is stable.

## Ontology

PRD authors and AI agents must use these terms consistently:

- Product Driver: market, business, constraint, or operational pressure that shapes product truth
- Product Claim: durable product commitment used to evaluate delivery value
- Capability: what the product can do
- Workflow: user or service observable behavior path
- Domain: semantic boundary derived after drivers and behavior are defined
- Glossary Term: a business-owned word or phrase whose meaning must stay stable across product discussions

## Claim-Centered Evaluation

`behavior/claims.md` is the bridge between business intent and implementation.

Each major claim should include:

- Claim Intent: what user/business problem it commits to solve
- Evaluation Dimensions: how success is judged
- Evidence Expectation: what logs/tests/data prove the claim
- Source Rationale: links to specific files in `_drivers/`
- Realization Pointers: links to implementation docs in `20-product-tdd/` or `30-unit-tdd/`

Default strategy:

- do not introduce hard numeric gates unless explicitly required

## PRD Layer Purity (Anti-pattern Guardrail)

PRD must not manage implementation details outside product truth. Do not encode:

- internal mechanism ordering
- module ownership topology
- wire transport internals
- local technical contracts or interface details

These belong to:

- `20-product-tdd/` for cross-unit technical truth
- `30-unit-tdd/` for unit-level architecture and contracts
- `40-deployment/` for runtime and operations truth

## Related Assets

- [PRD File Set Template](../assets/prd-file-set.template.md)
