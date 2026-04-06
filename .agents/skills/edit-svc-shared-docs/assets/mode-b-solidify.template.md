# SOP Template: Mode B (Solidify)

## Role

Use when findings must be restated into stable claims, contracts, decisions, or promotion candidates.

This mode often bridges tasks and durable docs, and it may occur multiple times inside the same task.

## Forbidden

- Do not start coding while durable ownership is still ambiguous.
- Do not promote unstable guesses into PRD, TDD, or deployment docs.
- In a Spoke repo, do not commit or push shared-doc edits from `docs/_shared/` without explicit human authorization.

## Read-Do Steps

1. Gather the current findings, evidence, and assumptions.
2. Decide which truths are stable enough to promote and which must stay in tasks.
3. Restate the target, scope, invariants, and verification.
4. Confirm the durable owner for each promoted truth.
5. If promotion was triggered by Spoke execution, capture the local seam and missing shared rule in the active task before any shared-doc mutation begins.
6. If promotion must update shared truth from a Spoke, verify the shared mount is current, edit the Hub source, then pause for human authorization before commit or push.
7. Hand off to Execute or return to Explore if ownership is still unclear.

## Exit Criteria

- Durable ownership is explicit.
- Verification is explicit.
- Shared and local mutations are isolated when both were necessary.
- The next edit or implementation step is safe to perform.
