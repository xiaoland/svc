# Sustainable Vibe Coding

Sustainable Vibe Coding (SVC) is a versioned knowledge Corpus and local
development-collaboration CLI for one Human—or a small team—working with
Coding Agents. It helps Agents complete long ambiguous work, improves
Human-Agent judgment per unit of attention, and lowers the cost of evolving
large long-lived systems without turning documentation into a second software
system.

## Core Contract

Product documents own Product what and why. Code, configuration, schemas,
tests, assertions, and runtime checks own mechanically enforceable truth.
Durable technical documents exist only where those surfaces cannot preserve an
expensive contract clearly enough. Active task state remains volatile in a
[Task Packet](task-packet/index.md).

Start non-trivial work with the [Working Protocol](working-protocol/index.md).
It routes by the missing return and current pressure:

| Need | Canonical entry |
| --- | --- |
| local problem-solving method | [Working Methods](methods/index.md) |
| task-local persistence and Human coordination | [Task Packet](task-packet/index.md) |
| delegated work placement | [Sub-agents](sub-agents/index.md) |
| claim qualification | [Verification](verification/index.md) |
| consequence-based design judgment | [Taste](taste/index.md) |
| durable Consumer truth | [Project owners](project/index.md) |
| optional coordination pressure | [Extensions](extensions/index.md) |
| Consumer artifact starting shapes | [Templates](templates/index.md) |
| Corpus baseline change | [Migrations](migrations/index.md) |

## Packaged Consumption

The canonical source is this `src/` tree. The `svc` wheel contains a read-only
projection of every canonical Corpus Markdown document and a machine-readable
catalog. `src/AGENTS.md` is the exact exception: it is maintainer authoring
guidance, not Consumer Corpus. Catalog paths are normalized paths relative to
`src/`, such as `working-protocol/index.md`.

No SVC framework document is copied into a Consumer repository. A project owns
its Product truth, technical decisions, Task Packets, and unmarked
documentation. SVC supplies on-demand guidance and narrowly bounded integration
anchors.

```text
svc lookup --list
svc lookup --list methods
svc lookup --path working-protocol/
svc lookup --keyword "task packet mutation gate"
svc lookup --regex 'mutation gate' --scope both --limit 10
```

`--list [prefix]` expands one logical Corpus level. `--path` reads one exact
Markdown source; a normalized directory address with or without its trailing
slash resolves to that directory's `index.md`, while the returned identity
remains the canonical Markdown path. Keyword search returns bounded
relevance-ordered candidates; regex search returns bounded exact occurrences.
A valid search miss is an empty successful result. Layered `svc --help` owns
CLI grammar.

Every command with `--json` returns one compact JSON value for its settled
result. Exit code `0` means ready, healthy, applied, or no-op; `2` is CLI
syntax; `3` means required action, invalid project state, conflict, or blocked
plan; `4` means release, execution, or local-apply integrity failure.

## Project Adoption and Product Capabilities

`svc init` is plan-first and applies only an exact approved plan digest. The
complete Product contract for Corpus adoption, generated navigation anchors,
configuration baseline, and local overlay lives in [Corpus delivery and
project evolution](project/prd/corpus.md). The current development, run,
Agent-analysis, and managed-external-boundary products are routed from
[Product Truth](project/prd/index.md); their technical and operational
projections remain in Product TDD and Deployment.

Create a Task control surface without overwrite:

```text
svc task init <task-id> --repo <repo>
svc task grow <task-id> --repo <repo>
```

`task init` creates only `tasks/<task-id>/packet.md`. `task grow` is a read-only
shape inventory and growth brief; the Agent makes the semantic change using
the [Task Packet guidance](task-packet/index.md).

## Baselines and Migration

`svc.json` records the Consumer project's reviewed Corpus baseline separately
from the installed CLI. The installed package manager owns CLI updates;
`svc upgrade --target config` migrates supported configuration, while `svc
upgrade --target corpus` selects packaged [migration guidance](migrations/index.md)
and records only the Human/Agent-reviewed baseline. SVC does not rewrite or
claim to verify Consumer-owned documents.

Release-relevant changes use Changie fragments and Behavioral SemVer. A major
release changes a required obligation, default, authority or permission
boundary, Task Packet semantic, Consumer layout, or supported CLI/Catalog
address; minor adds a compatible optional capability; patch restores or
clarifies the existing contract.
