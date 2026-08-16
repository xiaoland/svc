# Reorganize the SVC Corpus around symmetric capability owners and replace the monolithic Task Packet model with progressive task-local packages

Corpus release: 13.0.0.

### Applies when
A Consumer or automation reads a SVC 12.0.0 Markdown address, uses the flat
Task Packet template, or resolves Agent Task Analysis through the former
Working Protocol section.

### Required change
Update packaged lookup addresses with this complete map:

| 12.0.0 | 13.0.0 |
| --- | --- |
| `sections/working-protocol.md` | `working-protocol/index.md` |
| `sections/prd.md` | `project/prd/index.md` |
| `sections/product-tdd.md` | `project/product-tdd/index.md` |
| `sections/unit-tdd.md` | `project/unit-tdd/index.md` |
| `sections/deployment.md` | `project/deployment/index.md` |
| `sections/implementation-taste.md` | `taste/implementation/index.md` |
| `sections/extensions/alignment.md` | `extensions/alignment/index.md` |
| `sections/extensions/multi-repo.md` | `extensions/multi-repo/index.md` |
| `assets/templates/AGENTS.local.template.md` | `templates/AGENTS.local.template.md` |
| `assets/templates/AGENTS.root.template.md` | `templates/AGENTS.root.template.md` |
| `assets/templates/alignment-change-request.template.md` | `templates/alignment-change-request.template.md` |
| `assets/templates/deployment-runbook.template.md` | `templates/deployment-runbook.template.md` |
| `assets/templates/edit-shared-docs.template.md` | `templates/edit-shared-docs.template.md` |
| `assets/templates/product-tdd.template.md` | `templates/product-tdd.template.md` |
| `assets/templates/product-truth.template.md` | `templates/product-truth.template.md` |
| `assets/templates/task-packet.template.md` | `templates/task-packet/packet.template.md` |
| `assets/templates/task-diagnostics-matrix.template.md` | `templates/task-packet/diagnostic-matrix.template.md` |

`index.md` and the four pre-existing migration guides remain at their
addresses. Agent Task Analysis moves to
`methods/explore/agent-task-analysis.md`, section `Agent Task Analysis`;
update any stored path/section digest pair together.

A Task Packet is now a progressive package. `svc task init` creates only
`packet.md`; select opt-in Plan, Task-map, Cell, Inquiry, Design, Decision,
Diagnostic Matrix, or Verification templates only when their owner and
management pressure exist. `svc task grow` reports the current shape and
changes no file.

The new first-level entries are `working-protocol/`, `task-packet/`,
`methods/`, `sub-agents/`, `verification/`, `project/`, `taste/`,
`extensions/`, `templates/`, and `migrations/`. Use each directory's
`index.md` as its stable semantic entry.

### Verify
Run `svc lookup --list`, resolve every address used by the Consumer, and
load `working-protocol/index.md`,
`methods/explore/agent-task-analysis.md`, and
`templates/task-packet/packet.template.md`. Initialize one temporary Task,
confirm only `packet.md` is created, then run `task grow` and confirm the
packet tree is unchanged. Review and record the Consumer's 13.0.0 Corpus
baseline only after project-owned references and instructions are updated.

### Reference
`index.md` owns Corpus navigation; `task-packet/index.md` owns Task Packet
semantics; `working-protocol/index.md` owns universal Agent control;
`migrations/index.md` explains baseline adoption.
