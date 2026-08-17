# SVC User Manual

## Inspect the Corpus in This Source Tree

Query the guidance you need through the workspace CLI. Ordinary lookup writes
nothing and contacts no service.

```bash
pdm run svc lookup --list --json
pdm run svc lookup --list methods
pdm run svc lookup --path task-packet/
pdm run svc lookup --keyword "task packet growth"
pdm run svc lookup --regex 'bounded-incomplete' --scope both --limit 10
```

For an installed release, use `python -m pip install sustainable-vibe-coding`,
then start with `svc lookup --list`. CLI package and Corpus versions are
independent, so use paths returned by the installed wheel rather than assuming
that they match the current source tree.

`--list [prefix]` expands one Corpus directory level at a time. Use a returned
canonical Markdown path with `--path`, or pass a directory such as
`task-packet` or `task-packet/` to read its `index.md`. The response
always reports the canonical Markdown identity. `--keyword` returns a bounded
relevance-ordered candidate set; `--regex` returns bounded exact path/content
occurrences. A valid search with no matches succeeds with an empty collection.
Lookup reads the SVC Corpus, not the CLI manual; use `svc lookup --help` and
`svc <command> --help` for the current grammar.

## Initialize a Consumer Project

Initialization is dry-run by default. It creates no copied SVC documents and never silently overwrites consumer content.

```bash
svc init /path/to/project --json
svc init /path/to/project --apply <plan-digest>
svc status /path/to/project --json
```

The exact-plan apply may create:

```text
svc.json
.gitignore                 (a bounded generated ignore block for svc.local.json)
AGENTS.md                  (a bounded generated SVC navigation block)
AGENTS.local.md            (ignored, Consumer-owned local Agent guidance)
docs/index.md              (created when absent, with a bounded generated navigation block)
```

`svc.json` is the complete, committed project configuration. Schema v3 records
the adopted Corpus baseline independently from the CLI version and can
optionally declare development capabilities and bounded runs:

```json
{
  "schema_version": 3,
  "corpus_version": "14.0.0"
}
```

`svc.local.json` is an optional, ignored sparse overlay for `dev` and existing
`run` declarations. It must declare schema 3, cannot change the Corpus baseline, create a
local-only run name, or produce an invalid effective configuration. `init`
maintains just its marked ignore block; it never writes a local configuration
file. It creates a missing `AGENTS.local.md` as ignored, Consumer-owned local
Agent guidance and never rewrites it. Supported older configuration is migrated through a plan-first
`svc upgrade --target config`; `init` does not hide configuration migration.

Start with `svc status --json` in any repository. It is read-only and returns a
compact JSON preflight with independent CLI, config, Corpus-baseline,
integration, and workspace facts plus one primary continuation. Status
summarizes declared dev target names and committed run-entry names without executing them; use
`svc dev status` when runtime observation is needed. Every current `--json`
response is one compact JSON value; JSONL is reserved for a future command with
meaningful progress events.

Everything unmarked in `AGENTS.md` and `docs/index.md` remains Consumer-owned.
CLI help is self-sufficient; there is no installed SVC CLI Skill. A clean
legacy generated Skill is retired by an exact init plan, while a modified or
unproven file is never silently deleted. Modified generated navigation or
local-config-ignore blocks stop repair for review.

## Task Packets

Create the standard task-local control surface without overwriting an existing
packet:

```bash
svc task init <task-id> --repo /path/to/project
```

Inspect the packet shape and obtain a bounded growth brief:

```bash
svc task grow <task-id> --repo /path/to/project
```

The command inventories at most two directory levels, reports recognized and
unknown entries, and changes no file. The Agent uses the packaged Task Packet
guidance to make any semantic growth decision.

## Declare and Ensure Development Capabilities

An optional `dev.targets` map declares named capabilities directly. Each target
has a scope (`worktree`, `repository`, or `host`), one readiness probe (`http`,
`tcp`, or `exec`), an executable or manual provisioner, and an optional
target-local executable or manual `stop` action. Default text serves ordinary
Agent/Human use; compact JSON is the deliberate scripts/CI projection:

```bash
svc dev identity --repo /path/to/project --json
svc dev status --repo /path/to/project --json
svc dev status frontend --repo /path/to/project --json
svc dev ensure frontend --repo /path/to/project --json
svc dev stop frontend --repo /path/to/project --json
```

Root `status` summarizes declarations only; `svc dev status` observes declared
targets without starting or taking over a process. `ensure` handles one declared
target, reuses a healthy endpoint, refuses an occupied but unhealthy endpoint,
and does not run a `manual` provisioner. `stop` runs only Consumer-declared
cleanup and never infers authority from a recorded PID. Executable work is coordinated
at the declared scope and releases process authority once readiness succeeds.
Worktree scope is the default and its probe endpoint must prove the resolved
instance; host scope requires a declared `host_key`.

Dev values may interpolate only `${dev.instance}`, `${dev.worktree.id}`, and
`${dev.target}`. Commands are argument arrays, not shell snippets, and their
configured working directories must remain inside the workspace.

## Run One Shared Declared Command

Use a separate `run` map for bounded project-owned commands that Humans,
Agents, editor carriers, or CI should invoke through the same project name:

```json
{
  "schema_version": 3,
  "corpus_version": "14.0.0",
  "run": {
    "check": {
      "argv": ["pdm", "run", "test"],
      "env_files": [".env.shared"],
      "env": {"PYTHONUTF8": "1"}
    }
  }
}
```

```bash
svc run check --repo /path/to/project
svc run --follow <execution-id> --repo /path/to/project
svc run --inspect <execution-id> --repo /path/to/project --json
```

One caller owns the foreground process; concurrent local callers of the same
effective worktree entry follow that execution instead of starting it again.
The execution ID addresses captured stdout/stderr and a bounded receipt for
handoff. A later explicit entry invocation runs again—settled receipts are not
freshness or acceptance claims. Text mode preserves native stdout/stderr and
puts SVC lifecycle facts on stderr; `--json` suppresses native display and
returns one compact receipt.

`svc.local.json` may replace argv, cwd, and env-file arrays and merge inline env
for an existing committed entry. Relative paths resolve from the workspace
root. Environment files are strict and load in order before inline env; raw
environment values are never stored in the receipt. `run` has no shell string,
dependency graph, arbitrary arguments, background mode, readiness, cache,
artifact model, or project-result verdict.

## Analyze Agent Task Evidence

Telemetry acquires one explicitly selected local provider source; analysis reads
one immutable evidence bundle. Neither surface uploads data, contacts a network
service, invokes a model, or claims an audit-completeness verdict. The calling
Agent owns semantic interpretation and conclusions; SVC owns bounded capture,
native fidelity, snapshot identity, and deterministic structural navigation.

```bash
svc telemetry agent-thread list [selection options] [--json]
svc telemetry agent-thread export (--thread-id <id> | --source <path>) --output <absent.zip> [--json]

svc analysis query --schema
svc analysis query --input /path/to/evidence-v3.zip --request <file|->
svc analysis read --schema
svc analysis read --input /path/to/evidence-v3.zip --request <file|->
```

`list` is one bounded inventory surface. It exposes provider lifecycle,
recognition, and local provenance without predicting whether a source will
still be readable when export begins. `export` requires one exact thread ID or
source path and an absent destination, while keeping the source read-only and
refusing overwrite or source/output aliasing. A successful export is a
validated bundle; an interrupted process may leave an invalid partial target
that must be removed before retry. The caller owns where exported evidence is
stored and who may see it; there is no `--include-sensitive`
acknowledgement, `--repo` boundary, TTY gate, or private member-mode promise.

The schema-v3 ZIP authority is `manifest.json`, `native.bin`, and
`native-index.jsonl`. Native provider bytes remain in source order; framing
records only stable IDs, contiguous byte ranges, source coordinates, and
`complete|incomplete` state. One `evidence_id` binds native and framing bytes.
`trajectory.jsonl` may be included as a derived structural cache, but it is not
evidence authority and can be discarded and rebuilt. Its counts, capabilities,
and loss summary likewise remain derived. A schema-v1 or schema-v2 bundle is a
historical cutoff: query/read reject it after bounded identification; recollect
from the provider-local source.

This is a same-user local workflow, not a security sandbox. SVC does not
protect against root, a hostile process under the same account, or adversarial
path replacement. Native evidence may contain all selected provider content;
structural projection and omission are not confidentiality or redaction. The
caller owns storage, access, retention, and disclosure.

`query` is a closed machine-first protocol with `overview` and deterministic
`match` intents. It uses or rebuilds the structural cache and returns evidence
identity, source/capture facts, derived capability/loss status, stable native
and trajectory references, structural ranges, and bounded
predicate matches over record type, role, tool, relationship, native range, or
literal text. It does not accept arbitrary field selection, SQL/JSONPath,
regular-expression programs, joins, grouping, scoring, or natural-language
prompts. `read` is forward-only native reading: start at the beginning or an
exact native reference, optionally include bounded preceding records, and use a
scope-bound cursor to continue. It returns captured native bytes/values with
exact frame and fragment offsets, digests, provenance, and continuation.
Cursors carry typed request scope and are unsigned local state, not
authenticated capabilities. Frame and fragment digests are computed from the
native bytes when read rather than stored as framing authority.
Exact UTF-8 fragments are directly readable as text; arbitrary bytes use a
lossless base64 fallback. Read never filters, reorders, summarizes, or silently
returns normalized text.

Responses distinguish `complete`, `partial`, and `unavailable`; pagination is
not evidence loss. An incomplete acquisition frame remains readable but cannot
produce a projection record. A missing or invalid cache is rebuilt from native
evidence; failed rebuild makes structural query unavailable without preventing
native read. Query/read are JSON-first. Their machine contracts come from
`--schema`; the task-analysis method and authority boundary are part of
`svc analysis --help`, not the SVC Corpus.

The old `telemetry agent-thread analyze` command and Textual navigator are
removed; analysis is now the composition of explicit `query` and native
`read`, with the calling Agent deciding what the evidence means.

## Upgrade Deliberately

The installed package manager owns CLI installation and updates. Project
configuration and Corpus-baseline upgrades remain explicit SVC operations:

```bash
svc status /path/to/project
svc upgrade /path/to/project
svc upgrade /path/to/project --target config --apply <plan-digest>
svc upgrade /path/to/project --target corpus --apply <plan-digest>
```

Config apply performs only a supported exact file transformation and reports
remaining upgrade work. Corpus plans reference the exact packaged migration
guidance; after an Agent/Human reviews and updates Consumer-owned SVC documents,
Corpus apply records only the reviewed `corpus_version` baseline. SVC never
programmatically rewrites those project documents.

## Behavioral SemVer and Releases

SVC uses Behavioral SemVer:

- **MAJOR** changes required obligations, defaults, permission/authority boundaries, task-packet semantics, consumer layout, or a stable CLI/catalog contract.
- **MINOR** adds an optional backward-compatible capability.
- **PATCH** fixes or clarifies the existing protocol without changing those behaviors.

Changie 1.25.1 records each release-relevant change as a tool-native YAML
fragment under `changes/unreleased/` with an explicit `major`, `minor`, or
`patch` kind. Maintainers batch those fragments and merge the generated
`CHANGELOG.md` through an ordinary release-preparation pull request. That merge
starts the standard workflow, which derives the tag and PDM SCM package version
from one Changie version, smoke-tests the installed distribution, publishes
through Trusted Publishing, and creates the GitHub Release. Migration notes
remain optional packaged consumer guidance. See [CONTRIBUTING.md](CONTRIBUTING.md)
for the contributor and maintainer workflow.
