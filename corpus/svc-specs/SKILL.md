---
name: svc-specs
description: "Canonical ownership and maintenance of durable project knowledge: product requirements, technical design, deployment, and local instructions. Use for every non-trivial Task."
metadata: {"version": "1.0.0"}
---

# Specifications

Use this entry for every non-trivial Task: keep durable project knowledge at its canonical owner, and admit a new durable surface only when its admission rule holds.

## Find the Existing Authority

Identify the durable claim and its consumer, then find its existing owner. Prefer source, configuration, schema, tests, assertions, or automation that enforce the fact. Use the table to select only references whose admission rules match; do not create a document family by default.

| Truth | Durable owner | Admission |
| --------------------------------------------------------------- | -------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Mechanically enforceable implementation fact | source, configuration, schema, test, assertion, or automation | prefer whenever it can prevent drift directly |
| Product promise, behavior, rule, scope, or business language | [Product Requirement Document](references/prd.md) | keep a minimal Product owner; split only for a distinct consumer or cadence |
| Cross-unit authority, topology, or compatibility contract | [Product TDD](references/product-tdd.md) | another unit must rely on it to interoperate safely |
| Expensive internal invariant of one logical unit | [Unit TDD](references/unit-tdd.md) | it survives refactors and is not cheaply enforced or recovered |
| Repeated fragile seam in a physical subtree | nearest [local `AGENTS.md`](references/local-instructions.md) | nearby instructions and checks are likely to prevent recurrence |
| Runtime, packaging, observability, migration, or recovery truth | [Deployment](references/deployment.md) | operational behavior is non-trivial |
| Visual system, design decisions, and rejected patterns of a user-facing surface | [DESIGN.md](references/design-md.md) at the project root | the surface's look is part of the product promise and drifts across sessions without a canonical owner |
| Repository development, contribution, or release workflow | root `AGENTS.md`, `CONTRIBUTING.md`, executable configuration, or release source | keep the instruction at the entry used by its consumer |

A Unit is the smallest independently deliverable or deployable responsibility, such as an application, service, or library. The table assigns ownership, not a required document ladder; update only owners whose claims changed.

## Maintain the Claim and Its Projections

Add a durable surface only when it has stable useful content, a consumer, costly rediscovery or risk, one canonical owner, and no cheaper executable authority. Keep provisional findings, decisions, active Plans, evidence, and task artifacts in the Packet, not as durable truth.

A proposed claim updates its canonical owner only on acceptance as durable truth. Update the owner, then its projections. Return the owner and consistency checks, or explain why no new document is needed. Stop when the changed claim and its projections agree; other Task obligations remain.

Organize a growing document family as a routing index plus one projection per distinct consumer or change cadence: key routes by the reader's recognizable question, give each route entry enough of the target's content to decide without loading it, and keep claims out of the index; each projection opens with its use condition. Split when a capability gains an independent consumer or cadence; merge when one loses it.

Retire a durable surface when its basis disappears: the consumer is gone, the truth became executable, or the split rationale no longer holds. Absorb surviving claims into the remaining owner and delete the rest in the change that removes the basis, not as deferred cleanup. Version control preserves history; a stale surface misleads more than a missing one.

Judge the health of durable knowledge by consumer cost: trace real questions and count hops and reading volume to a trustworthy answer, including the cost of proving an answer absent. Coverage, consistency, and adoption are not measures of health.

Use the [root instruction asset](assets/AGENTS.root.template.md) to establish a Consumer project's Agent entry. Select other assets through the applicable reference; an available template does not justify a new owner.

## Extensions

Extensions add optional coordination contracts, not authority or replacements for core owners. Use them only when their admission rules hold; mono-repository work and ordinary ownership remain the default.

- [Alignment](references/alignment.md) addresses repeated costly coordination drift in references, boundaries, operations, state, or evidence after normal owners and stable anchors are already insufficient.
- [Multi-repo](references/multi-repo.md) addresses one product spanning repositories when shared truth otherwise drifts and freshness can be enforced mechanically.

An extension does not own Product/Technical/runtime truth, evidence, Working Methods, or acceptance. Do not create an extension for a one-off Task or to hide an unresolved core owner.

## Authority and Task Continuity

Recover the claim's intended benefit. Human intent, preferences, permissions, material trade-offs, and acceptance remain Human authority; factual and solution claims remain open to evidence and reasoning. Continue safe investigation; ask only for consequential missing Human input as the smallest decision-ready issue. This Skill grants no write, delegation, external-effect, or acceptance authority.

Reuse the Task's existing state for provisional findings, decisions, and evidence; an invocation or Child Assignment creates no separate Task or Packet. Return state changes to the Task owner. Discover `svc-task-packet` when state management needs guidance. Other Skills are optional; use qualified project mechanisms and report actual capability or authority gaps without relaxing obligations.
