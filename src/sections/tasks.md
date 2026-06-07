# Tasks

## 11.1 Role of Tasks

Tasks are the agent-owned, task-local workspace of the system.

The tasks directory is the battleground for:

- exploration before durable promotion
- diagnostics before bug fixes
- transient artifacts and one-off execution notes
- temporary reasoning that should not pollute durable docs
- human-agent collaboration around current state, evidence, and next steps

## 11.2 Task Packet Invariants

A task packet is not just a task file. It is a bounded workspace that lets the agent think, explore, verify, and recover without polluting durable truth or the conversation context.

Every non-trivial task packet should preserve these invariants:

- Agent-owned: the agent may create, update, split, and reorganize the packet inside the task boundary without separate human approval.
- Task-local: temporary reasoning, scratch artifacts, exploration notes, and verification material stay inside the bounded task workspace.
- Human-agent-collaboration-oriented: the packet remains readable, inspectable, and steerable by the human even though the agent owns its day-to-day mutation.
- Recoverable: a resumed agent can restore the current task state from a compact control surface.
- Bounded: the packet serves one task and does not become a permanent knowledge base.
- Non-durable: packet contents are not source truth until they pass the promotion test and move to the correct durable owner.
- Search-isolated: volatile task material is excluded from normal source and durable-doc search by default.

Agent-owned does not mean ungoverned. The agent can mutate the packet freely, but code, durable docs, public configuration, and generated release artifacts still follow their normal ownership, guardrail, and verification rules.

## 11.3 Minimal Viable Task Protocol (MVT)

Every non-trivial task packet must explicitly include these three anchors:

- Objective & Hypothesis: the core goal and the expected effect of the work
- Guardrails Touched: the 1-2 existing rules or boundaries that must not be violated
- Verification: objective proof that the task is done correctly

These are the minimum control surface. They are guardrails, not bureaucracy.

## 11.4 Progressive Poly-File Rule

A task packet may start as a single file.

When it grows beyond a compact control surface, it should become a task-local directory. The split is driven by collaboration pressure, not by a fixed taxonomy.

Split when the current shape makes it harder for a human or agent to quickly answer:

- what the task is now
- what is confirmed versus assumed
- what evidence supports the current understanding
- what decision or verification comes next
- what might deserve durable promotion

Common split dimensions are:

- current versus history
- state versus evidence
- decision versus exploration
- control surface versus temporary work
- summary versus raw output

Recommended directory-mode starting point:

```text
tasks/<task-id>/
|-- packet.md       # compact control surface and index
|-- notes.md        # compressed findings, discussion state, and decisions
`-- work/           # task-local scratch space for any temporary artifacts
```

For larger tasks, split `notes.md` only where it reduces cognitive load. Common names include `findings.md`, `decisions.md`, and `verification.md`, but these are recommendations rather than an exhaustive folder scheme.

`packet.md` must stay compact. It should not become a full history, raw log dump, or hidden durable architecture document.

## 11.5 Substrate Expansion Rule

Most tasks do not need substrate-complete wording.

Keep MVT as the default lightweight task frame. Expand the active task into alignment substrate fields only when coordination risk exceeds what MVT can safely express, for example when:

- references or object boundaries are drifting
- the valid request depends on state or context
- operation words may hide different side effects
- evidence is still weak or missing
- blast radius is not obviously local

This expansion makes the task packet more explicit, but it does not change durable ownership by itself.

## 11.6 Task and Mode Relationship

Tasks and issues do not map one-to-one to modes.

- a single task may traverse Explore, Solidify, Execute, and Diagnose more than once
- different sub-problems inside one task may temporarily use different modes
- mode transitions are driven by the current uncertainty or evidence state, not by a fixed linear pipeline
- input type stays the front-door classifier even when the active mode changes

The agent should update the active task packet when discussion, exploration, implementation friction, or verification changes the working state enough that losing it would increase task risk.

## 11.7 Optional Exploration Scaffold

Use the following fields only when they help reduce ambiguity:

- Perturbation & Input Type: what signal started the work and how it maps to Intent, Constraint, Reality, or Artifact
- Active Mode or Transition Note: the current mind-pattern, if recording it helps explain why the next step changed
- Governing Anchors: which existing PRD, Product TDD, Unit TDD, Deployment, or local AGENTS docs currently govern the area
- Impact Hypothesis: what downstream modules or topology could be affected
- Temporary Assumptions: what you are assuming until code or evidence proves otherwise
- Negotiation Triggers: when structural conflict or ambiguity must pause the work for human input
- Promotion Candidates: what knowledge might deserve durable storage after the task ends

If an optional topology extension is active, keep any extension-specific captures in tasks until the matching extension guidance says they can be promoted.

## 11.8 Search Isolation

When searching source or durable docs, exclude volatile workspaces by default: `tasks/`, `temp/`, generated output, dependency folders, virtual environments, and task-local scratch areas.

Search those locations only when the task explicitly targets them, when recovering task state, or when reviewing evidence inside the active packet.

## 11.9 Exit Rule

Do not promote packet content directly into durable truth without the promotion test. Tasks are for bounded exploration, not for becoming shadow architecture.

## Related Assets

- [Task Packet Template](../assets/templates/task-packet.template.md)
- [Task Diagnostics Matrix Template](../assets/templates/task-diagnostics-matrix.template.md)
