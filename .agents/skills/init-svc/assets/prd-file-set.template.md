# PRD File Set Template

## Directory Layout

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

## index.md

- one-way derivation statement: Drivers -> Behavior -> Domain Structure
- scope of this PRD package:
- links to all sub-files:

## glossary.md

- term:
- canonical business meaning:
- user-visible or business lifecycle language:
- notes on ambiguity with framework terms:

## _drivers/market-and-user-pressures.md

- market pressure:
- user pressure:
- urgency and tradeoff:

## _drivers/business-and-service-objectives.md

- business objective:
- service objective:
- success rationale:

## _drivers/hard-constraints.md

- compliance or legal:
- budget or staffing:
- platform or dependency limit:

## _drivers/operational-realities.md

- existing system limitation:
- runtime reality:
- migration dependency:

## behavior/claims.md

For each major claim, use this block:

- claim title:
- claim intent:
- evaluation dimensions:
- evidence expectation:
- source rationale (links to `_drivers/*`):
- realization pointers (links to `20-product-tdd/*` or `30-unit-tdd/*`):
- impact on existing claims:

Default policy:

- no hard numeric gates unless explicitly required

## behavior/capabilities.md

- capability:
- related claim(s):
- non-goal:

## behavior/workflows.md

- actor:
- trigger:
- normal flow:
- exception flow:
- observable outcome:

## behavior/rules-and-invariants.md

- rule or invariant:
- rationale:
- violation impact:
- linked claim(s):

## behavior/scope.md

- in scope:
- out of scope:
- open question:

## domain-structure/derived-boundaries.md

- derived domain boundary:
- derivation source (drivers/behavior references):
- boundary intent:

## domain-structure/cross-domain-interactions.md

- interaction pair:
- semantic contract:
- shared language:

Guardrails:

- `domain-structure/` cannot add new upstream obligations to `_drivers/` or `behavior/`
- `glossary.md` owns business vocabulary; framework ontology stays in `00-meta/concepts.md`
