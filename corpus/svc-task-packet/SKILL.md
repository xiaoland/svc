---
name: svc-task-packet
description: "Task-local state, plan records, and continuity. Use for every non-trivial Task."
metadata: {"version": "1.0.0"}
---

# Task Packet

A Task Packet is a disposable filesystem package for one non-trivial Task. Keep task-local state only when persistence, recovery, or sharing helps manage the work. It does not own durable project truth, Working Methods, acceptance, or a runtime work graph.

## Start or Recover the Current Task

For every non-trivial Task, locate its Packet using project conventions. Read `packet.md` and the active owners needed to recover the objective, authorization, current facts, next action, and completion verification scope. An incomplete Packet is not a reason to create a competing one. A request with a different outcome is a new Task with its own Packet; a follow-up refining the same outcome stays in the current one.

Distinguish confirmed decisions and observations from proposals and Agent inferences. Judge their authority and reliability by their source, status, and applicable scope, not by their presence in the Packet. Reuse decisions and evidence that still apply; resolve material conflicts or stale claims against the relevant Human decision, canonical owner, or original evidence, then update the record. Recording a proposal does not approve it, and historical questions do not create obligations for the current Task.

A Skill invocation or Child Assignment does not create another Task or competing Packet; return state changes to the Task owner. Preserve the intended benefit, not just the Human's literal wording.

If no Packet exists, create the smallest one at the authorized location, using [the packet asset](assets/packet.template.md) when useful. Check that the path belongs to this Task and preserve existing files and state. Resolve an unsafe path or conflicting state before writing. Use actual task state, not placeholders, in the Human's language.

Check whether a short `packet.md` and optional linear plan can keep foreseeable work and current facts recoverable. If so, continue directly. If independent plan owners, persistent parallel concerns, shared dependencies, or retrieval and editing needs make it insufficient, read [Growth guidance](references/growth.md) before adding structure. Anticipate known upcoming work; do not wait for the Packet to become unwieldy. Maintaining it does not replace substantive progress.

`packet.md` is the short Human entry. Use the Human's language, not Agent-internal vocabulary, and preserve:

- the outcome and material guardrails
- how terminal completion will be verified
- consequential current truth, decisions, and uncertainty
- the current front or next step at useful resolution
- one Human attention item, only when one exists
- a compact Task-map projection when topology has grown

Rewrite `packet.md` to the current state on each update; replace superseded statements instead of adding dated sections, because version control keeps the history. Keep conclusions in the entry and leave hashes, IDs, logs, and temporary paths to supporting evidence. Agent roles, Agent names, and coordination records are Agent-internal vocabulary too.

Supporting files do not excuse an empty `packet.md`. Add one only when its distinct owner and retrieval or maintenance needs make the Packet easier to manage.

## Update and Retire

Update the semantic information owner first, then work-control state, then the short Human projection when the Human consequence changed. Mechanical shards such as `decisions-001-010.md` may lower editing cost without becoming new semantic modules; keep a stable entry that owns current meaning.

Integrate accepted durable truth at its project owner during the Task, preferring executable sources for enforceable facts; `svc-specs` owns owner selection and admission. Move unresolved residual, such as follow-ups, operational or security debt, and pending Human choices, to the project's tracking owner, such as its docs, open-items list, or issue tracker; residual does not wait in a Packet. Close when you deliver the final result and no work remains for the Task: in the same change, check for stranded deltas, move residual, and delete the Packet without an archive or deletion-time promotion review. If Human acceptance is still pending, say so in the delivery and delete the Packet when the Human accepts or turns to unrelated work. When a project rule requires keeping Packets, follow it, mark the Packet closed, and still move durable facts and residual to their owners. This Skill's return leaves the surrounding Task's unmet obligations intact. Agent work-system retrospective is pressure-triggered closing guidance, not a required packet module.

## Plan and Coordinate

Start with `packet.md` and an optional linear plan:

- **Default**: write the plan directly in a `## 计划` section inside `packet.md`.
- **Split to `plan.md`**: when the plan exceeds 30 lines or needs independent revision history.
- **Use a Task Map** (multiple Tracks): when two or more work lines can advance in parallel and their completion times differ by more than one day.

A Task Map names independent Tracks, their convergence points, and the work after convergence. Use:

- [Task Map topology](references/planning.md) for Track, convergence point, and plan semantics
- [Information modules](references/information.md) for Inquiry, Design, Decision, and cross-return Verification state
- [Growth guidance](references/growth.md) to inspect pressure and migrate in place
- [Plan template](assets/plan.template.md) as an opt-in starting shape, never mandatory scaffolding

Task scale, Task nature, and collaboration pressure influence the shape, but do not select a fixed package type. Most Tasks mix information finding, design, implementation, qualification, and consolidation recursively.

## Authority Boundaries

Human intent, preferences, permissions, material trade-offs, and acceptance remain Human authority; factual and proposed-solution claims remain challengeable with evidence and reasoning. Continue safe investigation and independent authorized work. Ask only for consequential missing Human input, presenting the smallest decision-ready issue.

This Skill grants no write, delegation, external-effect, or acceptance authority. Other Skills are optional guidance, not prerequisites; use qualified project mechanisms and report actual capability or authority gaps without relaxing obligations.
