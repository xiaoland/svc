# AGENTS

This repository is the source of the Sustainable Vibe Coding (SVC) framework, not a consumer project. Keep the framework small, source-first, and mechanically verifiable.

## Knowledge Owners

- Framework purpose, consumer minimum, and owner registry: `src/index.md`
- Working protocol, task minimum, mutation gate, and documentation quality: `src/sections/working-protocol.md`
- Non-trivial implementation judgment: `src/sections/implementation-taste.md`
- Product truth: `src/sections/prd.md`
- Cross-unit technical contracts: `src/sections/product-tdd.md`
- Unit design and local instructions: `src/sections/unit-tdd.md`
- Runtime and operational truth: `src/sections/deployment.md`
- Optional topology and coordination guidance: `src/sections/extensions/`
- Consumer shapes: `src/assets/templates/`
- Release version and Behavioral SemVer evidence: strict release tags,
  append-only `changes/` fragments, same-slug `src/migrations/` notes, and
  `tools/release.py`
- Consumer runtime, project integration, and packaged-resource access: `svc_cli/`
- Catalog/wheel projection and repository tooling: `tools/build_catalog.py`, `pdm_build.py`, and `tools/`
- Monolith behavior: `tools/build_monolith.py` and `tests/`
- Historical release record and future release guidance: frozen `CHANGELOG.md`,
  GitHub Releases, and `CONTRIBUTING.md`
- Volatile work: `tasks/`; delete packets when their task closes, with no archive or deletion-time promotion review.

`build/monolith.md` is generated output, never an editing source.

## Development Workflow

- Runtime: Python 3.11+
- Environment and commands: PDM
- Install: `pdm install`
- Test: `pdm run test`
- Consumer CLI smoke test: `pdm run svc --help`
- Build the installable distribution: `pdm build`
- Build the ignored reference artifact: `pdm run build-monolith`
- Inspect the packaged corpus locally: `pdm run svc lookup --name 'sections/working-protocol\\.md'`
- Search source with `rg`; exclude `tasks/`, `.venv/`, and `build/` unless they are the target.
- Diagnose builder failures from the reported source file and Markdown target; missing local paths and fragments are contract failures.

## Execution Rules

- For non-trivial work, read `src/sections/working-protocol.md` before mutation.
- Load `src/sections/implementation-taste.md` only when a change shapes code structure, boundaries, data, authority, naming, abstraction, or complexity.
- Apply the nearest local `AGENTS.md` as an additive constraint when one exists.
- Edit canonical source first. Update a template only when its consumer-facing shape changes.
- Keep `src/` free of Python runtime and build-tool code; package projections belong under `svc_cli/` and repository tooling under `tools/`.
- Do not add a layer, template, tool, or agent surface without a distinct owner, trigger, consumer, and verification path.
