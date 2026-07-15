# v10 Executable Change Protocol

- **Objective**: Evolve SVC from a documented methodology into an executable, migratable, and measurable change protocol for sustainable long-cycle software development under Vibe Coding. The first delivery slice establishes a versioned, on-demand upstream corpus and reliable project-local adoption without copying framework documents into consumer repositories.
- **Guardrails**:
  - Keep SVC small, source-first, and mechanically verifiable; every new surface needs an owner, trigger, consumer, and verification path.
  - Preserve explicit authority across the canonical SVC corpus, Consumer-owned project material, and bounded Generated integration artifacts; never infer authority from a path alone.
  - No downstream SVC-managed framework document exists. The CLI serves immutable release content; consumer knowledge documents remain Consumer-owned.
  - Default every project-local write to a non-mutating exact plan. Never silently overwrite consumer content or a modified generated block or skill. Local repository plans are idempotent, preconditioned, postconditioned, rollback-safe, and fixture-tested.
  - `svc self-update` is an explicit installer operation, separate from adoption. It must not change `svc.json`; it does not promise to reverse a package-manager transaction.
  - Treat task state as disposable. Move verified durable truth to its canonical owner during implementation and delete this packet when v10 closes.
  - Do not mutate a new implementation or release-automation slice until its high-level protocol and Impact Handshake are confirmed by the user.
- **Verification**:
  - A clean wheel contains a generated catalog plus one read-only corpus projection; an sdist contains canonical source and the builder needed to reproduce that wheel payload.
  - CLI fixtures prove dry-run byte stability, exact-plan application, repeated-apply no-op behavior, conflict refusal, Consumer-owned preservation, generated-anchor/skill drift detection, pre/postcondition failure, and full rollback after injected local write failure.
  - Contract tests prove catalog integrity, deterministic machine output, lookup-query/result boundary stability, and allowed Behavioral SemVer declarations.
  - A clean consumer can initialize, inspect, query the installed corpus, explicitly adopt the installed baseline, and verify the resulting project state without framework-document copying.
  - `pdm run test` and `pdm run build-monolith` pass for every implementation slice.
- **Current Truth**:
  - v9 has no observable installation state. Its consumer path is four result files plus manual copy/customization instructions, and its migrations are prose in `CHANGELOG.md`.
  - Commit `986ef6a` implemented an unreleased, copy-and-migrate v10 contract with SVC-managed documents, `.svc/state.json`, and a migration graph. It is mechanically sound but superseded by the embedded-runtime product boundary.
  - v10 therefore requires a deliberate replacement of that consumption contract, not a revival or extension of the old copy-based installer.
  - The first sub-task has its own now-superseded design record at [`10-versioned-consumption/packet.md`](10-versioned-consumption/packet.md); its release topology and Towncrier work remain useful, but its consumer-copy engine does not describe the current product.
  - The embedded-runtime foundation in [`20-embedded-runtime-cli/packet.md`](20-embedded-runtime-cli/packet.md) is implemented: pure canonical `src/`, root-level `svc_cli/` runtime and `tools/` tooling, deterministic catalog/corpus lookup, minimal `svc.json`, Codex-only operational skill, non-destructive anchors with default `docs/index.md`, separate self-update and adoption, and no automatic consumer-file migration engine.
  - Its release planner now distinguishes a predeclared MAJOR's migration declaration from a pending MAJOR's staging policy, so an old non-applicability rationale cannot silently carry into a later release.
  - Semantic lookup, thread export, task helpers, and dev-server assurance remain deliberately deferred until each has a separate protocol and Impact Handshake.
  - The repository still has no Git tags, and no package or release has been published. GitHub App, protected environment, Trusted Publisher, branch protection, and immutable-release configuration remain external prerequisites.
  - This task must not use sub-agents.
- **Next Step**: Review the completed embedded-runtime foundation. Publishing, tagging, branching, external release configuration, and the next busybox command remain separately unauthorized.

## Supporting Material

- First sub-task: [`10-versioned-consumption/packet.md`](10-versioned-consumption/packet.md)
