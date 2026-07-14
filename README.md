# Sustainable Vibe Coding

Sustainable Vibe Coding (SVC) is a selective-memory framework and executable change protocol for AI-assisted software development. It keeps stable, expensive-to-recover truth durable while leaving exploration and task state disposable.

This repository contains the canonical framework, versioned consumer manifest, migration CLI, consumer templates, and a tool that builds a linked single-file reference.

## Develop SVC

Requirements: Python 3.11+ and PDM.

```bash
pdm install
pdm run test
pdm run build-monolith
pdm run svc --help
pdm build
```

`build/monolith.md` is ignored generated output. Edit sources under `src/`, not the monolith.

## Read SVC

1. Read [the framework index](src/index.md) for the consumer minimum and knowledge-owner registry.
2. Read [the working protocol](src/sections/working-protocol.md) for routing, task state, mutation permission, and verification.
3. Open only the relevant owner or optional extension.
4. Load [implementation taste](src/sections/implementation-taste.md) only for non-trivial implementation judgment.

Change history and the current Unreleased migration path live in [CHANGELOG.md](CHANGELOG.md).

## Consume a Versioned Release

Install a specific SVC distribution, then plan initialization without writing:

```bash
python -m pip install sustainable-vibe-coding==10.0.0
svc init /path/to/consumer
```

Inspect the operations and plan digest. Apply only that exact plan:

```bash
svc init /path/to/consumer --apply <plan-digest>
svc status /path/to/consumer
```

An initialized consumer has four durable documents:

```text
AGENTS.md
docs/00-meta/working-protocol.md
docs/00-meta/implementation-taste.md
docs/10-prd/README.md
```

and one Generated control file:

```text
.svc/state.json
```

The release manifest classifies every artifact explicitly:

- **SVC-managed** protocol files are replaced only when their installed digest still matches.
- **Consumer-owned** files are created only when absent and never overwritten during upgrade.
- **Generated** files are reproducible projections and never knowledge owners.

The canonical inventory is [the release manifest](src/manifest.json). Use `svc migrate` for upgrades; it is dry-run by default, requires an exact plan digest to apply, executes only adjacent registered migrations, and rolls back a failed or interrupted commit from its persistent journal.

For v9.8 consumers, declare the otherwise unobservable source version:

```bash
svc migrate /path/to/consumer --from-version 9.8.0 --to 10.0.0
```

The first plan may require manual resolution of Consumer-owned layout and unknown legacy files. Resolve those blockers, rerun the plan, then apply its new digest. SVC never guesses ownership or silently deletes content without installed provenance.

Create `tasks/` only for active non-trivial work. Add TDD, local `AGENTS.md`, Deployment, Alignment, multi-repo, a glossary, or additional PRD files only when their admission rule is satisfied and real content exists.

## Repository Layout

```text
src/index.md                  framework entry
src/manifest.json             versioned release inventory
src/svc_cli/                  consumer CLI and migration engine
src/sections/                canonical owner guidance
src/sections/extensions/     pressure-driven extensions
src/assets/templates/        consumer shapes
src/tools/                   documentation tooling
pdm_build.py                 canonical-source wheel projection
tests/                       tooling and framework contracts
tasks/                       volatile framework work
```
