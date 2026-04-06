# Durable Destination Map

## Typed Input Routing

| Input Type | Primary Durable Owner | Typical Secondary Owner | Default Notes |
| --- | --- | --- | --- |
| Intent | PRD | Product TDD / Unit TDD via realization pointers | Validate claim impact before technical realization |
| Constraint | Product TDD / Unit TDD | Deployment when runtime contract changes | Preserve PRD behavior unless renegotiated |
| Reality | Tasks first, then local AGENTS tripwire | Product TDD / Unit TDD / Deployment if stable truth emerges | No evidence, no modification |
| Artifact | Tasks or local workspace | None by default | Promote only if reuse and stability are proven |

## Durable Truth Types

| Candidate Truth Type | Durable Owner | Typical Location |
| --- | --- | --- |
| Product what and why | PRD | docs/10-prd/* |
| Cross-unit technical truth | Product TDD | docs/20-product-tdd/* |
| Logical structure inside a unit | Unit TDD | docs/30-unit-tdd/* |
| Local tactical hazards and tripwires | Local AGENTS | src/**/AGENTS.md |
| Runtime and operations runbooks | Deployment | docs/40-deployment/* |
| Ambiguous targeting conventions | Alignment | docs/15-alignment/* |
| Reusable workflows, route protocols, and ontology rules | Meta Engine | docs/00-meta/* |
| Volatile hypotheses and temporary reasoning | Tasks | tasks/* |

Promotion gate:

1. Stable across tasks
2. Expensive to rediscover
3. Not better enforced mechanically
4. Clear durable owner
