# v10 Executable Change Protocol

- **Objective**: Evolve SVC from a documented methodology into an executable, migratable, and measurable change protocol for sustainable long-cycle software development under Vibe Coding. The first delivery slice establishes reliable, versioned upstream-to-consumer adoption and upgrade.
- **Guardrails**:
  - Keep SVC small, source-first, and mechanically verifiable; every new surface needs an owner, trigger, consumer, and verification path.
  - Preserve explicit authority across SVC-managed, Consumer-owned, and Generated files; never infer authority from a path alone.
  - Default every adoption or migration to a non-mutating plan. Never silently overwrite consumer content or locally drifted managed content.
  - Migrations must be sequential, idempotent, preconditioned, postconditioned, rollback-safe, and fixture-tested.
  - Treat task state as disposable. Move verified durable truth to its canonical owner during implementation and delete this packet when v10 closes.
  - Do not mutate a new implementation or release-automation slice until its high-level protocol and Impact Handshake are confirmed by the user.
- **Verification**:
  - A versioned release artifact and machine-readable inventory make installed version, file authority, provenance, and drift mechanically observable.
  - CLI fixtures prove dry-run byte stability, exact-plan application, adjacent sequential migration, repeated-apply no-op behavior, conflict refusal, Consumer-owned preservation, Generated reconstruction, pre/postcondition failure, and full rollback after injected failure.
  - Contract tests prove manifest inventory integrity, migration-graph continuity, deterministic machine output, and allowed behavioral SemVer declarations.
  - A clean consumer can initialize, inspect, migrate from every supported source version, and verify the resulting state without manual file copying.
  - `pdm run test` and `pdm run build-monolith` pass for every implementation slice.
- **Current Truth**:
  - v9 has no observable installation state. Its consumer path is four result files plus manual copy/customization instructions, and its migrations are prose in `CHANGELOG.md`.
  - The two protocol documents behave as upstream-managed copies, while root `AGENTS.md`, product truth, task packets, and instantiated templates become Consumer-owned. The current consumer kernel defines no Generated file.
  - The repository exposes only a monolith builder, is marked non-distributable, reports package version `0.1.0` while framework history is `9.x`, has no release manifest, migration registry, fixtures, or Git tags, and contains tests that intentionally forbid the removed installer surface. The current baseline is 19 passing tests.
  - v10 therefore requires a deliberate replacement of the consumption contract, not a revival of the old copy-based installer.
  - The first sub-task has its own control surface at [`10-versioned-consumption/packet.md`](10-versioned-consumption/packet.md).
  - Its local consumption and migration slice is implemented across the release manifest, installable package, CLI, migration engine, durable consumer contract, and fixtures.
  - The approved distribution slice is implemented locally: the Python package is `svc_cli`; GitHub Releases are the canonical release record; PyPI is the installation projection; Towncrier and a repository planner own release state; and CI, Release PR, protected publication, exact-asset retry checks, and attestations are encoded as workflows.
  - The repository still has no Git tags, and no package or release has been published. GitHub App, protected environment, Trusted Publisher, branch protection, and immutable-release configuration remain external prerequisites.
  - v9.8 migration intentionally blocks until Consumer-owned layout and provenance-free legacy files are resolved manually; it then recognizes the released implementation-taste digest and applies the managed transition transactionally.
  - This task must not use sub-agents.
- **Next Step**: Review the first sub-task evidence, then decide whether to authorize external GitHub/PyPI setup and the first release or proceed to the next v10 sub-task. Publishing, tagging, branching, and external release remain separately unauthorized.

## Supporting Material

- First sub-task: [`10-versioned-consumption/packet.md`](10-versioned-consumption/packet.md)
