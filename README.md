# Sustainable Vibe Coding (SVC)

Sustainable Vibe Coding is a selective memory framework for AI-assisted software development. It helps small teams and solo builders keep the right truths durable while leaving volatile exploration in lightweight task space.

This repository contains:

- Source documentation for the SVC framework
- Templates for applying SVC in other repositories
- A monolith builder that compiles linked markdown into one reference file

## Quick Start

### Prerequisites

- Python 3.11 or newer
- PDM

### Setup

```bash
pdm install
```

### Build the Monolith Reference

```bash
pdm run build-monolith
```

Default output is `build/monolith.md`, generated from `src/index.md` and linked markdown under `src/`.

### Run Tests

```bash
pdm run test
```

## Main Commands

```bash
# Build consolidated markdown reference
pdm run build-monolith

# Run unit tests
pdm run test

# Optional direct invocation
python -m src.tools.build_monolith --entry src/index.md --output build/monolith.md --root src
```

## Repository Layout

```text
.
|-- AGENTS.md
|-- CHANGELOG.md
|-- SEQUENCE_OF_USE.md
|-- build/
|   `-- monolith.md
|-- scripts/
|   `-- build_monolith.py
|-- src/
|   |-- index.md
|   |-- sections/
|   |-- assets/
|   |   |-- templates/
|   |   `-- mappings/
|   `-- tools/
|       `-- build_monolith.py
`-- tests/
    `-- test_build_monolith.py
```

## How to Read SVC in This Repository

1. Start with `SEQUENCE_OF_USE.md` for the workflow view.
2. Read `src/index.md` for the framework purpose and principles.
3. Read section docs in `src/sections/` based on your current question.
4. Build and browse `build/monolith.md` when you want a single-file reference.

## Framework Concepts You Will See Often

- Typed input classification: Intent, Constraint, Reality, Artifact
- Reusable mode overlays: Explore, Solidify, Execute, Diagnose
- Durable ownership separation: PRD, Product TDD, Unit TDD, Local AGENTS, Deployment
- Promotion rule: only persist stable, expensive-to-rediscover truth

For detailed definitions and routing guidance, use:

- `src/sections/meta-engine.md`
- `src/sections/ontology.md`
- `src/assets/mappings/durable-destination-map.md`

## Contributor Workflow

1. Edit source markdown in `src/` and templates in `src/assets/templates/`.
2. Rebuild `build/monolith.md`.
3. Run tests.
4. Keep generated output aligned with source changes.

## Versioning and Migration

- Current framework baseline in this repo: v9.5 (see `src/index.md`)
- Change history and migration notes: `CHANGELOG.md`
