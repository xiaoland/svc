---
name: svc-task-packet
description: "Create, recover, maintain, grow, and close a Task Packet for every non-trivial task. Use when starting or continuing substantial work, recovering a paused task, changing its plan or information shape, coordinating returns, or checking remaining obligations before completion."
---

# Task Packet

If the current context does not already contain the [common SVC contract](../index.md), read it before acting. This Skill adds guidance within existing authorization; its trigger does not grant effect authority.

A Task Packet is a disposable filesystem package that helps a Human and Agent complete one non-trivial Task. It preserves only task-local state whose persistence, recovery, or sharing lowers control cost. It does not own durable project truth, Working Methods, acceptance, or a runtime work graph.

## Start or Recover the Current Task

For every non-trivial Task, first locate its existing Packet using the project's task location and naming conventions. Read `packet.md` and only the active owners needed to recover the objective, authorization, current truth, next action, and terminal verification boundary. Do not start a competing Packet because the existing one is incomplete.

If none exists, create the smallest Packet at the authorized project location, using [the packet asset](assets/packet.template.md) when useful. Confirm that the target belongs to this Task and does not replace another Task or overwrite existing files. When ordinary file tools cannot establish a safe path or preserve existing state, stop that write and resolve the boundary; the Skill does not promise transactional creation. Fill the entry with actual task state, not unchanged placeholders, and use the Human's language.

Then perform the early [shape preflight](references/growth.md), adding supporting files only for admitted topology or information pressure. Continue the substantive work; a Packet is its control surface, not a substitute for progress.

`packet.md` is the universal short Human entry. Write it in the language used with the Human—not Agent-internal method vocabulary—and keep it sufficient to recover:

- the outcome and material guardrails
- how terminal completion will be verified
- consequential current truth, decisions, and uncertainty
- the current front or next step at useful resolution
- one Human attention item, only when one exists
- a compact Task-map projection when topology has grown

Supporting files are part of the packet, not references that excuse an empty `packet.md`. Create another file only when its distinct owner and retrieval or maintenance pressure make the package cheaper to control.

## Grow from the Task's Real Shape

Start with `packet.md` and, for a small Task, an optional linear `plan.md`. When the Task admits persistent parallel concerns, a real shared barrier, or multiple local Plan owners, stabilize the suitable packet shape early rather than waiting for a monolith to fail. Use:

- [Planning topology](references/planning.md) for Task, Track, Phase, Cell, Plan, Slice, Step, and Assignment semantics
- [Information modules](references/information.md) for Inquiry, Design, Decision, and cross-return Verification state
- [Growth guidance](references/growth.md) to inspect pressure and migrate in place
- [Task Packet templates](references/templates.md) as opt-in starting shapes, never mandatory scaffolding

Task scale, Task nature, and collaboration pressure influence the shape, but do not select a fixed package type. Most Tasks mix information finding, design, implementation, qualification, and consolidation recursively.

## Update and Retire

Update the semantic information owner first, then work-control state, then the short Human projection when the Human consequence changed. Mechanical shards such as `decisions-001-010.md` may lower editing cost without becoming new semantic modules; keep a stable entry that owns current meaning.

Integrate accepted durable truth during the Task; use [Specs](../svc-specs/SKILL.md) when its canonical owner or admission is unclear. At close, check for stranded deltas and material residual, then delete the packet under the Consumer project's retention rule without an archive or deletion-time promotion review. Agent work-system retrospective is pressure-triggered closing guidance, not a required packet module.
