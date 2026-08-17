# <Project Name>

<One sentence describing the product or repository.>

> Replace every angle-bracket placeholder. Delete any optional owner row that is not admitted; a completed root must contain no placeholder or `absent` marker.
> Put absolute paths or other machine-local information to `AGENTS.local.md` (under repository root).

## Repository Map

- `<path>`: <crucial responsibility>
- `<path>`: <crucial responsibility>
- `docs/`: durable project knowledge
- `tasks/`: task packets

## Knowledge Owners

- Product what and why: `docs/10-prd/*`
- Cross-unit technical contracts, when admitted: `docs/20-prd-tdd/*`
- Unit design and local seam guidance, when admitted: `docs/30-unit-tdd/*`
- Runtime, packaging, migration, observability, and recovery truth, when admitted: `docs/40-deployment/*`
- Nearer `AGENTS.md` files are additive for their subtree.
- `tasks/` are task packets, they are volatile.

## Development Workflow

- Runtime and package manager: <versions/tools>
- Common commands: `your install/test/lint/check/build/smoke commands`
- Runtime data: `<state, database, logs, cache, and config paths>` (refer to AGENTS.local.md if it's absolute path)
- Environment overrides: `<locations>`
