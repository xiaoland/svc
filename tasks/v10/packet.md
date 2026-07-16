# v10 Executable Change Protocol

- **Objective**: Evolve SVC from a documented methodology into an executable, migratable, and measurable change protocol for sustainable long-cycle software development under Vibe Coding. The first delivery slice establishes a versioned, on-demand upstream corpus and reliable project-local adoption without copying framework documents into consumer repositories.
- **Guardrails**:
  - Keep SVC small, source-first, and mechanically verifiable; every new surface needs an owner, trigger, consumer, and verification path.
  - Preserve explicit authority across the canonical SVC corpus, Consumer-owned project material, and bounded Generated integration artifacts; never infer authority from a path alone.
  - No downstream SVC-managed framework document exists. The CLI serves immutable release content; consumer knowledge documents remain Consumer-owned.
  - Require a non-mutating exact plan only for high-risk writes to non-SVC-owned project content or installer state. Keep read-only commands and direct, explicitly requested runtime convergence free of digest ceremony. Every planned repository write remains idempotent, preconditioned, postconditioned, rollback-safe, and fixture-tested.
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
  - The embedded-runtime foundation in [`20-embedded-runtime-cli/packet.md`](20-embedded-runtime-cli/packet.md) is implemented and released as SVC 10.0.0: pure canonical `src/`, root-level `svc_cli/` runtime and `tools/` tooling, deterministic catalog/corpus lookup, minimal `svc.json`, Codex-only operational skill, non-destructive anchors with default `docs/index.md`, separate self-update and adoption, and no automatic consumer-file migration engine.
  - Its release planner now distinguishes a predeclared MAJOR's migration declaration from a pending MAJOR's staging policy, so an old non-applicability rationale cannot silently carry into a later release.
  - Semantic lookup and task helpers remain deliberately deferred until each has a separate protocol and Impact Handshake. Dev-server assurance is implemented in [`30-ensure-dev-server/packet.md`](30-ensure-dev-server/packet.md). The Codex thread-export contract is implemented in [`40-export-agent-thread/packet.md`](40-export-agent-thread/packet.md), with fresh-wheel fixture acceptance on macOS, Windows, and Linux; it works from direct local rollout data without requiring Codex CLI.
  - SVC 10.0.0 is published on PyPI and GitHub Releases. The Release PR workflow uses a built-in, short-lived `GITHUB_TOKEN` with job-scoped Contents and Pull requests write permissions; the repository Actions setting must allow token-created PRs, and a maintainer explicitly approves their CI runs. Protected publication and recovery remain documented in `CONTRIBUTING.md`.
  - All remaining changes in this v10 task are assigned to 10.0.1 under a one-time version exception authorized by the product owner. Their real Behavioral SemVer impact remains declared; release metadata must say `zero known adopted consumers`, because a published public package cannot mechanically prove that no unknown consumer exists.
  - Sub-agents are available again for bounded parallel research and review; the primary agent retains packet and implementation authority.
- **Next Step**: Complete the user-authorized 10.0.1 release hardening, verify the Release PR topology and cross-platform archive behavior, then publish through the reviewed Release PR and protected environment.

## Supporting Material

- First sub-task: [`10-versioned-consumption/packet.md`](10-versioned-consumption/packet.md)
- Third sub-task: [`30-ensure-dev-server/packet.md`](30-ensure-dev-server/packet.md)
- Fourth sub-task: [`40-export-agent-thread/packet.md`](40-export-agent-thread/packet.md)
