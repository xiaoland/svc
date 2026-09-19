# Verification

Verification qualifies a consequential owned claim with evidence from an
observation that can distinguish the claim from a material alternative. It
does not create the claim, infer Product requirements from an implementation,
or authorize acceptance and effects.

```text
owned Product/Technical claim
  -> relevant observation surface + discriminating oracle/relation
  -> evidence + scope + trusted base + residual
  -> consumer disposition: continue / reject / rework / accept / waive
```

## Keep the Owner Seams Clear

Product and Technical Design own expected claims. Test Design chooses
consequential scenarios, observation, oracle, comparison, Human criteria, and
required independence. Implementation builds probes, fixtures, automation,
and observability. Verification executes and interprets the applicable
mechanism. The consuming authority or effect gate decides what consequence
the qualification permits.

These concerns may interleave inside one Slice. They are ownership seams, not
phases, files, roles, or mandatory handoffs.

## Observe Where the Claim Is Authoritative

For a Product claim, prefer the Product-visible consequence. An internal value
is sufficient only when the claim is owned there or a qualified module
guarantee makes the projection valid. Control relevant preconditions and use
representative inputs; a stale, noisy, or confounded observation is not made
authoritative by convenience.

Choose the smallest credible mechanism for the loss at stake. Prefer compiler,
type, schema, constraint, or existing qualified guarantees when they
discriminate the claim. Add focused runtime, metamorphic or differential,
integration, external readback, shadow, fuzz, statistical, visual, or Human
observation only when the claim and residual require them. There is no fixed
test pyramid or universal verification ladder.

## Bound the Trusted Base

Determinism is useful but not validity. The trusted base includes the claim and
owner, input integrity and representativeness, oracle or relation,
instrumentation and environment, verdict interpretation, residual horizon,
and effect gate. A compiler or test can reliably prove the wrong proposition.

Treat implementation, fixture, oracle, and tests generated from one correlated
AI context as candidate evidence. Where the false-accept loss justifies it,
strengthen with owner-derived claims, real or historical inputs, an independent
mechanism, mutation/metamorphic/differential relations, or external readback.
Do not add a test when static enforcement or an existing guarantee already
owns the failure mode.

## Reuse and Distribute Proof

Reuse a qualified deep-module guarantee by checking the consumer connection
and its assumptions. Retest only composition behavior newly created by the
consumer. Changes to the claim, assumptions, environment, oracle, connection,
or relevant implementation invalidate that reuse and trigger proportionate
requalification.

Keep local proof with its Slice, Cell, or realization surface. Add a Task-root
`verification.md` only when claims, evidence, residuals, or requalification
span multiple returns and need one shared synthesis. It is not a final phase,
global evidence ledger, mandatory acceptance file, assurance schema, or
Reviewer role.
