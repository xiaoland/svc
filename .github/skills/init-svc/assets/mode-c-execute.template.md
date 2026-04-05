# SOP Template: Mode C (Execute)

## Role

Use when the current slice of work is clear enough to implement or edit safely.

This mode can appear in any input type once ownership and verification are sufficiently clear.

## Forbidden

- Do not skip local AGENTS and relevant TDD checks before coding.
- Do not keep executing when new evidence shows the problem is still not understood.

## Read-Do Steps

1. Restate the exact change and verification plan.
2. Load the nearest local AGENTS plus any governing PRD, TDD, or deployment docs.
3. Implement the smallest safe change for the current slice.
4. Run checks and compare the result against the declared verification.
5. If unexpected behavior appears, re-enter Explore or Diagnose instead of guessing.

## Exit Criteria

- The requested change for this slice is implemented.
- Verification passes.
- No known invariant is violated.
