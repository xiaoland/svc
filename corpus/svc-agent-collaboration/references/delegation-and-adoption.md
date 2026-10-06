# Delegation and Adoption

Read this when arranging substantial work, matching capability and feedback, or receiving a result that is difficult to adopt. It expands the entry's assignment and result-use guidance. Return a supported answer or achieved effect the consumer can use, with the conditions and unresolved claims that matter; do not require a new assignment form or a complete objective oracle before collaborating.

## Shape Work Around Its Use

Begin with the decision or effect the consumer needs and what could advance it: a supported explanation, an implemented change with relevant observations, a query that exposes a relationship, or a comparison that makes a consequential assumption clear. Consider what evidence or argument could support adoption, then choose the work boundary and integration point. Open design may require reasons, counterexamples, or observed use instead of a complete test oracle. Do not prescribe the answer to make judgment easy.

Supply the purpose, latest decisions, relevant known state, source entrances, material dependencies, constraints, and authorized or excluded effects. Preserve context that changes the result or its conditions. The caller need not enumerate every file, discover all local state, or prescribe each operation: that preparation can consume the work collaboration was meant to save. The owner establishes the source identity, initial state, affected consumers, and local facts needed for its claims and actions.

Assign tightly connected investigation, implementation, operation, repair, and verification to one owner with authority for their necessary work. File boundaries coordinate concurrent edits; they do not create a separate approval requirement for every necessary file when the effect is already authorized. Preserve others' work and coordinate overlapping changes. Local failures and missing routine details are the owner's responsibility; escalate a missing Human-specific fact, actual permission, or consequential change in goal or tradeoff with its effect on completion. General infrastructure improvement enters the critical path only when the requested outcome depends on it.

Match actual judgment, tools, context capacity, recovery ability, and feedback to the difficulty and consequences. A narrow outcome can still be difficult, and a role name is not capability evidence. Isolation of noisy material and a different reasoning route can be valuable; shared assumptions can also correlate errors. Consult independent judgment when it could change a consequential choice, giving the original goal and one decision to resolve. Another Agent's agreement is not independent observation, and routine failures do not require another decision-maker.

## Make the Return Easier to Judge Than the Search

Generation and adoption can have different costs. An owner can search many sources or explore several explanations, then return a small observation or argument that captures the decisive relationship. The consumer should understand that relationship, its inputs, the actual result, and the limits of the inference. A pile of evidence links saves little if the consumer must reconstruct the whole investigation.

| Claim and conditions | Useful basis for adoption and its limit |
| --- | --- |
| A fact can be precisely queried or constrained. | A short query, schema, type constraint, or qualified existing check can compress many facts. Understand its meaning, input coverage, version, and actual result. Compilation does not establish business correctness; an empty query result may reflect missed cases. |
| A meaningful relationship can be checked without a complete oracle. | An invariant, difference, round trip, conservation, or compatibility relation may constrain the claim. Establish its conditions and comparison reference. A necessary relationship may be insufficient, and both sides may share a defect. |
| Full observation is too expensive. | Select observations around uncertainty that could change the decision. State selection and inference assumptions. Sample success does not establish the entire population or an error probability without a justified model. |
| The result is a design, explanation, or preference requiring judgment. | Use assumptions, causal reasons, alternatives, counterexamples, and observed use where available. Preserve unresolved choices and keep commitments proportionate to consequences and reversibility. A score or Agent vote cannot create an objective oracle. |

Choose the basis for the claim, not a fixed hierarchy of tool names. A hash supports artifact identity; a running process supports a deployment-state claim. Neither alone establishes the user outcome. Applicable existing guarantees can support adoption without rerunning everything, but their assumptions and connection to the current claim must hold. A checker requiring nearly the same reasoning as the original work may erase the gain.

## Example: Resolve Missing Parent Records

Suppose invoice failures may be caused by references to nonexistent accounts, but the relevant relationship and data conditions are uncertain. Give the owner the schema, failing identifiers, snapshot entrance, and read-only authority. It investigates whether null references, archived records, or deleted accounts are legitimate and adapts a query such as:

```sql
SELECT i.id, i.account_id
FROM invoices AS i
LEFT JOIN accounts AS a ON a.id = i.account_id
WHERE i.account_id IS NOT NULL AND a.id IS NULL;
```

The useful return includes the actual result for the relevant snapshot and its interpretation. The consumer checks that the relationship and null handling match the domain, that the selection covers the failures, and that the reported observation comes from the stated input. This can replace reading every invoice or rediscovering the relationship. It supports a repair direction when the cases match; it does not establish every business rule or authorize deleting records. If missing parents are valid historical records, or archived accounts require different handling, the query and conclusion must reflect that condition. If the relationship and query were clear from the start, direct execution would have been cheaper.

## Example: Compare an Interaction Choice

Suppose users lose an unsaved filter when switching views and the desired interaction is open. An owner can compare preserving it, resetting it visibly, and asking before discarding it against the user goal and constraints. It returns decisive reasons, a counterexample such as a hidden filter making a new view appear empty, and observations from a prototype or actual use when available. The consumer can understand the tradeoff without recreating every candidate or reviewing the entire exploration history.

Observed users completing one path can support usability under those conditions; it cannot settle every preference or unobserved view. Without observed use, the return remains a reasoned proposal. The consumer may adopt a reversible candidate, request a specific missing observation, or retain the choice as unresolved. A second Agent's preference is another opinion, not a user observation.

## Adopt, Repair, or Return a Bounded Gap

Distinguish the owner's report of an action from the relevant observation for the actual candidate, inputs, and environment. Obtain the source result when the consequence or uncertainty requires it and understand the observation or argument connecting it to the claim. A launch receipt, role identity, self-assessment, or approval statement supports no broader claim merely because it came from an Agent. Use actual project effect gates and any required independent checks; do not invent a universal validator for every return.

Adopt supported work and integrate it with the surrounding task. When a concrete contradiction, changed premise, or missing observation matters, return the counterexample and actionable repair reason to the same owner. Let local feedback guide the correction within its authorization rather than relaying each operation. Reuse conclusions that still apply; neither a new candidate nor an interruption automatically invalidates everything.

If evidence is unavailable, continuation is unauthorized, or the remaining uncertainty cannot be reduced at proportionate cost, return the supported partial result, what prevents completion, effects still pending, and the smallest useful next action or decision. Preserve unsupported claims explicitly. Adoption of this return is not a declaration that the overall task is complete.
