# Sustainable Vibe Coding

SVC is Agent-facing guidance for completing software work with a Human while keeping authority, task state, durable truth, and verification understandable. The six Skills below provide conditional working guidance; they do not define a fixed pipeline or confer permissions.

Each Skill is a self-contained directory: its required instructions and resources travel with it. Root documents provide repository navigation and release adoption information, not prerequisites for running a Skill. Each entry states its own authority and return boundaries; references to other Skills are conditional discovery suggestions by name.

For full SVC adoption, keep the project-visible rule to use `svc-task-packet` for every non-trivial Task. Recover an existing Packet rather than creating a competing one. Skill discovery alone does not guarantee that this task-level rule is present before the host selects an entry; use the Consumer instruction asset below to establish it.

## Conditional Guidance

Read only the entry whose pressure is present. Each entry routes directly to its own references and to other owners when needed; the map does not require loading them all.

| Skill | When to use |
| --- | --- |
| [svc-task-packet](svc-task-packet/SKILL.md) | Start, recover, maintain, grow, and close every non-trivial Task |
| [svc-methods](svc-methods/SKILL.md) | Need non-obvious information, a coherent solution, or realization of an authorized bounded change |
| [svc-verification](svc-verification/SKILL.md) | Qualify a consequential claim or decide whether prior evidence can be reused |
| [svc-sub-agents](svc-sub-agents/SKILL.md) | Compare work placement or manage a bounded Assignment and its return |
| [svc-specs](svc-specs/SKILL.md) | Find or update the canonical owner of durable project knowledge |
| [svc-taste](svc-taste/SKILL.md) | Judge real design or implementation alternatives by their consequences |

For framework adoption across releases, use the applicable [migration guide](migrations/index.md). For a Consumer project's persistent Agent entry, use the [root instruction starting shape](svc-specs/assets/AGENTS.root.template.md); it must point to the actual adopted guidance, not assume a particular installation layout.
