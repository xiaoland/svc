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
svc lookup --list --json
svc lookup --path sections/working-protocol.md
svc lookup --keyword "task packet mutation gate"
svc lookup --name 'sections/working-protocol\.md'
svc lookup --name 'assets/templates/AGENTS\..*\.template\.md' --all
```

`--list` returns path-sorted catalog metadata without returning document bodies. Use one returned normalized source-relative path with `--path` to read and integrity-check exactly that authoritative document. Keyword search is deterministic and local; its candidates identify paths and excerpts, which are also resolved through `--path`. `--name` remains the intentional full-path regular-expression surface: it returns one document by default and rejects ambiguity, while `--all` permits deliberately broad reads. Semantic lookup is intentionally not a public command.

Every command with `--json` returns one compact JSON value for its settled
result, including recognized CLI errors; the trailing newline is framing, not
pretty printing. No current command has distinct progress events that justify
JSONL, so JSONL is reserved for a future bounded event stream rather than being
used for list-shaped terminal results. Exit code `0` means a ready, healthy,
applied, or no-op result; `2` is CLI syntax; `3` means required action, invalid
project state, conflict, or blocked plan; and `4` means release integrity,
local apply, or installer failure.

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

`svc.local.json` is an optional, ignored, sparse overlay for `dev` and existing
`run` declarations. It merges objects into the committed configuration and
replaces scalar or array values; it cannot change the schema version, adopted
SVC version, or create a local-only run entry. The effective configuration must
still satisfy schema v2. `init` maintains only its marked `.gitignore` entry
and never creates the local file.

The Codex skill at `.agents/skills/svc/SKILL.md` is a compact router to the installed CLI and corpus, not a copy of canonical guidance. Root `AGENTS.md` and `docs/index.md` remain Consumer-owned from creation. Only their marked SVC navigation blocks, and the installed skill, have generated provenance markers. A user-modified or malformed generated surface blocks refresh rather than being silently replaced.

```text
svc init <repo> --agent codex
svc init <repo> --apply <plan-digest>
svc status <repo> --json
```

`svc status --json` is an Agent's read-only first SVC command in a repository.
It reports `unadopted`, `malformed`, `actionable`, or `healthy` before its
detailed checks, then provides a `next` action and whether it needs Human
authorization. An unadopted repository asks for adoption authorization; it
does not instruct or perform `init` as discovery. Status reports the installed
CLI/corpus version separately from the adopted project version, and reports
missing, outdated, or user-modified generated guidance without claiming
ownership over consumer content. It also lists the selected `dev` profile and
target names as a declaration-only summary: it never probes, starts, or takes
over a target. Use `svc dev status` for runtime observation. Root status also
lists committed run-entry names without selecting or executing them.

## Declared Development Capabilities

Projects may use the optional `dev` section of schema-v2 `svc.json` to name a selected profile and its targets. A target declares its coordination scope, one readiness probe (`http`, `tcp`, or `exec`), a provisioning action (`exec` or `manual`), and bounded timing; its `access` entries describe consumer-facing endpoints. Configuration is strict: unknown fields, invalid effective overlays, symlinks, duplicate JSON keys, non-finite values, and `null` are rejected.

```text
svc dev identity --repo <repo> --json
svc dev status [target] --repo <repo> --json
svc dev ensure <target> --repo <repo> --json
svc dev setup vscode|npm [target] --repo <repo> --plan|--apply <digest> --json
```

`dev identity` exposes the resolved workspace identity for diagnosis. Root
`status` summarizes declarations only; `dev status` observes declared targets
without starting or taking over anything. `dev ensure` handles exactly one named
target: it reuses a healthy endpoint; refuses an endpoint that responds but is
unhealthy; and requires the consumer's manual action when declared. For
executable provisioning, it coordinates only the declared capability scope,
waits for the declared readiness check, then relinquishes process authority
after success. Worktree scope is the default and requires the probe endpoint to
prove the resolved worktree instance; repository scope intentionally shares one
capability, while host scope requires an explicit host key.

Interpolation is limited to `${dev.instance}`, `${dev.worktree.id}`, `${dev.profile}`, and `${dev.target}` in declared dev values. Commands are executed as argument arrays without a shell, and configured working directories must remain inside the workspace.

`svc dev setup` is the optional plan-first bridge to Consumer-owned editor/package surfaces. It adds only marked VS Code Tasks or reserved exact root `package.json` scripts that call `svc dev ensure <target>`; apply requires the current exact digest. It never reads `launch.json`, infers a package manager, creates package metadata, removes orphans, or replaces a conflicting Consumer entry.

## Shared Declared Runs

Projects may declare bounded project-owned commands in a separate direct `run`
map. One entry contains an exact non-shell `argv`, optional `cwd`, ordered
`env_files`, and inline `env`. Relative paths resolve from the workspace root.
The local overlay may replace argv, cwd, and env-file arrays and merge env keys
for an existing committed name. Environment precedence is ambient process,
then declared files in order, then inline values; malformed, missing, or
valueless env-file input fails before execution publication. Environment values
are never written to receipts or SVC output.

```json
{
  "schema_version": 2,
  "svc_version": "11.0.0",
  "run": {
    "check": {"argv": ["pdm", "run", "test"]}
  }
}
```

```text
svc run <entry> [--repo <repo>] [--json]
svc run --follow <execution-id> [--repo <repo>] [--json]
svc run --inspect <execution-id> [--repo <repo>] [--json]
```

The first caller for an effective worktree-local entry owns one foreground
execution; concurrent local callers follow it. Text mode keeps SVC lifecycle
lines on stderr and native stdout/stderr on their corresponding streams.
`--json` suppresses native display and emits one compact receipt on stdout.
Follow replays captured output and waits; inspect returns current facts without
replay or waiting. Owner `Ctrl+C` interrupts the command, follower `Ctrl+C`
only detaches, and ordinary shell `Ctrl+Z`/`bg`/`fg` behavior is retained.

An execution ID addresses local captured output and lifecycle facts only. A
settled invocation is not reused as fresh work, SVC does not interpret project
artifacts or results, and the surface has no dependency graph, arbitrary
arguments, force-new, background, cancel, timeout, readiness, hook, or matcher.
Exit code `2` remains usage, `3` covers configuration/selection/state/domain
errors, and `4` covers start, capture, owner-loss, or authority-store failure;
an exited command otherwise returns its own exit code.

## Local Agent-Thread Evidence and Analysis

`telemetry agent-thread list|export` is the explicit local acquisition surface;
`analysis query|read` is the machine-first consumer surface. The calling Agent
owns semantic interpretation, hypotheses, comparison, and conclusions. SVC
owns only bounded read-only capture, native fidelity, snapshot identity, and
deterministic structural navigation. Neither surface uploads data, contacts a
network service, invokes a model, or promises audit completeness.

```text
svc telemetry agent-thread list [selection options] [--json]
svc telemetry agent-thread export (--thread-id <id> | --source <path>) --output <absent.zip> [--json]

svc analysis query --schema
svc analysis query --input <evidence-v3.zip> --request <file|->
svc analysis read --schema
svc analysis read --input <evidence-v3.zip> --request <file|->
```

The inventory is one bounded list of provider lifecycle, recognition, and
local provenance; it does not predict whether a source will still be readable
when export begins. Export requires one exact selection and an absent
destination, keeps the selected source read-only, refuses overwrite and
source/output aliasing, and leaves output location and exposure with the
caller. A successful export is a validated bundle; if the process is
interrupted, an invalid partial target may remain and must be removed before
retry. The former `--include-sensitive` acknowledgement, `--repo` boundary,
TTY gate, private mode policy, and Textual navigator are removed.

Schema-v3 evidence has a three-member authority core: minimal `manifest.json`,
captured `native.bin`, and `native-index.jsonl` framing. The index gives every
retained byte a deterministic native ID, contiguous range, source coordinate,
and `complete|incomplete` state. One `evidence_id` binds the stored native and
framing bytes; frame and fragment digests are computed when read results need
them. An export may also carry `trajectory.jsonl` as a derived structural
cache. The cache, its counts, capabilities, and loss summary are rebuildable,
do not participate in evidence identity, and never substitute for native
content. Schema-v1 and schema-v2 artifacts are historical cutoffs: SVC
identifies and rejects them before recollection from an available provider
source.

This is a same-user local trust boundary, not a security sandbox. SVC does not
defend against root, a hostile process under the same account, or adversarial
path replacement. Native evidence may contain all selected provider content;
projection allowlists and bounds are structural navigation rules, not
confidentiality or redaction. The caller owns storage, access, retention, and
disclosure.

`query` accepts only the closed `overview` and `match` intents. It uses or
rebuilds the structural cache and returns evidence identity, source/capture
facts, derived capability/loss status, stable refs, structural ranges, and
deterministic bounded predicates over record type, role, tool, relationship,
native range, or literal text. Arbitrary field selection,
SQL/JSONPath, regex programs, joins, grouping, scoring, and natural-language
prompts are outside the contract. `read` is forward-only native reading from
the beginning or an exact native ref, with bounded preceding records and
scope-bound cursors for continuation. It returns captured native bytes/values,
exact ranges and fragments, digests, provenance, capture gaps, and
continuation. Frame and fragment digests are calculated from the returned
native authority rather than trusted from framing metadata. Cursors carry a
typed request scope and remain unsigned local continuation state, not
authenticated capabilities. Exact UTF-8 fragments are directly readable as
text, with base64 reserved as the lossless fallback for arbitrary bytes. Read
never filters, reorders, summarizes, or silently returns normalized content.

Responses use `complete`, `partial`, or `unavailable`; pagination alone never
changes evidence status. Acquisition loss leaves a final incomplete native
frame readable but unavailable for projection. A missing or invalid cache is
rebuilt from the native core; failed rebuild makes structural query unavailable
without invalidating native read. Query/read responses include a compact
packaged method reference. The canonical reasoning method is discoverable with:

```text
svc lookup --path sections/working-protocol.md --json
```

The old `telemetry agent-thread analyze` command, normalized-only schema-v2
authority, and TUI are removed. Use the packaged method and the two explicit
tools together; SVC does not decide what the evidence means.

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

SVC records release-relevant changes as Changie 1.25.1 tool-native YAML
fragments under `changes/unreleased/`. Each fragment explicitly declares a
Behavioral SemVer `major`, `minor`, or `patch` kind. Packaged Markdown migration
notes under `migrations/` are optional consumer guidance; the CLI does not apply
a generic consumer-file migration graph.

## SVC Behavioral SemVer

Version classification follows declared consumer behavior rather than document wording or accidental buggy behavior:

- **MAJOR** changes a required obligation, default behavior, permission or authority boundary, task-packet semantic, consumer layout, or supported stable CLI/catalog contract.
- **MINOR** adds a backward-compatible optional capability or expands accepted input without changing existing obligations or defaults.
- **PATCH** fixes or clarifies the protocol without changing its required behavior, defaults, permission boundary, task-packet semantics, or consumer layout.

An optional additive layout may be MINOR. A fix may change observed faulty behavior and remain PATCH when it restores an already-declared contract. Every release-relevant change records its impact in a Changie fragment; review remains responsible for classification truth. Maintainers batch the fragments into one Changie version and generated `CHANGELOG.md` notes. Merging the release-preparation pull request triggers the standard workflow, which derives the tag and PDM SCM package version from that version, smoke-tests the installed distribution, publishes through Trusted Publishing, and creates the GitHub Release.

## Knowledge Owners

Use the working protocol to resolve an owner from claim semantics, provenance, and diagnosed cause. The registry below names available durable destinations; it does not assign one from an input label alone.

| Truth | Durable owner | Admission |
| --- | --- | --- |
| Mechanically enforceable implementation fact | Source, configuration, schema, test, assertion, or automation | Prefer this owner whenever it can prevent drift directly |
| Product promise, behavior, rules, scope, business language | [PRD](sections/prd.md) | Always keep a minimal product truth; split only for distinct consumers or cadence |
| Repository development, debug, contribution, or release workflow | Root `AGENTS.md`, `CONTRIBUTING.md`, Changie configuration, or executable project configuration | Keep the instruction at the entry used by its consumer |
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
