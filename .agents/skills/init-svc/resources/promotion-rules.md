# Promotion Rules

Every candidate truth should pass this test before promotion into durable docs.

## 12.1 Promotion Test

Promote only if all are true:

- stable across tasks
- expensive to rediscover
- not better enforced mechanically
- has a clear durable owner

## 12.2 Default Destination by Input Type

- Intent -> PRD first, then downstream realization links if needed
- Constraint -> Product TDD or Unit TDD, depending on blast radius
- Reality -> task evidence first, then local AGENTS tripwire and any stable technical contract updates
- Artifact -> stay in tasks or local workspace unless a reusable pattern clearly emerges

## 12.3 Durable Destination Rules

- Product what/why -> PRD
- Cross-unit technical truth -> Product TDD
- Logical structural design within a unit -> Unit TDD
- Hard local complexity and tripwires -> local `AGENTS.md` near code
- Runtime and ops truth and runbooks -> Deployment
- Ambiguous targeting -> Alignment pack
- Reusable workflows, route protocols, and ontology rules -> Meta engine (`00-meta`)

## Related Assets

- [Durable Destination Map](./durable-destination-map.md)
