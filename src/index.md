# Sustainable Vibe Coding

Sustainable Vibe Coding (SVC) is a versioned knowledge corpus and a local development-collaboration CLI for small teams using AI-assisted development. It preserves truth that is costly to rediscover without turning copied documentation into a second software system.

## Core Contract

- Product documentation owns product what and why.
- Code, configuration, schemas, tests, assertions, and runtime checks own mechanically enforceable implementation truth.
- Durable technical documents exist only where those surfaces cannot preserve an expensive contract clearly enough.
- Active task state remains volatile under the working protocol and the consumer project's retention rule.

The [working protocol](sections/working-protocol.md) owns routing, task state, mutation permission, and verification. [Implementation taste](sections/implementation-taste.md) is loaded only when a change requires non-trivial implementation judgment.

## Packaged Runtime Consumption

SVC guidance is released inside the `svc` CLI. The canonical source is this `src/` corpus; the wheel contains a read-only projection of every canonical Markdown document plus a generated machine-readable catalog. A catalog path is the normalized path relative to `src/`, such as `sections/working-protocol.md` or `assets/templates/AGENTS.local.template.md`.

No SVC framework document is copied into a consumer repository. There is no consumer-side SVC-managed document class and no `.svc` installation state directory. A project owns its product truth, technical decisions, task packets, and unmarked documentation. SVC supplies on-demand guidance and narrowly bounded integration anchors only.

Query a released corpus locally:

```text
svc lookup --name 'sections/working-protocol\.md'
svc lookup --name 'assets/templates/AGENTS\..*\.template\.md' --all
svc lookup --keyword "task packet mutation gate"
```

`--name` is a full-path regular expression, not a document identifier. It returns one document by default and rejects ambiguity; `--all` permits intentionally broad matches. Keyword search is deterministic and local. Its results identify paths and excerpts; resolve a selected path through `--name` to read the authoritative body. Semantic lookup is intentionally not yet a public command.

Every command supports stable JSON output through `--json`. Exit code `0` means a ready, healthy, applied, or no-op result; `2` is CLI syntax; `3` means required action, invalid project state, conflict, or blocked plan; and `4` means release integrity, local apply, or installer failure.

## Project Adoption

`svc init` is plan-first. Its default plan makes no write. Applying the exact plan digest may only:

```text
svc.json
.gitignore                 (a bounded generated ignore block for svc.local.json)
.agents/skills/svc/SKILL.md
AGENTS.md                  (a bounded marked navigation block)
docs/index.md              (created when absent, with a bounded marked navigation block)
```

`svc.json` is the project's complete, committed SVC configuration. Schema v2 keeps the adoption baseline and may declare development capabilities:

```json
{
  "schema_version": 2,
  "svc_version": "10.0.1"
}
```

Its version means the project says it has adopted that SVC baseline. It does not assert that Consumer-owned documents match a framework snapshot. The installed package manager remains the authority for the executable version. Schema-v1 projects are never rewritten automatically; migrate their configuration deliberately before `init` or `adopt` can write.

`svc.local.json` is an optional, ignored, sparse overlay for the `dev` declaration. It merges objects into the committed configuration and replaces scalar or array values; it cannot change the schema version, adopted SVC version, or any non-`dev` field. The effective configuration must still satisfy schema v2. `init` maintains only its marked `.gitignore` entry and never creates the local file.

The Codex skill at `.agents/skills/svc/SKILL.md` is an operational guide: it explains when and how to use the CLI, but does not copy the canonical SVC corpus. Root `AGENTS.md` and `docs/index.md` remain Consumer-owned from creation. Only their marked SVC navigation blocks, and the installed skill, have generated provenance markers. A user-modified or malformed generated surface blocks refresh rather than being silently replaced.

```text
svc init <repo> --agent codex
svc init <repo> --apply <plan-digest>
svc status <repo>
```

`svc status` reports the installed CLI/corpus version separately from the adopted project version, and reports missing, outdated, or user-modified generated guidance without claiming ownership over consumer content.

## Declared Development Capabilities

Projects may use the optional `dev` section of schema-v2 `svc.json` to name a selected profile and its targets. A target declares its coordination scope, one readiness probe (`http`, `tcp`, or `exec`), a provisioning action (`exec` or `manual`), and bounded timing; its `access` entries describe consumer-facing endpoints. Configuration is strict: unknown fields, invalid effective overlays, symlinks, duplicate JSON keys, non-finite values, and `null` are rejected.

```text
svc dev identity --repo <repo> --json
svc dev status [target] --repo <repo> --json
svc dev ensure <target> --repo <repo> --json
svc dev setup vscode|npm [target] --repo <repo> --plan|--apply <digest> --json
```

`dev identity` exposes the resolved workspace identity for diagnosis. `dev status` observes declared targets without starting or taking over anything. `dev ensure` handles exactly one named target: it reuses a healthy endpoint; refuses an endpoint that responds but is unhealthy; and requires the consumer's manual action when declared. For executable provisioning, it coordinates only the declared capability scope, waits for the declared readiness check, then relinquishes process authority after success. Worktree scope is the default and requires the probe endpoint to prove the resolved worktree instance; repository scope intentionally shares one capability, while host scope requires an explicit host key.

Interpolation is limited to `${dev.instance}`, `${dev.worktree.id}`, `${dev.profile}`, and `${dev.target}` in declared dev values. Commands are executed as argument arrays without a shell, and configured working directories must remain inside the workspace.

`svc dev setup` is the optional plan-first bridge to Consumer-owned editor/package surfaces. It adds only marked VS Code Tasks or reserved exact root `package.json` scripts that call `svc dev ensure <target>`; apply requires the current exact digest. It never reads `launch.json`, infers a package manager, creates package metadata, removes orphans, or replaces a conflicting Consumer entry.

## Update and Migration Guidance

`svc self-update` and project adoption are separate:

```text
svc self-update
svc self-update --apply <plan-digest>
svc adopt <installed-version>
svc adopt <installed-version> --apply <plan-digest>
```

The initial self-update adapter supports only a non-editable `pip` installation in the current interpreter. It plans the exact installer command, performs no project write, and verifies the resulting package version in a fresh interpreter. Unsupported installers and editable development installations are reported without mutation.

After a CLI update, first inspect `svc status`. When a release provides migration guidance, look it up, evaluate the consumer repository's actual facts under its mutation gate, make Consumer-owned changes, and only then apply `svc adopt`. `adopt` writes `svc.json` only; it cannot claim that a human or Coding Agent has completed the required judgment.

The source release metadata in `manifest.json` records corpus version and Behavioral SemVer impact. A future major release declares either a packaged Markdown guide under `migrations/` or a concrete reason why migration guidance is not applicable. The release planner validates that declaration; the CLI does not apply a generic consumer-file migration graph.

## SVC Behavioral SemVer

Version classification follows declared consumer behavior rather than document wording or accidental buggy behavior:

- **MAJOR** changes a required obligation, default behavior, permission or authority boundary, task-packet semantic, consumer layout, or supported stable CLI/catalog contract.
- **MINOR** adds a backward-compatible optional capability or expands accepted input without changing existing obligations or defaults.
- **PATCH** fixes or clarifies the protocol without changing its required behavior, defaults, permission boundary, task-packet semantics, or consumer layout.

An optional additive layout may be MINOR. A fix may change observed faulty behavior and remain PATCH when it restores an already-declared contract. Every release declares its behavioral impact in release metadata; mechanical checks validate bump compatibility while review remains responsible for classification truth.

## Knowledge Owners

Use the working protocol to resolve an owner from claim semantics, provenance, and diagnosed cause. The registry below names available durable destinations; it does not assign one from an input label alone.

| Truth | Durable owner | Admission |
| --- | --- | --- |
| Mechanically enforceable implementation fact | Source, configuration, schema, test, assertion, or automation | Prefer this owner whenever it can prevent drift directly |
| Product promise, behavior, rules, scope, business language | [PRD](sections/prd.md) | Always keep a minimal product truth; split only for distinct consumers or cadence |
| Repository development, debug, contribution, or release workflow | Root `AGENTS.md`, `CONTRIBUTING.md`, or executable project configuration | Keep the instruction at the entry used by its consumer |
| Cross-unit authority, topology, or compatibility contract | [Product TDD](sections/product-tdd.md) | Another unit must rely on it to interoperate safely |
| Expensive internal invariant of one logical unit | [Unit TDD](sections/unit-tdd.md) | It survives refactors and is not cheaply enforced or recovered |
| Durable technical decision and rationale | ADR beside the affected technical owner | Real alternatives and long-lived consequences cannot be recovered cheaply; accepted history is superseded, not rewritten |
| Repeated fragile seam in a physical subtree | Nearest local `AGENTS.md` | A local tripwire or mandatory verification prevents likely recurrence |
| Runtime, packaging, observability, or recovery truth | [Deployment](sections/deployment.md) | Operational behavior is non-trivial |

Active reasoning, evidence, provisional decisions, and bounded artifacts are not durable destinations. Keep them in the [task control surface](sections/working-protocol.md#keep-a-task-control-surface) while work is active.

Before adding any durable surface, require all of the following:

- the claim is stable enough to outlive the current task
- losing it would be expensive or risky
- code, tests, schemas, or automation cannot preserve it better
- a canonical owner and real consumer exist
- useful content exists now

No empty placeholder passes this test.

## Optional Extensions

- [Alignment](sections/extensions/alignment.md): repeated coordination drift remains after normal owners and stable anchors are used.
- [Multi-repo](sections/extensions/multi-repo.md): one product spans repositories and shared truth has a mechanically enforceable freshness contract.

Mono-repo is the default. Extensions add only their distinct pressure-driven contract; they do not replace the core owner model.
