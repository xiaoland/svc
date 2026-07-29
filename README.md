# Sustainable Vibe Coding

Sustainable Vibe Coding (SVC) is a source-first framework delivered as a versioned local corpus and a small development-collaboration CLI. It helps AI-assisted teams retain costly-to-rediscover truth without copying upstream framework documents into every repository.

## Develop SVC

Requirements: Python 3.11+ and PDM.

```bash
pdm install
pdm run test
pdm run build-monolith
pdm run svc --help
pdm build
```

Edit canonical framework content under `src/`, never `build/monolith.md`. `src/` contains only SVC corpus content; Python runtime code is in `svc_cli/`, and repository-only builders/release tools are in `tools/`.

## Use a Released Corpus

Install the CLI, then query the guidance you need. The wheel contains the read-only corpus and a deterministic catalog, so ordinary lookup writes nothing and contacts no service.

```bash
python -m pip install sustainable-vibe-coding==11.0.0

svc lookup --name 'sections/working-protocol\.md'
svc lookup --name 'assets/templates/AGENTS\..*\.template\.md' --all
svc lookup --keyword "task packet mutation gate"
```

`--name` is a full-path regular expression over source-relative SVC document paths—not a document ID. Keyword results are short, deterministic candidates; use a returned path with `--name` to read canonical content. Semantic search is intentionally deferred until a local artifact and quality contract are measured.

## Initialize a Consumer Project

Initialization is dry-run by default. It creates no copied SVC documents and never silently overwrites consumer content.

```bash
svc init /path/to/project --agent codex --json
svc init /path/to/project --apply <plan-digest>
svc status /path/to/project
```

The exact-plan apply may create:

```text
svc.json
.gitignore                 (a bounded generated ignore block for svc.local.json)
.agents/skills/svc/SKILL.md
AGENTS.md                  (a bounded generated SVC navigation block)
docs/index.md              (created when absent, with a bounded generated navigation block)
```

`svc.json` is the complete, committed project configuration. Schema v2 records the adopted baseline and can optionally declare development capabilities:

```json
{
  "schema_version": 2,
  "svc_version": "11.0.0"
}
```

`svc.local.json` is an optional, ignored sparse overlay for only the `dev` configuration. It cannot change the schema or adopted version, and its merged result must remain valid. `init` maintains just its marked ignore block; it never writes a local configuration file. Schema-v1 projects are write-blocked until deliberately migrated to schema v2.

Everything unmarked in `AGENTS.md` and `docs/index.md` remains Consumer-owned. The Codex skill is a substantial operational guide to `svc` commands, not a duplicate of the framework corpus. Modified generated blocks, skills, or local-config ignore section block refresh for human review.

## Declare and Ensure Development Capabilities

An optional `dev` section selects a profile and declares named targets. Each target has a scope (`worktree`, `repository`, or `host`), one readiness probe (`http`, `tcp`, or `exec`), and either an executable or manual provisioning action. Use JSON output for editor or automation integration:

```bash
svc dev identity --repo /path/to/project --json
svc dev status --repo /path/to/project --json
svc dev status frontend --repo /path/to/project --json
svc dev ensure frontend --repo /path/to/project --json
svc dev setup vscode frontend --repo /path/to/project --plan --json
svc dev setup npm frontend --repo /path/to/project --apply <digest> --json
```

`status` only observes; it never starts or takes over a process. `ensure` handles one declared target, reuses a healthy endpoint, refuses an occupied but unhealthy endpoint, and does not run a `manual` provisioner. Executable provisioning is coordinated at the declared scope and releases process authority once readiness succeeds. Worktree scope is the default and its probe endpoint must prove the resolved instance; host scope requires a declared `host_key`.

Dev values may interpolate only `${dev.instance}`, `${dev.worktree.id}`, `${dev.profile}`, and `${dev.target}`. Commands are argument arrays, not shell snippets, and their configured working directories must remain inside the workspace.

`svc dev setup` is a deliberately narrow bridge for consumer-owned files: it can add marked VS Code Tasks or exact root `package.json` scripts that invoke `svc dev ensure <target>`. It is plan-first; `--apply` requires the current exact digest. It never reads `launch.json`, selects a package manager, creates package metadata, or overwrites a conflicting consumer entry.

## Observe Local Agent Threads

The `telemetry` family is explicit local observability for improving SVC, not automatic analytics or an audit-completeness promise. It reads one selected local provider source and can write one private normalized bundle; it never uploads, contacts a network service, collects anonymous metrics, or invokes a model.

```bash
svc telemetry agent-thread list [--archive-state active|archived|all] [--codex-home /path/to/.codex] [--limit 1-100] [--json]
svc telemetry agent-thread export --thread-id <uuid> --output /safe/export-dir/evidence.zip --include-sensitive
svc telemetry agent-thread export --source /path/to/rollout.jsonl --output /safe/export-dir/evidence.zip --include-sensitive
svc telemetry agent-thread analyze [--archive-state active|archived|all] [--codex-home /path/to/.codex]
svc telemetry agent-thread analyze (--input /path/to/evidence.zip | --thread-id <uuid> | --source /path/to/rollout.jsonl) --json
```

`list` keeps the existing non-sensitive schema-v1 envelope and descriptor keys. It does not print message bodies, tool values, reasoning, title, first-user-message preview, workspace/CWD, or full local paths. `--archive-state active|archived|all` filters provider-reported lifecycle before ordering and the safe result `--limit`; `all` is the default and the only mode that includes lifecycle `unknown`. Lifecycle is independent from source availability (`available`, `missing`, `unavailable`, or `unknown`): a missing rollout does not become archived, and an archived thread may still be unavailable. The existing `source_state` field remains a compatibility projection, not lifecycle authority; it may honestly report `unknown` or `unavailable` instead of inferring from a path, and an archived thread with a missing rollout remains `missing`. Unsafe source rows are skipped without spending a slot. A recognition surface that shows bounded workspace, title, or first-user-message values must be explicitly entered and sensitive; this automation-safe list never emits them. A degraded successful JSON response carries only `"warnings":[{"code":"thread-source-omitted","count":N}]`, never a local path or rollout-derived field; an empty list with that warning is distinct from a state-database failure.

`analyze` with no input or selector requires a TTY and explicitly enters a sensitive local navigator, defaulting to active threads. Its separate bounded query retains at most 5,000 safe rows and reads only exact CWD, title, and first-user-message recognition fields in addition to safe identity/lifecycle metadata; preview, reasoning, and tool-content columns remain excluded. Textual groups provider-reported workspace provenance lexically without resolving or walking it, shows unavailable sources as disabled, and exposes deterministic overview, timeline, tool, lane, context, task, terminal, and loss views. Recognition values live only in process memory, control characters are visibly escaped only at paint time, and stale asynchronous loads cannot replace a newer filter or selection.

`export` requires one exact thread ID or source file, `--include-sensitive`, and an absent `.zip` destination outside `--repo`. It never guesses a latest thread, mutates the source, scans task packets, or writes repository evidence. The schema-v2 bundle contains exactly `manifest.json` and canonical `trajectory.jsonl`. It deliberately discards provider envelopes, UI/rate-limit/world-state noise, duplicate bookkeeping, and opaque metadata; bounds retained messages, context, reasoning, tool data, task references, diagnostics, records, source bytes, and artifact bytes; and declares every frozen loss counter. Its manifest distinguishes `stable|grew|changed|displaced` source status from `ready|partial` result status. Opaque, unavailable, or redacted reasoning is not reconstructed or decrypted.

There is no raw/debug member, native transcript, old index, copied task file, derived analysis member, legacy reader, converter, or re-export mode. A released schema-v1 raw archive is unsupported: SVC identifies its bounded root manifest and returns `unsupported-agent-thread-bundle-schema` before opening any native, index, or task member. Recollection requires the original provider-local source. Codex is the first production adapter (`codex`, via `codex-rollout-v1`); normalized records and validation are provider-neutral.

`analyze --json` accepts one schema-v2 bundle or one explicit local thread/source. Bundle analysis needs no provider home; direct analysis normalizes ephemerally and writes no bundle. `--archive-state` is accepted only by the no-selector navigator, while `--codex-home` is rejected with `--input`. Without `--json`, any explicit input or selector also needs a TTY and opens the human analysis surface; non-TTY automation must use `--json`. The deterministic result covers task and interaction evidence, constraints, tool outcomes, retry/loop candidates, explicit lanes, terminal coverage, SVC command/test/build signals, context changes, and evidence coverage/loss. Its bounded Agent JSON carries structural metrics and same-bundle record references, not transcript excerpts, provider paths, native IDs, or tool/reasoning content. Missing capability or declared loss becomes `partial`/`unavailable`; SVC does not invoke a model, contact a network service, or manufacture a conclusion.

## Upgrade Deliberately

The executable and project adoption are deliberately separate:

```bash
svc self-update --json
svc self-update --apply <plan-digest>

svc status /path/to/project
svc lookup --keyword "migration"
svc adopt 10.0.0 /path/to/project --apply <plan-digest>
```

`self-update` changes only a supported non-editable pip installation in the current interpreter. It never changes `svc.json`. After reviewing any packaged migration guidance and applying Consumer-owned changes under the project's mutation gate, `svc adopt` records the new baseline in `svc.json` through another exact plan.

## Behavioral SemVer and Releases

SVC uses Behavioral SemVer:

- **MAJOR** changes required obligations, defaults, permission/authority boundaries, task-packet semantics, consumer layout, or a stable CLI/catalog contract.
- **MINOR** adds an optional backward-compatible capability.
- **PATCH** fixes or clarifies the existing protocol without changing those behaviors.

Append-only change fragments and the tag-range release planner make impact
reviewable. GitHub Releases are the canonical future human release record; the
Python package is the installation projection. See
[CONTRIBUTING.md](CONTRIBUTING.md) for commit, fragment, migration-note, and
tag-authoritative release rules.

## Repository Layout

```text
src/                         canonical SVC corpus
svc_cli/                     installable Python runtime
tools/                       catalog, monolith, and release tooling
pdm_build.py                 wheel corpus projection hook
tests/                       contract and fixture tests
tasks/                       volatile work packets
```
