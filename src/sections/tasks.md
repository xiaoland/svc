# Tasks

## 11.1 Role of Tasks

Tasks are the entropy buffer of the system.

The tasks directory is the battleground for:

- exploration before durable promotion
- diagnostics before bug fixes
- transient artifacts and one-off execution notes
- temporary reasoning that should not pollute durable docs

## 11.2 Minimal Viable Task Protocol (MVT)

Every non-trivial task packet must explicitly include these three anchors:

- Objective & Hypothesis: the core goal and the expected effect of the work
- Guardrails Touched: the 1-2 existing rules or boundaries that must not be violated
- Verification: objective proof that the task is done correctly

These are guardrails, not bureaucracy.

## 11.3 Substrate Expansion Rule

Most tasks do not need substrate-complete wording.

Keep MVT as the default lightweight task frame. Expand the active task into alignment substrate fields only when coordination risk exceeds what MVT can safely express, for example when:

- references or object boundaries are drifting
- the valid request depends on state or context
- operation words may hide different side effects
- evidence is still weak or missing
- blast radius is not obviously local

This expansion makes the task packet more explicit, but it does not change durable ownership by itself.

## 11.4 Task and Mode Relationship

Tasks and issues do not map one-to-one to modes.

- a single task may traverse Explore, Solidify, Execute, and Diagnose more than once
- different sub-problems inside one task may temporarily use different modes
- mode transitions are driven by the current uncertainty or evidence state, not by a fixed linear pipeline
- input type stays the front-door classifier even when the active mode changes

## 11.5 Optional Exploration Scaffold

Use the following fields only when they help reduce ambiguity:

- Perturbation & Input Type: what signal started the work and how it maps to Intent, Constraint, Reality, or Artifact
- Active Mode or Transition Note: the current mind-pattern, if recording it helps explain why the next step changed
- Governing Anchors: which existing PRD, Product TDD, Unit TDD, Deployment, or local AGENTS docs currently govern the area
- Impact Hypothesis: what downstream modules or topology could be affected
- Temporary Assumptions: what you are assuming until code or evidence proves otherwise
- Negotiation Triggers: when structural conflict or ambiguity must pause the work for human input
- Promotion Candidates: what knowledge might deserve durable storage after the task ends

If an optional topology extension is active, keep any extension-specific captures in tasks until the matching extension guidance says they can be promoted.

## 11.6 Exit Rule

Do not promote a task note directly into durable truth without the promotion test. Tasks are for bounded exploration, not for becoming shadow architecture.

## Related Assets

- [Task Packet Template](../assets/templates/task-packet.template.md)
- [Task Diagnostics Matrix Template](../assets/templates/task-diagnostics-matrix.template.md)
