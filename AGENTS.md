# AGENTS

This repository is the SVC framework source itself, not an application service. Keep changes source-first, minimal, and verifiable.

## Quick Operating Loop

1. Classify the request as Intent, Constraint, Reality, or Artifact.
2. Identify the durable owner for that truth before editing.
3. Choose the current working posture: Explore, Solidify, Execute, or Diagnose.
4. Load only the minimum needed references.
5. Edit source files, verify, then promote stable knowledge.

Input type decides ownership. Mode decides posture. Mode never overrides ownership.

## Repository-Specific Sources of Truth

- Framework narrative and principles: `src/index.md`
- Framework section details: `src/sections/`
- Reusable templates: `src/assets/templates/`
- Durable routing map: `src/assets/mappings/durable-destination-map.md`
- Build logic: `src/tools/build_monolith.py`
- Test coverage for builder behavior: `tests/test_build_monolith.py`

Generated artifact:

- `build/monolith.md` is generated output. Do not treat it as the editing source.

## Durable Owner Cheat Sheet

- Intent: update product-level behavior guidance first.
- Constraint: update technical boundary guidance without rewriting product intent.
- Reality: gather evidence first, then fix; no evidence, no modification.
- Artifact: keep tactical unless reuse and stability are proven.

When ownership is ambiguous, resolve route first using:

- `src/sections/meta-engine.md`
- `src/sections/ontology.md`

## Progressive Read Order

Read the smallest useful set:

1. `AGENTS.md` (this file)
2. `src/index.md`
3. Relevant section files in `src/sections/`
4. Relevant templates in `src/assets/templates/`

If a local `AGENTS.md` exists in a target subtree, apply it as additive constraints.

## Guardrails

- Keep source edits in `src/` and regenerate `build/monolith.md`.
- Prefer existing terminology and layer boundaries over introducing new vocabulary.
- Avoid framework bloat: add durable documentation only when it is stable and costly to rediscover.
- Preserve current public command surface in `pyproject.toml` unless change is intentional.

## Verification Commands

```bash
pdm run build-monolith
pdm run test
```

## Negotiation Triggers

Stop and request human confirmation when:

- A change conflicts with existing layer ownership or established claims.
- Blast radius crosses multiple durable owners and the correct owner is unclear.
- Evidence is insufficient for a bug-fix or architectural decision.
- A requested shortcut weakens maintainability, readability, or verifiability.
