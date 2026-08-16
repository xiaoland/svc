# Test Design

Use Test Design when material Product or Technical claims need a deliberate
challenge and observation solution. It is an independent projection of the
parent [Design method](index.md), but its expected outcomes must trace to
owned Product or Technical claims. With no owned claim, return a specification
gap or an exploratory probe; do not manufacture a normative oracle.

Select only what changes the solution or later qualification:

- representative scenarios, inputs, environments, timing, and failures
- Product- or Technical-level observation surfaces
- discriminating oracle, invariant, metamorphic relation, comparison, or
  Human judgment
- required independence and trusted-base assumptions
- material claims that will remain unqualified

Prefer the observation surface where the claim's consequence is authoritative.
An internal value is enough only when the claim is owned there or a qualified
module guarantee makes that projection valid. Reuse a module guarantee by
checking the consumer connection and assumptions; design new composition
challenges only where composition creates new behavior.

Test Design does not require an automated test. Implementation builds the
probe, fixture, replay, harness, or automation; [Verification](../../verification/index.md)
executes and interprets the applicable mechanism; the consuming authority
decides whether the result is sufficient.
