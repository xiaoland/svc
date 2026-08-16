# <Project Name>

<One sentence describing the product or repository.>

Replace every angle-bracket placeholder. Delete any optional owner row that is not admitted; a completed root must contain no placeholder or `absent` marker.

## Repository Map

- `<path>`: <crucial responsibility>
- `<path>`: <crucial responsibility>
- `docs/`: durable project knowledge
- `tasks/`: active task-local state

## Knowledge Owners

- SVC Working Protocol: `svc lookup --path working-protocol/index.md`
- SVC implementation taste, when needed: `svc lookup --path taste/implementation/index.md`
- Product what and why: `docs/10-prd/README.md`
- Cross-unit technical contracts, when admitted: `<path>`
- Unit design and local seam guidance, when admitted: `<paths>`
- Technical decisions and ADRs, when admitted: `<path>`
- Runtime, packaging, migration, observability, and recovery truth, when admitted: `<path>`
- Nearer `AGENTS.md` files are additive for their subtree.
- Task retention: <concrete deletion or time-to-live rule; no archive or deletion-time promotion review>

## Development Workflow

- Runtime and package manager: <versions/tools>
- Install: `<command>`
- Test: `<command>`
- Lint/type/check: `<command>`
- Build/package: `<command>`
- Smoke/debug entry: `<command, inspector, or harness>`
- Runtime data: `<state, database, logs, cache, and config paths>`
- Environment overrides: `<locations>`

Keep these entries executable and project-specific. Put durable behavior or architecture in its knowledge owner, not here.

## Execution Rules

- When SVC project state, migration, development capabilities, shared runs, or
  framework guidance are relevant, use the installed `svc` CLI. Discover CLI
  usage through `svc --help` and `svc <command> --help`; `svc lookup` searches
  the packaged SVC Corpus rather than the CLI manual.
- Load `working-protocol/index.md` through `svc lookup` for non-trivial work and follow its permission boundary.
- Load `taste/implementation/index.md` through `svc lookup` only when its implementation trigger is present.
- Read the nearest local `AGENTS.md` before editing a governed subtree.
- Prefer code, configuration, schemas, tests, and automation for mechanically enforceable truth.
- Follow the Working Protocol's semantic-owner and integration contract when durable truth changes.
- <project-specific approval, commit, or release rule>
