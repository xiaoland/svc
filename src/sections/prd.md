# Product Truth

Product truth owns what the product is for, what users or external systems can observe, which rules and scope apply, and why those commitments exist. It does not own implementation topology, internal sequencing, wire details, or local code contracts.

## Minimal Shape

Start with one `docs/10-prd/README.md` containing:

- product purpose and current pressure
- product claims and evaluation expectations
- capabilities and observable workflows
- rules, invariants, and scope boundaries
- business terms whose meaning must remain stable

Use [the product-truth template](../assets/templates/product-truth.template.md). Do not create an empty glossary or directory family.

## Derivation

Keep the reasoning direction explicit:

```text
drivers -> product behavior and claims -> derived domain structure
```

Market, user, business, hard-constraint, and operational pressures are upstream. Domain boundaries may stabilize language after behavior is understood, but they cannot invent new product obligations.

For each material claim, preserve enough of the following to evaluate it:

- the problem or outcome being committed to
- the driver or rationale
- observable success dimensions
- expected evidence

Do not add hard numeric gates unless the product actually requires them.

## Ownership Boundary

An Intent lens often points here, but only when the product promise changes. A dependency, environment, or implementation constraint can leave product truth unchanged. When product truth does change, update it before describing downstream realization.

Use Product TDD for admitted cross-unit technical contracts, Unit TDD for admitted internal unit design, and Deployment for non-trivial runtime or recovery truth.

## Expansion Rule

Split the single file only when real content has distinct consumers or change cadence. Common pressure-driven splits are drivers, behavior, scope, glossary, and derived domain structure. Every new file needs an owner and content at creation time.
