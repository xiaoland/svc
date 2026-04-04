# SOP Template: Mode D (Diagnose)

## Trigger

Use for outages, anomalies, crashes, corruption, or unclear runtime failures.

## Forbidden

- Strict read-only: no source code modifications.
- No guess-first fixes.

## Read-Do Steps

1. Collect telemetry (logs, metrics, traces, events).
2. Establish timeline and blast radius.
3. Build a failure-mode matrix in tasks/.
4. Define validation steps for each hypothesis.
5. Recommend transition: continue diagnosis, execute runbook, or switch to Mode C fix.

## Pause Point

Wait for human decision before any fix action or mitigation run.

## Exit Criteria

- Evidence-backed likely causes are ranked.
- Validation plan is explicit.
- Next mode and operator action are confirmed.
