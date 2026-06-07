# Typed Taxonomy and Mode Engine

Root AGENTS.md is an entry-point classifier plus a tiny ontology cheat sheet. It is not a static constitution.

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

Creative engineering is not a waterfall of design -> code -> verify. Design formation, verification preparation, implementation shape, execution, and diagnosis can reshape each other while durable ownership remains stable.

Verification is not only a post-Execute gate. Once a design claim is solid enough to act on, prepare the proof shape and let it constrain Execute. If Execute exposes friction that invalidates the proof shape or design claim, return to Explore, Solidify, or Diagnose.

## Dispatcher Contract

For every external perturbation:

1. Classify it as Intent, Constraint, Reality, or Artifact before acting.
2. Estimate blast radius and durable owner from that type.
3. Open or update an agent-owned task packet with MVT anchors if the work is non-trivial.
4. Keep the packet current when discussion, exploration, implementation friction, or verification changes the working state.
5. Select the current mode overlay for this slice of work.
6. Load only the route protocol, mode SOP, and governing anchors needed for the task.
7. Search source and durable docs with volatile workspaces excluded by default.
8. Expand the request into alignment substrate fields only when coordination risk exceeds what MVT can safely express.
9. Load topology-extension guidance only when the repo shape actually requires it.
10. Promote stable knowledge after the work, not during guesswork.

## Substrate Expansion Rule

Most tasks do not need substrate-complete wording.

Expand the active request into alignment substrate fields only when one or more of these are true:

- references or visual names are unstable
- object boundaries are ambiguous
- operation words may hide different side effects
- valid interpretation depends on state or context
- evidence is missing or too weak to justify mutation
- blast radius is not obviously local

This is an escalation path, not a replacement for MVT.

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
- For non-trivial code work, use implementation taste to expose authority, trust, naming, and complexity unknowns.
- Exit when the unknowns are reduced enough to solidify or execute.

### Mode B: Solidify

- Use when findings must be restated into stable claims, contracts, or explicit decisions.
- This mode often bridges tasks and durable docs.
- For non-trivial code work, use implementation taste to form the temporary design claim and prepare the verification shape.
- Exit when durable ownership and verification are explicit.

### Mode C: Execute

- Use when the current slice of work is clear enough to implement or edit safely.
- This mode can appear multiple times inside the same task.
- For non-trivial code work, use implementation taste as a projection onto concrete code surfaces, not as a new durable owner.
- Exit when verification passes or when new uncertainty forces a return to Explore or Diagnose.

### Mode D: Diagnose

- Use when observed reality diverges from expectations and evidence must be collected before action.
- This mode is common in Reality work but can also reappear when execution produces unexplained behavior.
- For non-trivial code work, use implementation taste to check whether the failure came from authority drift, trust-boundary confusion, semantic naming drift, or unjustified complexity.
- Exit when likely causes are ranked and the next action is justified.

## Progressive Load Rules

Load the smallest useful set of references:

- Always read root AGENTS.md first.
- Read the matching input route protocol in `00-meta/`.
- Read one or more mode SOPs only for the current working posture.
- Read nearest local `AGENTS.md` files before changing code.
- Read PRD, Product TDD, Unit TDD, or Deployment docs only for the owning layer of the current route.
- Read implementation taste when a non-trivial code design or implementation change will shape implementation structure, boundary shape, data shape, state flow, authority flow, durable naming, abstraction, or complexity budget.
- Read `15-alignment/` only when repeated drift, ambiguous targeting, or risky mutation requires more explicit coordination grammar.
- Read topology-extension guidance only when the repo actually uses that topology.
- Read `00-meta/concepts.md` only when boundary language is unclear or the user explicitly asks for meta concepts.
- Read `10-prd/glossary.md` only when business/domain terminology matters.

## Source Search Defaults

For ordinary source and durable-doc search, exclude volatile and generated surfaces by default:

- `tasks/`
- `temp/`
- generated output such as `build/`, `dist/`, and coverage reports
- dependency folders such as `node_modules/`
- virtual environments and tool caches such as `.venv/`, `.tox/`, and `.pytest_cache/`

Search those surfaces only when the active question targets them, when recovering the active task packet, or when reviewing evidence deliberately stored there.

## Impact Handshake Rule

Meta engine owns when the pre-execution Impact Handshake must trigger. Alignment supplies the grammar that the handshake draws from.

Before an agent mutates durable truth after loading the substrate, or when the blast radius is not obviously local, it must pause and restate:

- Address and Object: the anchors or symbols that will be touched
- State Diff: `From -> To`
- Blast Radius Forecast: expected files, modules, or downstream surfaces affected
- Invariants Check: what is explicitly protected from change
- Verification: the concrete proof that will bound side effects

If evidence is missing or the owning layer is still unclear, do not handshake guesses. Return to Explore or Diagnose until the next step is justified.

## Topology Extension Rule

Root guidance should stay neutral by default.

If a repository shape introduces extra operational surfaces such as a shared-doc mount, load the matching extension guidance before mutating that surface.

For the multi-repo variant, see [Optional Multi-Repo Extension](multi-repo.md).

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
- [Implementation Taste](implementation-taste.md)
- [Mode A Template](../assets/templates/mode-a-explore.template.md)
- [Mode B Template](../assets/templates/mode-b-solidify.template.md)
- [Mode C Template](../assets/templates/mode-c-execute.template.md)
- [Mode D Template](../assets/templates/mode-d-diagnose.template.md)
- [Concept Dictionary Template](../assets/templates/concepts.template.md)
