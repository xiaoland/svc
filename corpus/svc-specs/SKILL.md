---
name: svc-specs
description: "Maintain the canonical owner of durable project knowledge. Use when project work establishes or changes product commitments, cross-unit technical contracts, unit-internal design, operational knowledge, local Agent instructions, or coordination extensions; when a durable claim needs an owner; or when deciding whether code, configuration, schemas, and tests make a new document unnecessary."
metadata: {"version": "16.0.2"}
---

# Specifications

## Find the Existing Authority

Identify the durable claim and its consumer, then find its existing owner. Prefer source, configuration, schema, tests, assertions, or automation that enforce the fact. Use the table to select only references whose admission rules match; do not create a document family by default.

| Truth | Durable owner | Admission |
| --------------------------------------------------------------- | -------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Mechanically enforceable implementation fact | source, configuration, schema, test, assertion, or automation | prefer whenever it can prevent drift directly |
| Product promise, behavior, rule, scope, or business language | [Product Requirement Document](references/prd.md) | keep a minimal Product owner; split only for a distinct consumer or cadence |
| Cross-unit authority, topology, or compatibility contract | [Product TDD](references/product-tdd.md) | another unit must rely on it to interoperate safely |
| Expensive internal invariant of one logical unit | [Unit TDD](references/unit-tdd.md) | it survives refactors and is not cheaply enforced or recovered |
| Repeated fragile seam in a physical subtree | nearest local `AGENTS.md` | nearby instructions and checks are likely to prevent recurrence |
| Runtime, packaging, observability, migration, or recovery truth | [Deployment](references/deployment.md) | operational behavior is non-trivial |
| Repository development, contribution, or release workflow | root `AGENTS.md`, `CONTRIBUTING.md`, executable configuration, or release source | keep the instruction at the entry used by its consumer |

A Unit is the smallest independently deliverable or deployable responsibility, such as an application, service, or library. The table assigns ownership, not a required document ladder; update only owners whose claims changed.

## Maintain the Claim and Its Projections

Before durable mutation, establish the authorized effect, owner, affected consumers, invariants, and proportionate verification. Finding an owner grants no write permission. Ask the Human for missing Product intent or authority; continue independent authorized work.

Add a durable surface only when it has stable useful content, a consumer, costly rediscovery or risk, one canonical owner, and no cheaper executable authority. Keep provisional findings, decisions, active Plans, evidence, and task artifacts in the Packet, not as durable truth.

Update the canonical owner, then its projections. Return the owner and consistency checks, or explain why no new document is needed. Stop when the changed claim and its projections agree; other Task obligations remain.

Use the [root instruction asset](assets/AGENTS.root.template.md) to establish a Consumer project's Agent entry. Select other assets through the applicable reference; an available template does not justify a new owner.

## Extensions

Extensions add optional coordination contracts, not authority or replacements for core owners. Use them only when their admission rules hold; mono-repository work and ordinary ownership remain the default.

- [Alignment](references/alignment.md) addresses repeated costly coordination drift in references, boundaries, operations, state, or evidence after normal owners and stable anchors are already insufficient.
- [Multi-repo](references/multi-repo.md) addresses one product spanning repositories when shared truth otherwise drifts and freshness can be enforced mechanically.

An extension does not own Product/Technical/runtime truth, evidence, Working Methods, or acceptance. Do not create an extension for a one-off Task or to hide an unresolved core owner.

## Authority and Task Continuity

Recover the claim's intended benefit. Human intent, preferences, permissions, material trade-offs, and acceptance remain Human authority; factual and solution claims remain open to evidence and reasoning. Continue safe investigation; ask only for consequential missing Human input as the smallest decision-ready issue. This Skill grants no write, delegation, external-effect, or acceptance authority.

For every non-trivial Task, recover its Packet or create the smallest `packet.md` at the project's authorized location. Preserve objective, authority and constraints, current facts, next action, and completion evidence. An invocation or Child Assignment creates no competing Task or Packet; return state changes to the Task owner. Discover `svc-task-packet` by name when recovery or state organization needs guidance. Other Skills are optional, not prerequisites; use qualified project mechanisms and report actual capability or authority gaps without relaxing obligations.
