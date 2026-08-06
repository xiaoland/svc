# SVC CLI Shared Declared Runs

- **Objective**: Preserve the solidified minimum public contract for the narrow
  `svc run` shared-execution surface, define its exact implementation contract,
  and complete grounded preflight before requesting mutation approval. `svc dev`
  remains the established long-lived-capability domain. Cross-command
  Agent-friendly output is deliberately deferred to a separate unit after
  `svc run` rather than being bundled into this task.
- **Guardrails**:
  - Preserve simplicity first. Do not accumulate commands, schemas, boundaries,
    or infrastructure without a demonstrated role in the core interaction.
  - Do not reopen SVC CLI's product identity. It delivers and distributes the
    SVC Corpus; new runtime behavior must be a justified mechanical projection
    of accepted SVC semantics rather than an independent product direction.
  - Keep project discovery and code understanding with existing tools such as
    `rg`, `jq`, code graphs, and `ast-grep`; SVC CLI does not own project context
    acquisition or semantic task interpretation.
  - Keep permission, authorization, and confirmation between the Human and the
    Agent harness; SVC CLI does not own that control plane.
  - Preserve the distinct Agent, Human-terminal, Human-through-IDE, and CI
    invocation paths. IDE Tasks remains an optional Human-facing carrier; a CI
    workflow is an automation carrier. Neither defines the core development
    model or transfers ownership of the underlying tools to SVC CLI. Different
    carriers must not force Agent and Human to create duplicate declarations or
    duplicate execution instances merely to collaborate.
  - Reuse project-owned test, build, lint, smoke, and diagnostic tools rather
    than reimplementing them inside SVC.
  - Establish product need from the trajectories of real projects maintained by
    Agents. Similar execution tools may answer a narrow implementation question,
    but their feature sets and architectures are not consumer evidence for SVC.
  - Do not admit `svc run` as a generic command wrapper or task runner. Naming,
    discovery, JSON, dependency graphs, caching, affected selection, parallel
    execution, TUI, and CI reuse are already owned by mature project tools and
    are not sufficient SVC differentiation.
  - Treat local and CI use as two execution contexts for the same integrated
    development surface. Do not infer merge, release, remote-runner, or complete
    delivery ownership merely because CI can invoke it.
  - Keep the admitted `run` domain separate from `dev` in
    configuration and CLI interaction. Do not introduce a common public
    declaration, discovery catalog, command verb, or lifecycle model.
  - Define only the output required by the new `run` interaction. Do not use
    this task to redesign output from existing SVC commands. Native command
    streams, wrapper lifecycle facts, and machine-readable results remain
    distinct semantic channels; compact JSON is used only when requested.
  - This task has completed Explore/Solidify and is waiting for an explicit
    implementation start. Task-packet mutation and validation were authorized;
    no canonical SVC source, CLI implementation, template, release, or consumer
    mutation is authorized yet.
- **Verification**:
  - This packet alone preserves the accepted product directions, excluded
    responsibilities, foreground issue, and next concrete inquiry; linked
    task-local dossiers preserve the baseline, decisions, and supporting
    evidence.
  - The admitted outcome and implementation contract are tested against direct
    project-tool invocation on real large-project maintenance and Human-Agent
    handoff scenarios.
  - `run` verification distinguishes native stdout/stderr, wrapper-owned
    lifecycle presentation, the execution receipt, and caller-local outcomes
    such as an observer detaching.
  - The implementation plan identifies the exact canonical owners, public
    command changes, compatibility cost, coherent batches, and proportional
    tests before requesting mutation approval.
- **Current Truth**:
  - This is not a small single-file design task. It adds an independent `run`
    domain alongside the existing `dev` domain across local and CI execution,
    with effects on product semantics, command design, configuration, process
    lifecycle, editor and CI integration, compatibility, observability, and
    verification. `packet.md` is only the compact Human current view; the task
    packet is the complete task-local workspace.
  - SVC CLI's product identity is settled: it is the delivery/distribution
    runtime for the SVC Corpus. The working principle is to use as few deep
    capabilities as possible to reduce the cost for Agents to understand,
    operate, and take over large projects; this principle evaluates runtime
    projections rather than redefining the CLI.
  - Agent-friendly output remains an accepted direction, but Sir explicitly
    deferred its cross-command design to a separate unit after `svc run`. This
    packet specifies only the new command's required public projection. The
    narrow `svc run` shared-execution surface has passed product admission
    through the Beluna command-level handoff case.
  - Agent-friendly output means high-signal semantic presentation suited to LLM
    consumption; it is not synonymous with JSON. Compact JSON is materially
    preferable to prettified JSON when structured JSON is the right carrier.
  - IDE Tasks remains an optional Human interaction surface that may invoke SVC
    CLI. SVC CLI neither replaces IDE Tasks nor requires Agents to interact
    through it. The earlier decision excluding CI has been withdrawn: CI may
    invoke the same integrated development surface non-interactively.
  - SVC CLI cannot and should not own general project context, project semantics,
    existing specialist-tool behavior, Human-Agent permissions, or the complete
    software-delivery lifecycle.
  - The accepted terminology is
    `dev target` for a long-lived development capability and `declared run` for a
    named bounded acceptance operation; a configuration member may be called a
    `run entry`. The accepted public shape is separate top-level `dev` and
    `run` namespaces with `svc dev` and `svc run` interaction.
  - A generic run wrapper currently fails the differentiation test. npm scripts,
    Make/just, VS Code Tasks, Vite Task, Nx, Turborepo, and Bazel already cover
    overlapping execution, discovery, graph, cache, output, Agent, Human, and
    CI surfaces at different depths. “Agent-friendly JSON” is not a distinct
    claim either.
  - The admitted project acceptance interface has this boundary:
    project-owned tools remain execution authorities, while local Agent, Human,
    and IDE-carried callers converge on one explicitly identified bounded
    execution and its recoverable collaboration receipt. CI invokes the same
    declared acceptance surface in its own execution namespace; it does not
    share a live local process. This is the bounded analogue of `svc dev ensure`:
    multiple local CLI invocations are not automatically multiple
    underlying execution instances. A settled receipt is an observation
    horizon, never a reusable freshness claim, task-acceptance verdict, or
    quality verdict; selection and interpretation remain with the Agent and
    Human.
  - Public `dev` / `run` separation does not preclude private implementation
    reuse. The accepted private boundary gives a neutral execution engine only
    concrete process-attempt mechanics: launch, execution identity,
    policy-selected capture and observation, wait, follow, inspect, owned
    interruption, settlement, and explicit ownership release. `dev` remains the
    sole owner of HTTP/TCP/exec
    readiness, polling, capability scope, conflict, and reuse. This does not
    create a common public API, daemon, declaration, or lifecycle.
  - Internal coordination distinguishes a domain-supplied convergence key from
    the execution ID of one concrete process attempt. The former decides which
    callers may share work; the latter lets them wait, follow, inspect, and
    hand off that execution. The distinction is accepted; the implementation
    plan now gives both identities an internal representation without promoting
    either spelling into a general public protocol.
  - The accepted `run` convergence authority is a local active slot
    derived by the `run` domain from execution namespace, worktree identity,
    and resolved run-entry identity. It allows independent Human and Agent
    callers in one workspace to converge without exchanging an arbitrary token.
    It deliberately does not bridge hosts/CI checkouts or claim source/result
    freshness.
  - A second caller using an active slot follows the existing execution. This is
    a direct consequence of the accepted product definition, not a separate
    policy choice requiring another review.
  - The existing real-project audit supports a narrower need than earlier tool
    comparisons implied: long maintenance work uses multiple evidence horizons,
    later Human or independent review, interruption recovery, and sometimes an
    execution whose outcome is not captured. This supports recoverable shared
    execution evidence. It has not directly observed duplicate native runs
    caused only by different Human/Agent carriers.
  - Public grammar and the minimum implementation mechanics are now planned
    against the current code and real-project trajectory. Features outside that
    plan remain absent rather than forming a speculative backlog.
  - The first directly measured consumer case is the SVC repository itself.
    Its native `pdm run test` completes 131 tests in about 2.1 seconds and
    already emits useful pytest text. That entry does not independently justify
    shared-run complexity. The more valuable distribution acceptance is
    currently expanded inside CI rather than exposed as one project-owned
    bounded operation. This creates a concrete boundary question: require one
    project-owned driver command, or let a run entry own an ordered sequence.
    The real flow's dynamic value and artifact handoffs make a seemingly simple
    command list insufficient. The single-command boundary is accepted: project
    orchestration remains in a script, PDM composite, Make/just entry, or other
    project-owned driver.
  - The minimum bounded-run process lifecycle is accepted: the starter CLI
    remains foreground owner until settlement; a joined caller observes; owner
    `Ctrl+C` interrupts the execution while observer `Ctrl+C` only stops
    following. No background worker or daemon is justified by current evidence.
  - A read-only Beluna Core case supplies the first positive product-admission
    evidence. Its project-native Agent Task harness writes strong case-level
    receipts, but an active task's full `cargo test` failed during AIMock
    readiness before a new case receipt was produced. The Human handoff contains
    prose but no addressable command execution or output. A narrow SVC receipt
    would preserve the outer command failure while Cargo and Beluna continue to
    own test and case semantics.
  - Native command output and the SVC execution receipt are accepted as separate
    semantic outputs. The bounded receipt identifies the execution and its
    terminal facts; SVC-captured native output is addressable through the same
    execution ID rather than embedded in the receipt. SVC does not infer or
    track project artifacts from paths, URIs, or identifiers printed by the
    command.
  - The bounded-run product definition is now solidified. Exact public grammar,
    state storage, locking, capture, retention, and rendering are implementation
    judgments, not a queue of additional product decisions. Wrapper-owned
    command and terminal lines are allowed when clearly attributed and bounded;
    Agent-friendly output does not require hiding the command being executed.
  - A file-level implementation plan and failure-path preflight are complete in
    [`design/07-implementation-plan-and-preflight.md`](design/07-implementation-plan-and-preflight.md).
    The corrected minimum proposal uses a committed direct run-entry map with
    one exact argv, optional cwd, ordered env files, and inline env. A sparse
    local overlay may override the complete launch specification of an existing
    committed entry: argv/cwd/env-files replace while env keys merge. Env files
    resolve from the workspace root and load before inline env. Effective argv,
    resolved cwd, resolved env-file inputs, and declared env participate in
    convergence identity, but env values are never emitted in a receipt. This
    follows the shared-name/local-realization principle detailed in
    [`design/08-run-configuration.md`](design/08-run-configuration.md). Runtime
    coordination uses one neutral private execution engine with atomic attempt
    records, observable logs, policy-selected capture, and process ownership
    release. The public bounded run controller remains foreground-owned until
    process settlement. `dev` retains HTTP/TCP/exec readiness,
    polling, capability context, and reuse; after its probe succeeds, it asks the
    engine to release the provisioning process so it can continue in the
    background. This internal reuse, detailed in
    [`design/09-dev-execution-reuse.md`](design/09-dev-execution-reuse.md), adds
    no public pattern matcher, hook command, background field, cross-domain
    reference, or daemon. Implementation follows a library-first rule:
    python-dotenv owns env parsing, urllib3 owns dev readiness HTTP/TLS
    mechanics, and SVC code owns only its configuration, authority, lifecycle
    composition, and projections.
  - Preflight resolved unexpected owner loss without inventing takeover: the
    first caller that proves the lifetime lock is abandoned records and returns
    `owner-lost` without starting a replacement in that invocation. A later
    explicit invocation may deliberately start a new execution.
  - The exact run-only public projection and the distinct foreground-run,
    long-lived-dev, and bounded-dev-activation launch policies are frozen in
    [`design/10-run-public-projection-and-process.md`](design/10-run-public-projection-and-process.md).
    `run --follow` and `run --inspect` accept only run-domain execution IDs.
    Failure of an owner's terminal display sink does not become capture failure,
    and a foreground run remains in the terminal's foreground process group.
  - Sir accepted the corrected effective-run configuration, env-file and inline
    environment precedence, library-first ownership, neutral private dev/run
    process-mechanics boundary, and implementation-plan corrections on
    2026-08-06. No canonical or code mutation has been authorized or performed.
  - The consumer and carrier topology in [`design-map.md`](design-map.md) is
    accepted.
- **Next Step**: Await Sir's explicit start instruction. Then implement the
  accepted plan in coherent batches and validate its stated verification
  matrix. Return to discussion if implementation evidence invalidates the
  planned state/authority model or expands its blast radius.

## Supporting Material (Optional)

- Reference input: <https://chatgpt.com/share/6a702603-b2ac-83ea-9a67-80b94e95f0ac>
- Related SVC mechanism discussion: [`../core-mechanism-evolution/packet.md`](../core-mechanism-evolution/packet.md)
- Current runtime baseline: [`baseline.md`](baseline.md)
- Accepted decisions: [`decisions.md`](decisions.md)
- Discussion topology: [`design-map.md`](design-map.md)
- Design dossiers (01 is deferred; 02–10 own this unit):
  - [`design/01-agent-friendly-output.md`](design/01-agent-friendly-output.md)
  - [`design/02-integrated-development-infrastructure.md`](design/02-integrated-development-infrastructure.md)
  - [`design/03-run-product-admission.md`](design/03-run-product-admission.md)
  - [`design/04-shared-execution-coordination.md`](design/04-shared-execution-coordination.md)
  - [`design/05-consumer-case-svc.md`](design/05-consumer-case-svc.md)
  - [`design/06-consumer-case-beluna.md`](design/06-consumer-case-beluna.md)
  - [`design/07-implementation-plan-and-preflight.md`](design/07-implementation-plan-and-preflight.md)
  - [`design/08-run-configuration.md`](design/08-run-configuration.md)
  - [`design/09-dev-execution-reuse.md`](design/09-dev-execution-reuse.md)
  - [`design/10-run-public-projection-and-process.md`](design/10-run-public-projection-and-process.md)
