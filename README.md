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
python -m pip install sustainable-vibe-coding==10.0.0

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
.agents/skills/svc/SKILL.md
AGENTS.md                  (a bounded generated SVC navigation block)
docs/index.md              (created when absent, with a bounded generated navigation block)
```

`svc.json` records only the project's adopted SVC baseline (plus its file schema):

```json
{
  "schema_version": 1,
  "svc_version": "10.0.0"
}
```

Everything unmarked in `AGENTS.md` and `docs/index.md` remains Consumer-owned. The Codex skill is a substantial operational guide to `svc` commands, not a duplicate of the framework corpus. Modified generated blocks or skills block refresh for human review.

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
