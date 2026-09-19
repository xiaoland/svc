# Task Packet

A Task Packet is a disposable filesystem package that helps a Human and Agent
complete one non-trivial Task. It preserves only task-local state whose
persistence, recovery, or sharing lowers control cost. It does not own durable
project truth, Working Methods, acceptance, or a runtime work graph.

`packet.md` is the universal short Human entry. Write it in the language used
with the Human—not Agent-internal method vocabulary—and keep it sufficient to
recover:

- the outcome and material guardrails
- how terminal completion will be verified
- consequential current truth, decisions, and uncertainty
- the current front or next step at useful resolution
- one Human attention item, only when one exists
- a compact Task-map projection when topology has grown

Supporting files are part of the packet, not references that excuse an empty
`packet.md`. Create another file only when its distinct owner and retrieval or
maintenance pressure make the package cheaper to control.

## Grow from the Task's Real Shape

Start with `packet.md` and, for a small Task, an optional linear `plan.md`.
When the Task admits persistent parallel concerns, a real shared barrier, or
multiple local Plan owners, stabilize the suitable packet shape early rather
than waiting for a monolith to fail. Use:

- [Planning topology](planning.md) for Task, Track, Phase, Cell, Plan, Slice,
  Step, and Assignment semantics
- [Information modules](information.md) for Inquiry, Design, Decision, and
  cross-return Verification state
- [Growth guidance](growth.md) to inspect pressure and migrate in place
- [Task Packet templates](./templates/index.md) as opt-in starting
  shapes, never mandatory scaffolding

Task scale, Task nature, and collaboration pressure influence the shape, but
do not select a fixed package type. Most Tasks mix information finding,
design, implementation, qualification, and consolidation recursively.

## Update and Retire

Update the semantic information owner first, then work-control state, then the
short Human projection when the Human consequence changed. Mechanical shards
such as `decisions-001-010.md` may lower editing cost without becoming new
semantic modules; keep a stable entry that owns current meaning.

Integrate accepted durable truth during the Task. At close, check for stranded
deltas and material residual, then delete the packet under the Consumer
project's retention rule without an archive or deletion-time promotion review.
Agent work-system retrospective is pressure-triggered closing guidance, not a
required packet module.
