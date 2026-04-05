# Route Template: Reality

## Trigger

Use for bugs, anomalies, outages, crashes, corrupt state, or any mismatch between expected and observed runtime behavior.

## Primary Owner

- `tasks/` for evidence gathering and hypothesis ranking
- nearest local `AGENTS.md` for recurrence tripwires after the fix

## Mode Relationship

- Common opening overlay: Diagnose.
- Explore or Execute may follow once evidence changes the posture.

## Forbidden

- No evidence, no modification.
- Do not jump straight from symptom to fix.

## Read-Do Steps

1. Capture logs, metrics, traces, events, and failing tests.
2. Define blast radius and timeline.
3. Build a diagnostics matrix with validation steps.
4. Rank hypotheses by evidence quality.
5. Only after validation, plan the fix and identify recurrence tripwires.
6. Promote stable operational or technical lessons into Deployment or TDD docs when justified.

## Exit Criteria

- Likely cause is evidence-backed.
- Validation steps are explicit.
- A recurrence guard exists as a test, assertion, runbook, or local AGENTS tripwire.
