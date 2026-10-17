---
name: svc-task-packet
description: "Use for every non-trivial task: starting, resuming, updating plans or task state, coordinating results, and checking remaining work before closing."
metadata: {"version": "16.0.2"}
---

# Task Packet

A Task Packet is a disposable filesystem package for one non-trivial Task. Keep task-local state only when persistence, recovery, or sharing helps manage the work. It does not own durable project truth, Working Methods, acceptance, or a runtime work graph.

## Start or Recover the Current Task

For every non-trivial Task, locate its Packet using project conventions. Read `packet.md` and the active owners needed to recover the objective, authorization, current facts, next action, and completion verification scope. An incomplete Packet is not a reason to create a competing one.

A Skill invocation or Child Assignment does not create another Task or competing Packet; return state changes to the Task owner. Preserve the intended benefit, not just the Human's literal wording.

Before durable mutation, establish the authorized effect, owner, affected consumers, invariants, and proportionate verification. If no Packet exists, create the smallest one at the authorized location, using [the packet asset](assets/packet.template.md) when useful. Ensure the target belongs to this Task and overwrites no existing files. If file tools cannot establish a safe path or preserve state, stop the write and resolve the risk; creation is not guaranteed to be transactional. Use actual task state, not placeholders, in the Human's language.

Check whether a short `packet.md` and optional linear plan can keep foreseeable work and current facts recoverable. If so, continue directly. If independent plan owners, persistent parallel concerns, shared dependencies, or retrieval and editing needs make it insufficient, read [Growth guidance](references/growth.md) before adding structure. Anticipate known upcoming work; do not wait for the Packet to become unwieldy. Maintaining it does not replace substantive progress.

`packet.md` is the short Human entry. Use the Human's language, not Agent-internal vocabulary, and preserve:

- the outcome and material guardrails
- how terminal completion will be verified
- consequential current truth, decisions, and uncertainty
- the current front or next step at useful resolution
- one Human attention item, only when one exists
- a compact Task-map projection when topology has grown

Supporting files do not excuse an empty `packet.md`. Add one only when its distinct owner and retrieval or maintenance needs make the Packet easier to manage.

## Update and Retire

Update the semantic information owner first, then work-control state, then the short Human projection when the Human consequence changed. Mechanical shards such as `decisions-001-010.md` may lower editing cost without becoming new semantic modules; keep a stable entry that owns current meaning.

Integrate accepted durable truth at its project owner during the Task, preferring executable sources for enforceable facts. Discover `svc-specs` by name when that owner or admission is unclear. At close, check for stranded deltas and material residual, then delete the packet under the Consumer project's retention rule without an archive or deletion-time promotion review. This Skill's return leaves the surrounding Task's unmet obligations intact. Agent work-system retrospective is pressure-triggered closing guidance, not a required packet module.

## Grow from the Task's Real Shape

Start with `packet.md` and an optional linear `plan.md` for small Tasks. Persistent parallel concerns, a real shared barrier, or multiple local Plan owners warrant early structure. Use:

- [Planning topology](references/planning.md) for Task, Track, Phase, Cell, Plan, Slice, Step, and Assignment semantics
- [Information modules](references/information.md) for Inquiry, Design, Decision, and cross-return Verification state
- [Growth guidance](references/growth.md) to inspect pressure and migrate in place
- [Task Packet templates](references/templates.md) as opt-in starting shapes, never mandatory scaffolding

Task scale, Task nature, and collaboration pressure influence the shape, but do not select a fixed package type. Most Tasks mix information finding, design, implementation, qualification, and consolidation recursively.

## Authority Boundaries

Human intent, preferences, permissions, material trade-offs, and acceptance remain Human authority; factual and proposed-solution claims remain challengeable with evidence and reasoning. Continue safe investigation and independent authorized work. Ask only for consequential missing Human input, presenting the smallest decision-ready issue.

This Skill grants no write, delegation, external-effect, or acceptance authority. Other Skills are optional guidance, not prerequisites; use qualified project mechanisms and report actual capability or authority gaps without relaxing obligations.
