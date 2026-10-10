---
name: svc-taste
description: "Use when choosing between design or implementation options affecting user experience, permissions, data ownership, state, boundaries, naming, dependencies, performance, or maintenance."
metadata: {"version": "16.0.1"}
---

# Taste and Design Judgment

Taste uses knowledge of consequences to judge plausible designs when Product or Technical facts do not decide the choice. Apply it to the current choice, not as a global maxim catalog or universal law.

## Ground the Choice

Start with the choice, its consequences, project facts, and Human preferences. Read [Implementation Taste](references/implementation.md) only when authority, data, state, boundaries, naming, dependencies, performance, or complexity affect the judgment. Mechanical edits with clear ownership and verification need no maxim review.

Keep four authorities distinct:

- project Product or Technical truth from its canonical owner
- the Human's legitimate product, aesthetic, workflow, and implementation preference
- general design heuristics, which are rebuttable and pressure-dependent
- Task-local hypotheses, which have no durable authority yet

## Weigh Consequences and Counter-Pressure

Weigh intended consequences, causal reasons, costs, and counter-pressure. State what would weaken the recommendation, using observable consequences or counterexamples when useful. A technique alone, without a use case or predicted consequence, does not justify a choice.

Product and UI choices may use rendered alternatives, interaction replay, references, and Human perception. Architecture choices may use authority, dependencies, lifecycle, propagation, migration, and failure scenarios. Implementation choices use code/data/API shape, naming, contracts, tests, observability, and future-change cost. Weigh short- and long-term stakeholder consequences; heuristics are not laws.

Apply an aligned default directly. A reversible local departure with no material consequence may stay bounded. Present one decision-ready question when a departure changes product experience, explicit preference, authority, acceptance, or long-term cost. Human intent, preferences, permissions, material trade-offs, and acceptance retain their authority; factual and proposed-solution claims remain challengeable regardless of speaker. Continue safe investigation and independent authorized work while resolving consequential missing Human input.

## Return a Usable Judgment

Return a recommendation with its reason, cost, and counter-pressure in enough detail for the consuming work. Stop reading when further heuristics cannot change the choice. Discover `svc-workflow` by name for Explore when a material fact is missing, or Design when the solution remains incoherent. Neither route is mandatory; other Task obligations remain.

## Authority and Task Continuity

Before durable mutation, establish the authorized effect, owner, affected consumers, invariants, and proportionate verification. This Skill grants no write, delegation, external-effect, or acceptance authority. Keep durable project truth at its canonical owner, preferring executable sources for enforceable facts.

For every non-trivial Task, recover its Packet or create the smallest `packet.md` at the project's authorized location. Preserve objective, authority and constraints, current facts, next action, and completion evidence. An invocation or Child Assignment creates no competing Task or Packet; return state changes to the Task owner. Other Skills are optional guidance, not prerequisites; discover them by name when needed, use qualified project mechanisms when absent, and report actual capability or authority gaps without relaxing obligations.
