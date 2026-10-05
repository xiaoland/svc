---
name: svc-taste
description: "Apply consequence-based judgment to real design and implementation trade-offs. Use when alternatives affect authority, data, state, boundaries, naming, dependencies, abstraction, performance, product experience, or future change cost, including choices uncovered while implementing. Keep project truth and Human preferences distinct from rebuttable heuristics."
---

# Taste and Design Judgment

If the current context does not already contain the [common SVC contract](../index.md), read it before acting. This Skill adds guidance within existing authorization; its trigger does not grant effect authority.

Taste is compressed consequence knowledge used when several plausible designs need judgment beyond owned Product or Technical truth. Use it for local Design or Implementation pressure; do not load a global maxim catalog or apply taste as universal law.

## Judge the Current Pressure

Start from the concrete choice, its consequences, existing project facts, and the Human's legitimate preferences. Read [Implementation Taste](references/implementation.md) only when authority, data, state, boundaries, naming, dependencies, or complexity can change the judgment. Mechanical edits with clear ownership and verification do not need a maxim review.

Return a judgment with its causal reason, material cost, and counter-pressure at the resolution needed by the consuming work. Stop consulting guidance when further heuristics cannot change the choice. A material missing fact calls for [Methods' Explore guidance](../svc-methods/references/explore.md); an unresolved coherent solution calls for [Design](../svc-methods/references/design.md); Human-owned preferences or consequential trade-offs follow the common contract. These are conditional routes, not a required sequence.

Keep four authorities distinct:

- project Product or Technical truth from its canonical owner
- the Human's legitimate product, aesthetic, workflow, and implementation preference
- general design heuristics, which are rebuttable and pressure-dependent
- Task-local hypotheses, which have no durable authority yet

Apply an aligned default directly. A reversible local departure with no material consequence may stay bounded. Present one decision-ready question when a departure changes product experience, explicit preference, authority, acceptance, or long-term cost. Facts and proposed solutions remain challengeable regardless of speaker.

Useful guidance states, in ordinary prose, the recurring pressure, desired consequence, preferred default and causal reason, cost and counter-pressure, conditions that weaken it, and an observable projection or counterexample when useful. A technique without a discoverable use case, predicted consequence, or counter-pressure is inert shelf content.

Product and UI judgment may use rendered alternatives, interaction replay, references, and Human perception. Architecture judgment may use authority and dependency topology, lifecycle, propagation, migration, and failure scenarios. Implementation judgment uses code/data/API shape, naming, contracts, tests, observability, and future-change cost; load [Implementation Taste](references/implementation.md) for that pressure. Add further domain entries only after recurring content and retrieval value justify their owner and maintenance cost.
