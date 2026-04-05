# Typed Taxonomy and Mode Engine

In v9.5, root AGENTS.md is an entry-point classifier plus a tiny ontology cheat sheet. It is not a static constitution.

The front door is now typed input classification, but Mode Dispatch still exists as a reusable SOP and mind-pattern layer. The system no longer depends on mode selection alone to decide ownership or blast radius.

## Dual-Axis Mental Model

Two different questions must be answered separately:

1. Input type: what kind of perturbation entered the system, and which durable layer owns the truth?
2. Mode: what thinking posture or SOP is appropriate for the current slice of work?

Rule of thumb:

- input type decides ownership, blast radius, and mandatory guardrails
- mode decides the current way of working
- changing mode does not change durable ownership by itself
- one task or issue may traverse multiple modes
- mode transitions are non-linear and reversible

## Dispatcher Contract

For every external perturbation:

1. Classify it as Intent, Constraint, Reality, or Artifact before acting.
2. Estimate blast radius and durable owner from that type.
3. Open a task packet with MVT anchors if the work is non-trivial.
4. Select the current mode overlay for this slice of work.
5. Load only the route protocol, mode SOP, and governing anchors needed for the task.
6. Promote stable knowledge after the work, not during guesswork.

## Input Route Taxonomy

### Intent

- Trigger: the business wants new behavior, policy, scope, or strategy.
- Primary owner: `10-prd/`
- Agent focus: validate impact on existing product claims and update product truth first.
- Guardrail: do not smuggle mechanism, topology, or interface details into PRD.
- Common mode overlays: Explore, Solidify, Execute.

### Constraint

- Trigger: business behavior stays the same, but technical, performance, dependency, or environment boundaries change.
- Primary owner: `20-product-tdd/` or `30-unit-tdd/`
- Agent focus: restate the technical contract and preserve PRD commitments unless explicitly renegotiated.
- Guardrail: do not rewrite product intent just to justify an implementation choice.
- Common mode overlays: Solidify, Execute, Diagnose when reality diverges.

### Reality

- Trigger: bug, anomaly, outage, mismatch between expectation and runtime reality.
- Primary owner: evidence in `tasks/`, then recurrence guardrails in local `AGENTS.md`
- Agent focus: diagnose with logs, traces, tests, and validation steps before proposing a fix.
- Guardrail: no evidence, no modification.
- Common mode overlays: Diagnose first; Explore or Execute may follow.

### Artifact

- Trigger: a concrete intermediate deliverable such as a script, data cleanup, migration helper, or one-off analysis output.
- Primary owner: `tasks/` or the local work surface
- Agent focus: deliver the artifact quickly with explicit verification and avoid unnecessary promotion.
- Guardrail: do not turn disposable tactics into durable architecture without evidence.
- Common mode overlays: Execute, sometimes Explore.

## Mode Dispatch as SOP Layer

### Mode A: Explore

- Use when key unknowns remain and the solution space must be mapped.
- This mode can appear inside Intent, Constraint, Reality, or Artifact work.
- Exit when the unknowns are reduced enough to solidify or execute.

### Mode B: Solidify

- Use when findings must be restated into stable claims, contracts, or explicit decisions.
- This mode often bridges tasks and durable docs.
- Exit when durable ownership and verification are explicit.

### Mode C: Execute

- Use when the current slice of work is clear enough to implement or edit safely.
- This mode can appear multiple times inside the same task.
- Exit when verification passes or when new uncertainty forces a return to Explore or Diagnose.

### Mode D: Diagnose

- Use when observed reality diverges from expectations and evidence must be collected before action.
- This mode is common in Reality work but can also reappear when execution produces unexplained behavior.
- Exit when likely causes are ranked and the next action is justified.

## Progressive Load Rules

Load the smallest useful set of references:

- Always read root AGENTS.md first.
- Read the matching input route protocol in `00-meta/`.
- Read one or more mode SOPs only for the current working posture.
- Read nearest local `AGENTS.md` files before changing code.
- Read PRD, Product TDD, Unit TDD, or Deployment docs only for the owning layer of the current route.
- Read `00-meta/concepts.md` only when boundary language is unclear or the user explicitly asks for meta concepts.
- Read `10-prd/glossary.md` only when business/domain terminology matters.

## Extension Rules

`00-meta/` should stay high-signal. Do not create new top-level input types lightly.

Promote a new route add-on or mode SOP only if all are true:

1. The current guidance is insufficient without losing clarity.
2. The new protocol adds a distinct operational constraint, not just extra wording.
3. Repeated failures show the current route or mode guidance is too weak.

## Route and Mode Writing Guidelines

1. Define the trigger in 1-2 precise sentences.
2. State whether the document governs ownership, working posture, or both.
3. State forbidden actions and negotiation triggers.
4. Use read-do steps with explicit evidence or verification.
5. State the exit condition and promotion rule for any new knowledge discovered.

## The Closest to Target Consumption Logic

Before changes in a directory, recursively check for local AGENTS.md from the current directory to its parents.

## Related Assets

- [Root AGENTS Template](../assets/templates/AGENTS.root.template.md)
- [Intent Route Template](../assets/templates/input-intent.template.md)
- [Constraint Route Template](../assets/templates/input-constraint.template.md)
- [Reality Route Template](../assets/templates/input-reality.template.md)
- [Artifact Route Template](../assets/templates/input-artifact.template.md)
- [Mode A Template](../assets/templates/mode-a-explore.template.md)
- [Mode B Template](../assets/templates/mode-b-solidify.template.md)
- [Mode C Template](../assets/templates/mode-c-execute.template.md)
- [Mode D Template](../assets/templates/mode-d-diagnose.template.md)
- [Concept Dictionary Template](../assets/templates/concepts.template.md)
