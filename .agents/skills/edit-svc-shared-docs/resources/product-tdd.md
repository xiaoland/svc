# Product TDD

## 8.1 Role of Product TDD

Product TDD is the durable technical design layer for truths spanning multiple units or repos.

It is the default durable destination when a Constraint input changes cross-unit contracts, system topology, or global authority paths while product behavior remains stable.

## 8.2 Product TDD Contents

Typical Product TDD files include:

- unit-topology.md
- system-state-and-authority.md
- cross-unit-contracts.md
- claim-realization-matrix.md

Use this layer to answer questions such as:

- which units own which state or responsibility
- how constraints reshape cross-unit interfaces
- how PRD claims are realized without changing PRD ownership
- which compatibility promises must survive refactors

## 8.3 Constraint Route Rule

When work is classified as Constraint and spans multiple units:

1. Restate the new boundary or limit in technical terms.
2. Identify which contracts or topology assumptions become invalid.
3. Update Product TDD before code if future changes would otherwise drift.
4. Keep PRD stable unless the constraint truly changes the product promise.

## 8.4 Boundary Check

Promote a technical truth into Product TDD only when both are true:

1. another unit must rely on it to interoperate safely
2. changing it would break cross-unit compatibility, authority, or topology

Keep it local when one unit can change it without forcing another unit to update.

Minimal examples:

- payload format between two services -> Product TDD
- one service's internal DB table naming -> Unit TDD or local `AGENTS.md`

If a multi-repo topology extension is active, shared Product TDD stays Hub-owned. See [Optional Multi-Repo Extension](multi-repo.md).

## Related Assets

- [Product TDD File Set Template](../assets/templates/product-tdd-file-set.template.md)
