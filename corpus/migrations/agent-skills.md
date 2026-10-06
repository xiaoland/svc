# Adopt the Six SVC Agent Skills

Target Corpus release: 15.0.0 (in preparation).

## Applies When

Use this guide when adopting the v15 framework or aligning an earlier development checkout with its final Skill layout, including projects whose Agent instructions still route guidance through the CLI. This is a framework adoption change; CLI installation and manual configuration migration have separate owners.

## Update the Consumer Entry

Keep persistent Agent-visible authority boundaries and the rule to use [svc-task-packet](../svc-task-packet/SKILL.md) for every non-trivial Task. Resolve its pointer to the actual adopted location. Skill descriptions support conditional discovery but cannot guarantee that a host sees the task-level rule before selecting an entry. Each Skill contains the authority boundaries needed for its own work. The [root instruction asset](../svc-specs/assets/AGENTS.root.template.md) provides a starting shape without prescribing installation or distribution boundaries.

Replace old concept-directory references with the new semantic owners below. There are no old-address aliases. Each Skill directory contains its required instructions, references, and assets. Installers can move those directories independently; no entry requires the repository root or a sibling directory. Discover additional adopted Skills by name when their guidance is useful, without assuming they are installed.

| Old entry | New owner |
| --- | --- |
| Task Packet | [svc-task-packet](../svc-task-packet/SKILL.md), with topology, information, growth, and template-selection references and opt-in assets |
| Working Methods; draft `svc-methods` | [svc-workflow](../svc-workflow/SKILL.md), with staged/iterative Human collaboration and Explore, Design, Planning, and Implementation |
| Verification | [svc-verification](../svc-verification/SKILL.md), owning V&V criteria, evidence, and feedback |
| Agent collaboration | [svc-agent-collaboration](../svc-agent-collaboration/SKILL.md), covering delegation, result adoption, coordination, and responsibility transfer |
| Specifications and Consumer instruction templates | [svc-specs](../svc-specs/SKILL.md), with owner and coordination references and opt-in assets |
| Taste | [svc-taste](../svc-taste/SKILL.md), with Implementation Taste reference |

## Preserve Responsibilities While Changing Navigation

Task Packet still covers every non-trivial Task, including creating, recovering, maintaining, growing, and closing its state. It is not reduced to handoff or parallel work. Use ordinary file tools and the admitted assets at an authorized project location, preserving existing Packet files. The framework does not claim those tools provide the old command's transactional creation guarantees.

Workflow separates Human collaboration from reusable methods. Staged collaboration advances within a jointly confirmed delivery scope; iterative collaboration maintains the goal while requirements and routes evolve through feedback. Neither mode grants permissions, requires approval for every engineering step, nor excuses inadequate design or product evidence. Methods select by the missing return and compose recursively; V&V qualifies claims without owning acceptance. Delegated authority stays bounded by the Assignment. Specs and Taste retain their admission and authority distinctions. Moving a document does not authorize a product decision, durable mutation, or external effect.

Replace CLI-mediated framework retrieval and task-template operations with these Skill entries, conditional references, and ordinary file tools. CLI commands are execution and observation tools; use their current `--help` as the command contract. CLI installation and project adoption remain separate from this framework guidance; the release does not promise that every host discovers Skills identically.

## Align Earlier v15 Draft Installations

The Methods upgrade to Workflow belongs to the same unreleased v15 development line. The current release layout contains six Skills, including independent `svc-verification`; archives using the retired `svc-methods` entry are not supported release inputs. Replace the old Methods entry and Consumer pointers with the actual installed `svc-workflow/SKILL.md`, without a forwarding alias. Methods references keep their names inside Workflow. Workflow discovers specialist V&V guidance by the name `svc-verification`, without requiring an installation layout or sibling path. If an intermediate draft installation placed V&V references inside Workflow, update Workflow and install or update independent Verification through the original manager; do not retain competing copies.

Prepare the target release and confirm its Workflow entry can be installed before removing old files. At each original host and scope, explicitly inspect the retired names and apply reviewed removal plans, then install the replacement. These project/Codex commands are read-only until repeated with `--apply <plan-digest>`:

```console
svc skills status --repo /path/to/project --agent codex --skill svc-methods --json
svc skills install --repo /path/to/project --agent codex --version 15.0.0 --skill svc-workflow --json
svc skills remove --repo /path/to/project --agent codex --skill svc-methods --json
svc skills install --repo /path/to/project --agent codex --version 15.0.0 --skill svc-workflow --json
```

Use the actually available target release version; preparation of v15 does not establish online availability. Select `--agent claude` or `--global` when that was the original installation. These are separate transactions; review fresh plans after mutations or failures. Explicit old names still identify their original installation records for status and removal. Default update does not rename them or install a missing Workflow entry. Update the other actually installed current names with explicit selections, then refresh `svc skills adopt` in each affected project, supplying `--skills-dir` for an external or global installation when needed. Consumer-authored pointers outside managed blocks need separate review.

Modified, unrecorded, incomplete, or foreign-managed files remain protected. Preserve local customizations and resolve ownership rather than deleting files or records to bypass a refusal. For Vercel Skills, OpenSkills, or another manager, replace entries through that manager and preserve its file and lock ownership; SVC adoption can refer to the resulting installation without taking ownership. Earlier `svc-sub-agents` drafts also need the [Agent collaboration transition](agent-collaboration.md); the two content changes do not create separate release versions.

Preserve the V&V relationship between product purpose, behavior constraints, observations, and oracles. Workflow owns Human collaboration and working methods, including the minimum coordination needed to design a judgment basis. Independent Verification owns specialist V&V guidance for obtaining and interpreting evidence and feeding contradictions back to requirements, design, or implementation. An oracle must detect requirement-relevant behavior differences while accepting implementation changes that preserve all relevant requirements. Product validation remains relevant throughout the work rather than becoming a final test phase. Planning as a method forms and revises a limited route; Task Packet retains persistent plan state and topology. Project-specific commit, deployment, installation, or account permissions are not imported from a workflow example.

## Verify Adoption

From the persistent Consumer entry, begin a representative non-trivial Task and reach Task Packet without loading all six bodies. Copy an individual Skill away from the repository and confirm its instructions and local resources remain usable without the root index or sibling Skills. Check that Workflow can load the matching method without consulting both collaboration references and discover Verification by name when criteria, evidence, or feedback require specialist guidance. Each Skill must still fulfill its own minimum responsibilities when the other is absent, and identify actual capability or authority gaps rather than claiming success. Check every relocated local reference and asset pointer.

These checks establish usable navigation and preserved responsibilities in the observed context. They do not establish a statistical guarantee of model triggering or execution reliability.
