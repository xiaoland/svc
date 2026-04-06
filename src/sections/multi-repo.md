# Optional Multi-Repo Extension

Multi-repo is a pressure-driven topology extension, not the default SVC posture.

Load this extension only when one product spans multiple repositories and shared truth would otherwise be copied, drift, or force agents to leave the local worktree constantly.

## Admission Rule

Adopt the multi-repo extension only when all are true:

1. one product or system spans multiple repos
2. shared PRD, shared meta rules, or shared cross-unit contracts would otherwise be duplicated
3. the team is willing to accept explicit shared-ref freshness and mutation discipline

If these conditions are not present, stay mono-repo.

## Topology

Use a Hub-and-Spoke shape:

- Hub repo: shared slow truth authored once in `00-meta/`, `10-prd/`, `15-alignment/`, `20-product-tdd/`, and global `tasks/`
- Spoke repo: local code, local `30-unit-tdd/`, local `40-deployment/`, local `tasks/`, and local `src/**/AGENTS.md`
- shared mount: `docs/_shared/` inside each Spoke for nearby read access to Hub truth

Example:

```text
Hub repo
|-- 00-meta/
|-- 10-prd/
|-- 15-alignment/
|-- 20-product-tdd/
`-- tasks/
```

```text
Spoke repo
|-- docs/
|   |-- _shared/
|   |-- 30-unit-tdd/
|   `-- 40-deployment/
|-- tasks/
`-- src/
```

## Read Rule

In a Spoke repo:

- read shared truth from `docs/_shared/`
- treat `docs/_shared/` as read-only during ordinary local execution
- keep local structure and operations outside the shared mount

## Shared-Doc Mutation Rule

When Spoke execution discovers a missing shared rule:

1. capture local pressure in the active Spoke task:
   - local code path or seam
   - missing shared rule or ambiguity
   - local consequence if unresolved
   - verification pressure after return
2. decide whether the truth is truly shared or still local
3. update shared truth source-first
4. update the Spoke shared ref second
5. resume the captured local task

Never mix Hub doc edits, Spoke shared-ref bumps, and Spoke-local code changes in one commit.

When available, use the repo skill `edit-svc-shared-docs` to reduce submodule editing risk and protect Spoke agents from unsafe shared-doc edits.

## Shared vs Local Boundary

Use the same authority rule as the core framework:

- if another unit must rely on it to interoperate safely, it belongs in Product TDD
- if one unit can change it without forcing another unit to update, it stays in Unit TDD or local `AGENTS.md`

Minimal examples:

- payload format between two services -> Product TDD
- one service's internal DB table naming -> Unit TDD

## Freshness Contract

Use `git submodule` as the default reference transport.

Equivalent mechanisms are acceptable only if they preserve:

1. one authoritative upstream source
2. nearby read access from the active Spoke worktree
3. default read-only local consumption
4. machine-verifiable freshness

Freshness should be maintained by automation or an equivalent deterministic workflow, not by human memory.

## Task Routing

- Hub `tasks/`: shared exploration, global diagnosis, and cross-unit contract work
- Spoke `tasks/`: local implementation, local diagnosis, and local-pressure capture before shared promotion

## Related Assets

- [Shared Docs Edit Protocol Template](../assets/templates/edit-shared-docs.template.md)
- [Product TDD](product-tdd.md)
- [Unit TDD and Local Context](unit-tdd.md)
- [Tasks](tasks.md)
