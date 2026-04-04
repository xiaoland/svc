# AGENTS and Meta Engine

In v9.3, Root AGENTS.md is an entry-point dispatcher, not a static constitution.

## 4.1 Dynamic Execution Protocol

Working modes are based on Cynefin and must be MECE (mutually exclusive, collectively exhaustive).

### Mode A: Exploration (Complex)

- Trigger: vague ideas, unknown causality, open problem space
- Action: load mode-a-explore SOP
- Constraint: no PRD/TDD/prod code updates

### Mode B: Solidification (Complicated)

- Trigger: transition from ambiguity to structure
- Action: load mode-b-solidify SOP
- Constraint: categorize truths, restate, wait for confirmation

### Mode C: Execution (Clear)

- Trigger: specific tasks with known causality
- Action: load mode-c-execute SOP
- Constraint: consult local AGENTS and relevant unit TDD before coding

### Mode D: Diagnosis (Chaotic)

- Trigger: anomalies, crashes, corruption, unclear runtime failures
- Action: load mode-d-diagnose SOP
- Constraint: strict read-only, Telemetry First, diagnosis matrix first
- Failure Mode Deduction: produce a tasks diagnostics matrix with validation steps before any fix.

### Extension

> 00-meta should stay high-signal. Do not turn it into a graveyard of unused SOPs.

## Admission Rules

Promote a new mode/skill only if all are true:

1. MECE compliance: cognitive approach and constraints differ from existing modes.
2. High-stakes constraints: strict operational boundaries are required.
3. Demonstrated pain: repeated hallucination or guessing without explicit procedure.

## Mode (SOP) Writing Guidelines (Read-Do Pattern)

1. Define triggers in 1-2 precise sentences.
2. Set explicit forbidden actions.
3. Use concrete read-do steps with linear verbs.
4. Define pause points that require human confirmation.
5. Define exit criteria and next mode.


## 4.2 Pre-Execution Restatement Rule

Before mode B/C execution, restate target, state/context, operation, scope, invariants, likely affected files, and uncertainty.

## 4.3 The Closest to Target consumption logic

Before changes in a directory, recursively check for local AGENTS.md from current to parent directories.

## Related Assets

- [Root AGENTS Template](../assets/templates/AGENTS.root.template.md)
- [Mode A SOP Template](../assets/templates/mode-a-explore.template.md)
- [Mode B SOP Template](../assets/templates/mode-b-solidify.template.md)
- [Mode C SOP Template](../assets/templates/mode-c-execute.template.md)
- [Mode D SOP Template](../assets/templates/mode-d-diagnose.template.md)

