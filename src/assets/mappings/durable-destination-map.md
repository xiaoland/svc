# Durable Destination Map

| Candidate Truth Type | Durable Owner | Typical Location |
| --- | --- | --- |
| Product what and why | PRD | docs/10-prd/* |
| Cross-unit technical truth | Product TDD | docs/20-product-tdd/* |
| Logical structure inside a unit | Unit TDD | docs/30-unit-tdd/* |
| Local tactical hazards and tripwires | Local AGENTS | src/**/AGENTS.md |
| Runtime and operations runbooks | Deployment | docs/40-deployment/* |
| Ambiguous targeting conventions | Alignment | docs/15-alignment/* |
| Reusable workflows and SOPs | Meta Engine | docs/00-meta/* |
| Volatile hypotheses and temporary reasoning | Tasks | tasks/* |

Promotion gate:

1. Stable across tasks
2. Expensive to rediscover
3. Not better enforced mechanically
4. Clear durable owner
