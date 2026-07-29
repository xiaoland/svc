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
  "svc_version": "11.0.0"
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

## Local Agent-Thread Observability

`svc telemetry agent-thread list|export|analyze` is an explicit local observability family for improving SVC from real human-Agent collaboration. It never implies automatic collection, network egress, upload, anonymous metrics, or a model-generated judgment. The first provider adapter reads a validated local Codex rollout from `$CODEX_HOME` (default `~/.codex`) or an explicit source path; it does not require a PATH-installed `codex`, a running App or VS Code extension, or a network connection.

```text
svc telemetry agent-thread list [--archive-state active|archived|all] [--codex-home <path>] [--limit <1-100>] [--json]
svc telemetry agent-thread export --thread-id <uuid> --output /safe/export-dir/evidence.zip --include-sensitive
svc telemetry agent-thread export --source <rollout.jsonl> --output /safe/export-dir/evidence.zip --include-sensitive
svc telemetry agent-thread analyze [--archive-state active|archived|all] [--codex-home <path>]
svc telemetry agent-thread analyze (--input <bundle.zip> | --thread-id <uuid> | --source <rollout.jsonl>) --json
```

`list` keeps the existing non-sensitive schema-v1 envelope and descriptor keys. It does not print message bodies, tool values, reasoning, title, first-user-message preview, workspace/CWD, or full local paths. `--archive-state active|archived|all` filters provider-reported lifecycle before ordering and the safe result `--limit`; `all` is the default and the only mode that includes lifecycle `unknown`. Lifecycle is independent from source availability (`available`, `missing`, `unavailable`, or `unknown`): a missing rollout does not become archived, and an archived thread may still be unavailable. The existing `source_state` field remains a compatibility projection, not lifecycle authority; it may honestly report `unknown` or `unavailable` instead of inferring from a path, and an archived thread with a missing rollout remains `missing`. Unsafe state rows are omitted without spending a result slot. A recognition surface that shows bounded workspace, title, or first-user-message values must be explicitly entered and sensitive; this automation-safe list never emits them. When source rows must be omitted, the successful JSON response adds exactly `"warnings":[{"code":"thread-source-omitted","count":N}]`; it contains no path or rollout-derived content. An empty list with that warning is a degraded inventory, distinct from a missing, corrupt, or unreadable state database failure.

`analyze` without an input or selector requires a TTY and explicitly enters the sensitive local navigator, defaulting to active threads. Its separately bounded Codex query retains at most 5,000 safe rows and reads only exact `cwd`, `title`, and `first_user_message` recognition fields in addition to the safe identity/lifecycle columns; it never selects preview, reasoning, or tool-content columns. Workspace paths are provenance grouped lexically as POSIX, drive, UNC, relative, truncated, or unknown paths and are never resolved or walked. The Textual alternate-screen UI shows bounded title and first-user-message recognition, lifecycle, recency, availability, and deterministic overview/timeline/tool/lane/context/task/terminal/loss views. Control and format characters are escaped only when painted; private recognition and trajectory values are not logged, cached, placed in widget IDs, or emitted as diagnostics. Unavailable sources remain recognizable but disabled. Archive-filter and asynchronous selection generations prevent an older load from replacing a newer one.

`export` requires exactly one explicit thread ID or source, `--include-sensitive`, and an absent destination outside the selected repository. It never selects a latest thread implicitly, writes the provider source, scans task packets, or permits its output to become repository evidence. The result is a schema-v2 ZIP containing exactly private `manifest.json` and canonical `trajectory.jsonl` members. The trajectory is a provider-neutral, intentionally lossy analysis input: provider envelopes, UI/rate-limit/world-state noise, duplicate bookkeeping, and opaque metadata are discarded; messages, context, reasoning, tool values, task references, diagnostics, records, source bytes, and artifact bytes are bounded before retention. The manifest declares capabilities, every frozen loss counter, diagnostics, source status (`stable`, `grew`, `changed`, or `displaced`), and `ready` or `partial` result status. The collector reads only the descriptor-bound initial source extent and does not chase appends; a race can therefore yield honest partial evidence rather than an invented complete transcript. Opaque, unavailable, or redacted reasoning remains so and is never fabricated, decrypted, or recovered.

This artifact is not a raw/debug archive and contains no provider-native transcript, old structural index, copied task file, or derived analysis member. Released schema-v1 raw archives are cut off: SVC adds no reader, converter, re-export selector, or transition mode. Once a bounded root manifest identifies schema v1, analysis fails with `unsupported-agent-thread-bundle-schema` before opening its native, index, or task members; recollection requires an available provider-local source. Codex is the first provider (`codex`, via `codex-rollout-v1`), while normalized records and validation remain provider-neutral.

`analyze --json` requires exactly one explicit schema-v2 bundle, thread ID, or source. A bundle is provider-home independent; a direct thread/source selection runs the same normalizer ephemerally and publishes nothing. `--archive-state` is valid only for the no-selector navigator, and `--codex-home` is invalid with `--input`. Without `--json`, an explicit input or selector also requires a TTY and opens the same human analysis surface; a non-TTY caller must use `--json`. Analysis uses normalized record order—not timestamps or provider-native fields—as authority. It deterministically projects ten dimensions: task evidence, interaction transitions, constraint evidence, tool outcomes, retry/loop candidates, explicit lanes, terminal coverage, SVC signals, context changes, and evidence coverage/loss. The compact schema-v1 Agent JSON contains only bounded structural metrics, stable finding/unknown codes, and same-bundle record references; it does not copy message, reasoning, tool, workspace-path, or provider-native content. Missing capabilities and declared loss reduce a dimension to `partial` or `unavailable` rather than inviting a guess. Analysis performs no network call, model invocation, cross-thread synthesis, or source/output mutation.

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
