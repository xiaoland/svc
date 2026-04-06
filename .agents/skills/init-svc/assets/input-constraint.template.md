# Route Template: Constraint

## Trigger

Use when product behavior stays the same, but technical, dependency, performance, or environment boundaries change.

## Primary Owner

- `20-product-tdd/` or `30-unit-tdd/`

## Mode Relationship

- Common overlays: Solidify, Execute, and Diagnose when reality diverges.
- Do not let mode selection blur whether the change is cross-unit or unit-local.

## Forbidden

- Do not rewrite product intent to justify an implementation decision.
- Do not hide cross-unit contract changes inside task notes only.

## Read-Do Steps

1. Restate the constraint in technical terms.
2. Identify affected units, contracts, and authority paths.
3. Update Product TDD or Unit TDD where future drift would be expensive.
4. Define verification that proves the new contract still satisfies PRD commitments.
5. Escalate if the constraint actually changes a product promise.

## Exit Criteria

- The updated technical contract is explicit.
- Verification for the constrained design is defined.
- PRD remains unchanged unless renegotiation is confirmed.
