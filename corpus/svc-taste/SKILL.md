---
name: svc-taste
description: "Judgment of design and implementation trade-offs by their consequences when Product or Technical facts do not decide the choice."
metadata: {"version": "17.0.0"}
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

Price risk by expected value. For a protection, recovery path, compatibility layer, retry, check, or guarantee, estimate how often its trigger occurs, the loss when it occurs, and how much the project's stage and positioning weigh that loss; compare that product with the certain build, verification, learning, and maintenance cost. State the likelihood estimate: a failure you can construct is a possibility, not a frequency. Project stage sets the weight; unreleased work needs no compatibility layer, and reversible or demo-grade deployments warrant less caution than critical paths. Find the few decisions that carry most of the value. Where perfection is expensive, prefer best-effort behavior with a simple escape such as manual refresh or correction over a guarantee mechanism. The pressure runs both ways: make near-zero-downside improvements directly, and accept high cost when the return is high.

Apply judgment within agreed goals and authority. Bring a recommendation to the Human when it depends on a missing Human preference or a material departure from accepted commitments. Resolve reversible local choices directly when they stay within those bounds; continue unaffected authorized work while a Human decision is pending.

## Calibrate the Judgment

Treat felt quality as a hypothesis, not a conclusion. When a design feels good or bad, explain which concrete decision causes the response before relying on it; an unexplained preference does not justify a choice. Study work widely recognized as excellent and analyze its specific decisions, since judgment calibrated on familiar examples inherits their limits. Strong work keeps purpose, architecture, design, and implementation simple together; when one layer is simple and another convoluted, find which decision broke the alignment. Seek critique on the reasons given, not only the outcome.

Calibration also runs outward: check the result against the current catalogue of model default patterns — the arrangements models produce regardless of subject when no axis of the brief pins them down. A default reached on a free axis is evidence that no decision happened, not a defect; the response is to make the choice, not to ban the pattern, since each of these arrangements is legitimate for some brief. Run `scripts/check-default-patterns.sh <files>` on markup or styles before accepting a visible result; its findings are candidates for a decision, and a clean run says nothing about whether the design is good.

## Return a Usable Judgment

Return a recommendation with its reason, cost, and counter-pressure in enough detail for the consuming work. Stop reading when further heuristics cannot change the choice. Discover `svc-workflow` by name for Explore when a material fact is missing, or Design when the solution remains incoherent. Neither route is mandatory; other Task obligations remain.

## Authority and Task Continuity

Human goals, preferences, permissions, material trade-offs, and acceptance retain their authority; factual and proposed-solution claims remain open to evidence and reasoning. This Skill grants no write, delegation, external-effect, or acceptance authority. Keep durable project truth at its canonical owner, preferring executable sources for enforceable facts.

Apply the judgment within the existing Task and return the recommendation, rationale, and unresolved matters to the Task owner. This Skill requires no separate Task or record. Other Skills are optional guidance; discover them when needed and report actual capability or authority gaps without relaxing obligations.
