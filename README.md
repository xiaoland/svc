# Sustainable Vibe Coding

Sustainable Vibe Coding (SVC) is a selective-memory framework for AI-assisted software development. It keeps stable, expensive-to-recover truth durable while leaving exploration and task state disposable.

This repository contains the canonical framework, consumer templates, and a tool that builds a linked single-file reference.

## Develop SVC

Requirements: Python 3.11+ and PDM.

```bash
pdm install
pdm run test
pdm run build-monolith
```

`build/monolith.md` is ignored generated output. Edit sources under `src/`, not the monolith.

## Read SVC

1. Read [the framework index](src/index.md) for the consumer minimum and knowledge-owner registry.
2. Read [the working protocol](src/sections/working-protocol.md) for routing, task state, mutation permission, and verification.
3. Open only the relevant owner or optional extension.
4. Load [implementation taste](src/sections/implementation-taste.md) only for non-trivial implementation judgment.

Change history and the current Unreleased migration path live in [CHANGELOG.md](CHANGELOG.md).

## Apply the Minimal Consumer Kernel

A new consumer starts with exactly four durable documents:

```text
AGENTS.md
docs/00-meta/working-protocol.md
docs/00-meta/implementation-taste.md
docs/10-prd/README.md
```

Use these sources:

- customize [the root AGENTS template](src/assets/templates/AGENTS.root.template.md)
- copy [the working protocol](src/sections/working-protocol.md)
- copy [implementation taste](src/sections/implementation-taste.md)
- instantiate [the product-truth template](src/assets/templates/product-truth.template.md)

Create `tasks/` only for active non-trivial work. Add TDD, local `AGENTS.md`, Deployment, Alignment, multi-repo, a glossary, or additional PRD files only when their admission rule is satisfied and real content exists.

## Repository Layout

```text
src/index.md                  framework entry
src/sections/                canonical owner guidance
src/sections/extensions/     pressure-driven extensions
src/assets/templates/        consumer shapes
src/tools/                   documentation tooling
tests/                       tooling and framework contracts
tasks/                       volatile framework work
```
