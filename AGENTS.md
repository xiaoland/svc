# AGENTS

This repository is the source of the Sustainable Vibe Coding (SVC) framework, not a consumer project. Keep the framework small, source-first, and mechanically verifiable.

## Knowledge Owners

- Framework purpose and Corpus navigation: `corpus/index.md`
- Corpus authoring and layout rules: `corpus/AGENTS.md` (maintainer-only; excluded from the packaged Corpus)
- Working Methods: `corpus/methods/`
- Task Packet semantics and growth: `corpus/task-packet/`
- Sub-agent work placement: `corpus/sub-agents/`
- Claim qualification: `corpus/verification/`
- Design judgment and implementation taste: `corpus/taste/`
- Product, technical, unit, runtime, and coordination specifications: `corpus/specs/`
- Consumer Agent-instruction shapes: `corpus/templates/`
- SVC's own durable Product, technical, and runtime truth: `docs/`
- Corpus migration selection and guides: `corpus/migrations/`
- CLI release configuration, version, Behavioral SemVer evidence, and notes:
  `towncrier.cli.toml`, `.changes/cli/`, `cli/pyproject.toml`, generated
  `CLI_CHANGELOG.md`, GitHub Releases, and `CONTRIBUTING.md`
- Corpus release configuration, version, Behavioral SemVer evidence, and notes:
  `towncrier.corpus.toml`, `.changes/corpus/`, `corpus/version.json`, generated
  `CORPUS_CHANGELOG.md`, GitHub Releases, and `CONTRIBUTING.md`
- Consumer runtime, project integration, and packaged-resource access:
  `cli/src/svc_cli/`; its tests live under `cli/tests/`
- Catalog/wheel projection: `cli/src/svc_cli/catalog.py`,
  `tools/build_catalog.py`, and `cli/pdm_build.py`
- Root repository-tool behavior: `tools/` and root `tests/`
- Task work and retained task evidence: `tasks/`; retention is task-specific and
  task material is never part of the packaged Corpus.

## Development Workflow

- Runtime: Python 3.11+
- Environment and commands: PDM 2.28+
- Install: `pdm install`
- Check everything: `pdm run check`
- Consumer CLI smoke test: `pdm run svc --help`
- Build the installable distribution: `pdm build -p cli`
- Inspect the packaged corpus locally: `pdm run svc lookup --path task-packet/`
- Search source with `rg`; exclude `tasks/`, `.venv/`, and `build/` unless they are the target.
- Diagnose builder failures from the reported source file and Markdown target; missing local paths and fragments are contract failures.

## Execution Rules

- For non-trivial work, read `corpus/index.md` and the governing Corpus owner before mutation.
- Before materially editing the Corpus, read the nearest `corpus/AGENTS.md` authoring contract.
- Load `corpus/taste/implementation/index.md` only when a change shapes code structure, boundaries, data, authority, naming, abstraction, or complexity.
- Apply the nearest local `AGENTS.md` as an additive constraint when one exists.
- Edit canonical source first. Update a template only when its consumer-facing shape changes.
- Keep `corpus/` free of Python runtime and build-tool code; package sources and
  projections belong under `cli/`, and repository tooling belongs under
  `tools/`.
- Do not add a layer, template, tool, or agent surface without a distinct owner, trigger, consumer, and verification path.
