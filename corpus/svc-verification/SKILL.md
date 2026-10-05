---
name: svc-verification
description: "Qualify consequential claims with discriminating evidence. Use when checking a fix, behavior, existing system, test result, integration return, or completion claim; deciding whether existing evidence remains valid; or identifying the scope, trusted assumptions, and residual of an observation."
metadata: {"version": "16.1.0"}
---

# Verification

Recover the intended benefit behind Human wording. Product intent, personal preference, permission, material trade-offs, and acceptance remain Human authority; factual, causal, technical, feasibility, and proposed-solution claims remain challengeable from evidence, logic, stakeholder consequences, and short- and long-horizon return on investment.

Proceed autonomously with safe exploration, review, and design. Before durable mutation, establish the authorized desired effect, semantic owner, affected consumers and invariants, and proportionate verification. Ask the Human only for consequential missing information, authority, preference, trade-off, or acceptance that cannot be inferred safely. Resolve independent work first and present the smallest decision-ready issue. This Skill grants no write, delegation, external-effect, or acceptance authority.

The surrounding Task keeps every unmet obligation after this Skill returns. For its non-trivial Task, recover the existing Task Packet or create the smallest `packet.md` at the project's authorized task location. Keep the objective, authorization and constraints, current facts, next action, and completion verification sufficient to resume. A Skill invocation or Child Assignment does not create a new Task or competing Packet; the Child returns its state delta to the Task owner. Preserve project-owned truth separately, preferring source, configuration, schema, tests, assertions, or automation for facts they can enforce directly.

Other SVC Skills can supply additional guidance when available: discover them by name through the host's available-Skill interface and load only the relevant guidance. They are not prerequisites for this Skill. If one is unavailable, continue with the guidance here and qualified project mechanisms; report an actual missing capability or authority instead of assuming access or relaxing an obligation.

Verification qualifies a consequential owned claim with evidence from an observation that can distinguish the claim from a material alternative. It does not create the claim, infer Product requirements from an implementation, or authorize acceptance and effects.

## Establish the Claim Before Running Checks

First state the consequential claim, its Product or Technical owner, and the boundary at which its consequence can be observed. If the expected behavior is missing, return that gap to the owner; use Methods' Design guidance in `svc-methods` when the observation or oracle needs design. Do not infer the expected result from the candidate implementation.

Execute the smallest credible observation that distinguishes the claim from a material alternative, then interpret it against the owned oracle. Return the evidence, scope, trusted base, and material residual so the consumer can decide its consequence. Stop when that claim is adequately qualified for the consumer, or report an explicit partial/unavailable result with its unmet condition. Building a missing probe belongs to Methods' Implementation guidance in `svc-methods`; discovering an unknown mechanism belongs to Explore in `svc-methods`. Read those only when that work is required.

```text
owned Product/Technical claim
  -> relevant observation surface + discriminating oracle/relation
  -> evidence + scope + trusted base + residual
  -> consumer disposition: continue / reject / rework / accept / waive
```

## Keep the Owner Seams Clear

Product and Technical Design own expected claims. Test Design chooses consequential scenarios, observation, oracle, comparison, Human criteria, and required independence. Implementation builds probes, fixtures, automation, and observability. Verification executes and interprets the applicable mechanism. The consuming authority or effect gate decides what consequence the qualification permits.

These concerns may interleave inside one Slice. They are ownership seams, not phases, files, roles, or mandatory handoffs.

## Observe Where the Claim Is Authoritative

For a Product claim, prefer the Product-visible consequence. An internal value is sufficient only when the claim is owned there or a qualified module guarantee makes the projection valid. Control relevant preconditions and use representative inputs; a stale, noisy, or confounded observation is not made authoritative by convenience.

Choose the smallest credible mechanism for the loss at stake. Prefer compiler, type, schema, constraint, or existing qualified guarantees when they discriminate the claim. Add focused runtime, metamorphic or differential, integration, external readback, shadow, fuzz, statistical, visual, or Human observation only when the claim and residual require them. There is no fixed test pyramid or universal verification ladder.

## Bound the Trusted Base

Determinism is useful but not validity. The trusted base includes the claim and owner, input integrity and representativeness, oracle or relation, instrumentation and environment, verdict interpretation, residual horizon, and effect gate. A compiler or test can reliably prove the wrong proposition.

Treat implementation, fixture, oracle, and tests generated from one correlated AI context as candidate evidence. Where the false-accept loss justifies it, strengthen with owner-derived claims, real or historical inputs, an independent mechanism, mutation/metamorphic/differential relations, or external readback. Do not add a test when static enforcement or an existing guarantee already owns the failure mode.

## Reuse and Distribute Proof

Reuse a qualified deep-module guarantee by checking the consumer connection and its assumptions. Retest only composition behavior newly created by the consumer. Changes to the claim, assumptions, environment, oracle, connection, or relevant implementation invalidate that reuse and trigger proportionate requalification.

Keep local proof with its Slice, Cell, or realization surface. Add a Task-root `verification.md` only when claims, evidence, residuals, or requalification span multiple returns and need one shared synthesis; use Task Packet information guidance in `svc-task-packet` when that state needs its own owner. It is not a final phase, global evidence ledger, mandatory acceptance file, assurance schema, or Reviewer role.
