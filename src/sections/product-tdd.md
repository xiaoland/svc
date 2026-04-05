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

## Related Assets

- [Product TDD File Set Template](../assets/templates/product-tdd-file-set.template.md)
