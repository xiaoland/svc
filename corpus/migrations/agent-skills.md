# Adopt the Six SVC Agent Skills

Corpus release: 16.0.0.

## Applies When

Use this guide when adopting the v16 framework from the v15 concept-directory Corpus, including projects whose Agent instructions still route guidance through the CLI. This is a framework adoption change; CLI installation and manual configuration migration have separate owners.

## Update the Consumer Entry

Keep persistent Agent-visible authority boundaries and the rule to use [svc-task-packet](../svc-task-packet/SKILL.md) for every non-trivial Task. Resolve its pointer to the actual adopted location. Skill descriptions support conditional discovery but cannot guarantee that a host sees the task-level rule before selecting an entry. Each Skill contains the authority boundaries needed for its own work. The [root instruction asset](../svc-specs/assets/AGENTS.root.template.md) provides a starting shape without prescribing installation or distribution boundaries.

Replace old concept-directory references with the new semantic owners below. There are no old-address aliases. Each Skill directory contains its required instructions, references, and assets. Installers can move those directories independently; no entry requires the repository root or a sibling directory. Discover additional adopted Skills by name when their guidance is useful, without assuming they are installed.

| Old entry | New owner |
| --- | --- |
| Task Packet | [svc-task-packet](../svc-task-packet/SKILL.md), with topology, information, growth, and template-selection references and opt-in assets |
| Working Methods | [svc-methods](../svc-methods/SKILL.md), with Explore, Design, and Implementation references |
| Sub-agents | [svc-sub-agents](../svc-sub-agents/SKILL.md), with Explorer and Executor role contracts |
| Verification | [svc-verification](../svc-verification/SKILL.md) |
| Specifications and Consumer instruction templates | [svc-specs](../svc-specs/SKILL.md), with owner and coordination references and opt-in assets |
| Taste | [svc-taste](../svc-taste/SKILL.md), with Implementation Taste reference |

## Preserve Responsibilities While Changing Navigation

Task Packet still covers every non-trivial Task, including creating, recovering, maintaining, growing, and closing its state. It is not reduced to handoff or parallel work. Use ordinary file tools and the admitted assets at an authorized project location, preserving existing Packet files. The framework does not claim those tools provide the old command's transactional creation guarantees.

Methods still select by the missing return and compose recursively; Explore, Design, and Implementation are not fixed stages. Verification qualifies claims without owning acceptance. Delegated authority stays bounded by the Assignment. Specs and Taste retain their admission and authority distinctions. Moving a document does not authorize a product decision, durable mutation, or external effect.

Replace CLI-mediated framework retrieval and task-template operations with these Skill entries, conditional references, and ordinary file tools. CLI commands are execution and observation tools; use their current `--help` as the command contract. This release does not add a framework installer, routing service, or a promise that every host discovers Skills identically.

## Verify Adoption

From the persistent Consumer entry, begin a representative non-trivial Task and reach Task Packet without loading all six bodies. Copy an individual Skill away from the repository and confirm its instructions and local resources remain usable without the root index or sibling Skills. Check that Methods loads the needed branch and can switch when implementation reveals a real information or design gap. Check every relocated local reference and asset pointer.

These checks establish usable navigation and preserved responsibilities in the observed context. They do not establish a statistical guarantee of model triggering or execution reliability.
