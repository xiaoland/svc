# Promotion Rules

Every candidate truth should pass this test before promotion into durable docs.

## 12.1 Promotion Test

Promote only if all are true:

- stable across tasks
- expensive to rediscover
- not better enforced mechanically
- has a clear durable owner

## 12.2 Durable Destination Rules

- Product what/why -> PRD
- Cross-unit technical truth -> Product TDD
- Logical structural design within a unit -> Unit TDD
- Hard local complexity and tripwires -> Local AGENTS.md near code
- Runtime and ops truth and runbooks -> Deployment
- Ambiguous targeting -> Alignment pack
- Reusable workflows and SOPs -> Meta engine (00-meta)

## Related Assets

- [Durable Destination Map](../assets/mappings/durable-destination-map.md)
