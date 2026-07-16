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

Edit canonical framework content under `src/`, never `build/monolith.md`. `src/` contains only SVC corpus content and release metadata; Python runtime code is in `svc_cli/`, and repository-only builders/release tools are in `tools/`.

## Use a Released Corpus

Install the CLI, then query the guidance you need. The wheel contains the read-only corpus and a deterministic catalog, so ordinary lookup writes nothing and contacts no service.

```bash
python -m pip install sustainable-vibe-coding==10.0.1

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
  "svc_version": "10.0.1"
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

## Capture Local Agent-Thread Evidence

The `telemetry` family is explicit local evidence capture, not automatic analytics. It reads a selected local provider snapshot and writes one private archive; it never uploads, contacts a network service, or collects anonymous metrics.

```bash
svc telemetry agent-thread list [--codex-home /path/to/.codex] [--json]
svc telemetry agent-thread export --thread-id <uuid> --output /safe/export-dir/evidence.zip --include-sensitive
svc telemetry agent-thread export --source /path/to/rollout.jsonl --output /safe/export-dir/evidence.zip --include-sensitive
```

`list` exposes non-sensitive selection metadata only. `export` requires an exact thread ID or an exact source file; it never guesses a latest thread. Its absent `.zip` destination must be outside `--repo`, preventing an export or its temporary file from becoming task-packet evidence. `--include-sensitive` is a deliberate acknowledgement to copy raw conversation, tool arguments/results, and reasoning fields wherever the provider makes them available. The export is limited to provider-obtainable data: opaque, unavailable, or redacted reasoning is not reconstructed or decrypted. Codex is the first provider (`codex`, via the `codex-rollout-v1` adapter), using local rollout data from Codex App or the VS Code extension without requiring the `codex` CLI; the `agent-thread` surface leaves a seam for future providers.

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

Towncrier fragments and the release planner make the impact reviewable. GitHub Releases are the canonical release record; the Python package is the installation projection. See [CONTRIBUTING.md](CONTRIBUTING.md) for commit, fragment, and release workflow rules.

## Repository Layout

```text
src/                         canonical SVC corpus and release metadata
svc_cli/                     installable Python runtime
tools/                       catalog, monolith, and release tooling
pdm_build.py                 wheel corpus projection hook
tests/                       contract and fixture tests
tasks/                       volatile work packets
```
