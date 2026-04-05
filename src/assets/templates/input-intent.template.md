# Route Template: Intent

## Trigger

Use when the business wants new behavior, scope, policy, or strategy.

## Primary Owner

- `10-prd/`

## Mode Relationship

- Common overlays: Explore, Solidify, Execute.
- Do not assume these modes must occur in a fixed order.

## Forbidden

- Do not encode mechanism, topology, or interface details in PRD.
- Do not skip impact review against existing product claims.

## Read-Do Steps

1. Restate the intended behavior change and success signal.
2. Inspect impacted `_drivers/`, `behavior/claims.md`, workflows, scope, and `glossary.md`.
3. Update PRD so the new or changed claim is explicit.
4. Add realization pointers only after product truth is stable.
5. Promote downstream technical implications into Product TDD or Unit TDD only if needed.

## Exit Criteria

- PRD reflects the new or revised product claim.
- Impact on existing product claims is explicit.
- Business vocabulary remains consistent.
