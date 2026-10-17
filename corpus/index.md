# Sustainable Vibe Coding

SVC is Agent-facing guidance for completing software work with a Human while keeping authority, task state, durable truth, and verification understandable. Workflow and Task Packet apply to every non-trivial Task; the other Skills supply pressure-specific guidance. The six Skills do not define a fixed pipeline or confer permissions.

Each Skill is a self-contained directory: its required instructions and resources travel with it. Root documents provide repository navigation and release adoption information, not prerequisites for running a Skill. Each entry states its own authority and return boundaries; references to other Skills are conditional discovery suggestions by name.

For full SVC adoption, keep the project-visible rule to read and use `svc-workflow` and use `svc-task-packet` for every non-trivial Task. Recover an existing Packet rather than creating a competing one. Skill descriptions state their triggers but cannot guarantee host selection; use the Consumer instruction asset below to establish these task-level rules.

## Guidance Entries

Read Workflow for every non-trivial Task and maintain its Task Packet. Load additional Skills and references only for the current pressure; the map does not require loading them all.

| Skill | When to use |
| --- | --- |
| [svc-task-packet](svc-task-packet/SKILL.md) | Start, recover, maintain, grow, and close every non-trivial Task |
| [svc-workflow](svc-workflow/SKILL.md) | Read and use for every non-trivial Task; guide Human–Agent collaboration and autonomous work with Explore, Design, Planning, and Implementation |
| [svc-verification](svc-verification/SKILL.md) | Establish, use, or improve criteria, evidence, and feedback; judge conformance, fitness, and evidence reuse |
| [svc-agent-collaboration](svc-agent-collaboration/SKILL.md) | Assign or accept Agent work, seek independent judgment, adopt results, coordinate dependencies, or transfer responsibility |
| [svc-specs](svc-specs/SKILL.md) | Find or update the canonical owner of durable project knowledge |
| [svc-taste](svc-taste/SKILL.md) | Judge real design or implementation alternatives by their consequences |

For framework adoption across releases, use the applicable [migration guide](migrations/index.md). For a Consumer project's persistent Agent entry, use the [root instruction starting shape](svc-specs/assets/AGENTS.root.template.md); it must point to the actual adopted guidance, not assume a particular installation layout.
