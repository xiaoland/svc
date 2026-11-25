# Sustainable Vibe Coding

SVC is Agent-facing guidance for completing software work with a Human while keeping authority, task state, durable truth, and verification understandable. Workflow, Task Packet, and Specs apply to every non-trivial Task; the other Skills supply pressure-specific guidance. Choose and combine Skills for the current work under project and Human authority.

Each Skill is a self-contained directory: its required instructions and resources travel with it. Root documents provide repository navigation and release adoption information. Each entry states its own authority and return boundaries; references to other Skills are conditional discovery suggestions by name.

For full SVC adoption, keep the project-visible rule to read and use `svc-workflow`, use `svc-task-packet`, and use `svc-specs` for every non-trivial Task. Workflow guides Human–Agent collaboration and methods for understanding, designing, planning, implementing, and delivering software work. Its entry supplies the shared judgment actions, basic staged protocol, and direct routes by the next result needed. Apply judgment throughout the work; references develop particular methods and collaboration situations. The collaboration agreement bounds the result currently due and the authority to produce it. Recover the current Packet. Keep durable truth at its canonical owner. Skill descriptions summarize guidance and use conditions; use the Consumer instruction asset below to establish the task-level rules.

## Guidance Entries

Read Workflow and Specs for every non-trivial Task and maintain its Task Packet. Load additional Skills and references for the current pressure.

| Skill | When to use |
| --- | --- |
| [svc-task-packet](svc-task-packet/SKILL.md) | Start, recover, maintain, grow, and close every non-trivial Task |
| [svc-workflow](svc-workflow/SKILL.md) | Read and use for every non-trivial Task; choose and combine working methods, form and revise judgments, and apply the Human collaboration agreement |
| [svc-verification](svc-verification/SKILL.md) | Design criteria and observations; obtain, reuse, and judge evidence; improve feedback |
| [svc-agent-collaboration](svc-agent-collaboration/SKILL.md) | Assign or accept Agent work, seek independent judgment, adopt results, coordinate dependencies, or transfer responsibility |
| [svc-specs](svc-specs/SKILL.md) | Use for every non-trivial Task; find or update the canonical owner of durable project knowledge |
| [svc-taste](svc-taste/SKILL.md) | Judge design or implementation choices when Product or Technical facts leave the choice unresolved |
| [svc-writing](svc-writing/SKILL.md) | Draft or revise substantial prose for human readers: documentation, design documents, issues, PR descriptions, reports |

For framework adoption across releases, use the applicable [migration guide](migrations/index.md). For a Consumer project's persistent Agent entry, use the [root instruction starting shape](svc-specs/assets/AGENTS.root.template.md); it must point to the actual adopted guidance, not assume a particular installation layout.
