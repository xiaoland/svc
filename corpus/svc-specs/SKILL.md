---
name: svc-specs
description: "Find and maintain the canonical owner of durable project knowledge. Use when establishing or changing product commitments, cross-unit contracts, unit-internal design, operational knowledge, local Agent instructions, or admitted coordination extensions; or deciding whether code, configuration, schemas, and tests make a new document unnecessary."
---

# Specifications

If the current context does not already contain the [common SVC contract](../index.md), read it before acting. This Skill adds guidance within existing authorization; its trigger does not grant effect authority.

A Unit is the smallest responsibility that can be delivered or deployed independently, such as an application, service, or library. The nearest local `AGENTS.md` may preserve a repeated fragile seam in one physical subtree.

## Find the Existing Authority

First identify the durable claim and its consumer, then search the project's existing owners. Prefer source, configuration, schema, test, assertion, or automation when it can enforce the fact directly. Use the registry below to choose only the reference whose admission rule matches the claim; do not generate a document family by default.

Update the canonical owner before repairing its projections. Preserve provisional findings and active work in the [Task Packet](../svc-task-packet/SKILL.md) rather than promoting them to durable truth. Return the updated owner and relevant consistency checks, or the reason no new durable document is warranted. Stop when the changed claim and its dependent projections agree; missing Product intent or mutation authority goes back to the Human under the common contract.

Use the [root instruction asset](assets/AGENTS.root.template.md) when establishing a Consumer project's Agent entry. Choose other assets only through the applicable reference; their presence does not admit a new owner.

| Truth | Durable owner | Admission |
| --------------------------------------------------------------- | -------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Mechanically enforceable implementation fact | source, configuration, schema, test, assertion, or automation | prefer whenever it can prevent drift directly |
| Product promise, behavior, rule, scope, or business language | [Product Requirement Document](references/prd.md) | keep a minimal Product owner; split only for a distinct consumer or cadence |
| Cross-unit authority, topology, or compatibility contract | [Product TDD](references/product-tdd.md) | another unit must rely on it to interoperate safely |
| Expensive internal invariant of one logical unit | [Unit TDD](references/unit-tdd.md) | it survives refactors and is not cheaply enforced or recovered |
| Repeated fragile seam in a physical subtree | nearest local `AGENTS.md` | nearby instructions and checks are likely to prevent recurrence |
| Runtime, packaging, observability, migration, or recovery truth | [Deployment](references/deployment.md) | operational behavior is non-trivial |
| Repository development, contribution, or release workflow | root `AGENTS.md`, `CONTRIBUTING.md`, executable configuration, or release source | keep the instruction at the entry used by its consumer |

Before adding a durable surface, require stable useful content, a real consumer, expensive rediscovery or risk, one canonical owner, and no cheaper executable authority. Keep evidence, provisional decisions, active Plans, and bounded artifacts in the [Task Packet](../svc-task-packet/SKILL.md).

Product Requirement Document owns what and why. Product TDD owns admitted cross-unit technical contracts. Unit TDD owns admitted unit-internal design. Deployment owns operational reality. These are semantic projections, not a required document ladder; one change updates only the owners whose claims actually changed.


## Extensions

Extensions are optional, they add pressure-specific coordination contracts without replacing the core owner model or common collaboration contract. Use one only when its admission rule is satisfied; mono-repository work and ordinary semantic ownership remain the default.

- [Alignment](references/alignment.md) addresses repeated costly coordination drift in references, boundaries, operations, state, or evidence after normal owners and stable anchors are already insufficient.
- [Multi-repo](references/multi-repo.md) addresses one product spanning repositories when shared truth otherwise drifts and freshness can be enforced mechanically.

An extension does not own Product/Technical/runtime truth, evidence, Working Methods, or acceptance. Do not create an extension for a one-off Task or to hide an unresolved core owner.
