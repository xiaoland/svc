# AGENTS

This repository is the source of the Sustainable Vibe Coding (SVC) framework, not a consumer project. Keep the framework small, source-first, and mechanically verifiable.

## Knowledge Owners

- Framework purpose and Corpus navigation: `src/index.md`
- Corpus authoring and layout rules: `src/AGENTS.md` (maintainer-only; excluded from the packaged Corpus)
- Working Methods: `src/methods/`
- Task Packet semantics and growth: `src/task-packet/`
- Sub-agent work placement: `src/sub-agents/`
- Claim qualification: `src/verification/`
- Design judgment and implementation taste: `src/taste/`
- Product, technical, unit, runtime, and coordination specifications: `src/specs/`
- Consumer Agent-instruction shapes: `src/templates/`
- SVC's own durable Product, technical, and runtime truth: `docs/`
- Corpus migration selection and guides: `src/migrations/`
- Release configuration, version, Behavioral SemVer evidence, and notes:
  `.changie.yaml`, Changie data under `changes/`, generated `CHANGELOG.md`,
  GitHub Releases, and `CONTRIBUTING.md`
- Consumer runtime, project integration, and packaged-resource access:
  `svc_cli/src/svc_cli/`; its tests live under `svc_cli/tests/`
- Catalog/wheel projection: `svc_cli/src/svc_cli/catalog.py`,
  `tools/build_catalog.py`, and `svc_cli/pdm_build.py`
- Root repository-tool behavior: `tools/` and root `tests/`
- Task work and retained task evidence: `tasks/`; retention is task-specific and
  task material is never part of the packaged Corpus.

## Development Workflow

- Runtime: Python 3.11+
- Environment and commands: PDM 2.28+
- Install: `pdm install`
- Test: `pdm run test`
- Consumer CLI smoke test: `pdm run svc --help`
- Build the installable distribution: `pdm build -p svc_cli`
- Inspect the packaged corpus locally: `pdm run svc lookup --path task-packet/`
- Search source with `rg`; exclude `tasks/`, `.venv/`, and `build/` unless they are the target.
- Diagnose builder failures from the reported source file and Markdown target; missing local paths and fragments are contract failures.

## Execution Rules

- For non-trivial work, read `src/index.md` and the governing Corpus owner before mutation.
- Before materially editing the Corpus, read the nearest `src/AGENTS.md` authoring contract.
- Load `src/taste/implementation/index.md` only when a change shapes code structure, boundaries, data, authority, naming, abstraction, or complexity.
- Apply the nearest local `AGENTS.md` as an additive constraint when one exists.
- Edit canonical source first. Update a template only when its consumer-facing shape changes.
- Keep `src/` free of Python runtime and build-tool code; package sources and
  projections belong under `svc_cli/`, and repository tooling belongs under
  `tools/`.
- Do not add a layer, template, tool, or agent surface without a distinct owner, trigger, consumer, and verification path.
