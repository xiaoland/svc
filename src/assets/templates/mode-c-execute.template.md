# SOP Template: Mode C (Execute)

## Trigger

Use for clear and scoped implementation work with known causality.

## Forbidden

- Do not skip local AGENTS and relevant Unit TDD checks.
- Do not bypass tests for behavior-affecting changes.

## Read-Do Steps

1. Load root dispatcher guidance and matching mode SOP.
2. Load nearest local AGENTS.md constraints.
3. Load relevant Unit TDD and Product TDD context.
4. Perform pre-execution restatement.
5. Implement tests first when practical.
6. Implement code changes and run checks.

### Pre-Execution Restatement Contract

Before changing durable docs or code, restate:

- target
- state/context
- operation
- scope
- invariants
- likely affected files
- uncertainty

## Pause Point

If uncertainty remains high after restatement, pause and return to Mode A or Mode B.

## Exit Criteria

- Requested behavior is implemented.
- Tests and checks pass.
- No invariant in local AGENTS or TDD docs is violated.
