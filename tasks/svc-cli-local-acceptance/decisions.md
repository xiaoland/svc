# SVC CLI Development Surface Decisions

This register records decisions accepted in the Human-Agent discussion. Later
entries do freeze a minimum public and implementation contract, but the
register does not authorize canonical or code mutation.

## D-000 — SVC CLI Product Identity Is Established

- **State**: accepted
- **Authority and date**: Sir, 2026-08-04
- **Decision**: SVC CLI is the delivery and distribution runtime for the SVC
  Corpus. This task does not need to keep redefining what the CLI is.
- **Consequence**: Agent-friendly output and integrated development
  infrastructure must be evaluated as mechanical projections of accepted SVC
  Corpus semantics, not as independent attempts to reposition the CLI.
- **Design principle**: Prefer as few deep capabilities as possible that reduce
  Agent cost when understanding, operating, and taking over large projects.

## D-001 — Output Semantics Before Format

- **State**: accepted direction; deferred to a separate unit by D-018
- **Authority and date**: Sir, 2026-08-04
- **Decision**: Optimize each function's stdout and stderr for Agent use by
  selecting a representation from the output's semantics and LLM preferences.
  JSON is not intrinsically Agent-friendly. When JSON fits, compact JSON is
  materially preferable to prettified JSON.
- **Consequence**: The design must classify result shapes and interaction needs
  before choosing one global format or envelope.

## D-002 — Local Acceptance Infrastructure

- **State**: accepted; refined by D-006, D-007, and D-014
- **Authority and date**: Sir, 2026-08-04
- **Decision**: Explore SVC CLI as local acceptance infrastructure with a role
  analogous to a test framework and usable from IDE Tasks.
- **Consequence**: SVC may provide a common local acceptance surface over
  project-owned tools. Later decisions narrowed this to one project-owned
  bounded command with shared execution evidence and resolved its minimum
  semantics and public shape.

## D-003 — Human, Agent, and IDE Tasks Are Not Peer Consumers

- **State**: accepted
- **Authority and date**: Sir, 2026-08-04
- **Decision**: SVC CLI directly serves Agents and Humans. IDE Tasks is one
  optional Human-facing carrier that can invoke SVC CLI. “Usable from IDE
  Tasks” must not be confused with “SVC CLI replaces IDE Tasks” for either
  Human or Agent.
- **Consequence**: Interaction design must keep the direct Agent path, direct
  Human terminal path, and optional Human-through-IDE path distinct.
- **Topology status**: accepted as recorded in `design-map.md`.

## D-004 — CI Is Outside the Product Boundary

- **State**: withdrawn; superseded by D-006
- **Original authority and date**: Sir, 2026-08-04
- **Withdrawal authority and date**: Sir, 2026-08-05
- **Decision**: SVC CLI does not expose the acceptance infrastructure to CI and
  does not claim production-level CI, merge, release, or remote-runner quality.
- **Reason withdrawn**: A shared development CLI can usefully provide the same
  integrated environment and check surface in local, Agent, and CI execution.
  Production-grade CI ownership is not a prerequisite for being invoked by CI.

## D-005 — Existing Specialist Tools Remain Owners

- **State**: accepted
- **Authority and date**: Sir, 2026-08-04
- **Decision**: SVC CLI does not own general project context acquisition or
  duplicate specialist tools such as `rg`, `jq`, code graphs, `ast-grep`, test
  frameworks, and project-native build or diagnostic tools.
- **Consequence**: Any new development capability must compose existing tools
  through a smaller SVC-specific interaction rather than absorb their domains.

## D-006 — Integrated Development Surface Includes CI

- **State**: accepted; refined by D-007 and D-014
- **Authority and date**: Sir, 2026-08-05
- **Decision**: Evolve the existing SVC CLI `dev` family toward a unified
  development tool through integration rather than reimplementation. The same
  surface may be invoked by Agents, Humans, optional IDE Tasks, and CI
  workflows. Local acceptance is one capability within this larger surface.
- **Consequence**: D-006 supersedes D-004 and expands D-002. CI is an execution
  and automation carrier, not evidence that SVC CLI owns the CI platform,
  merge policy, release process, or the semantics of integrated project tools.
- **Reference lesson**: hogli and Vite+ demonstrate the leverage of one
  consistent entry point across development environments and checks. Their
  exact command catalogs, implementation choices, and telemetry mechanisms are
  evidence, not requirements to copy.

## D-007 — Dev and Run Are Separate Public Domains

- **State**: accepted; activated by D-014
- **Authority and date**: Sir, 2026-08-05
- **Decision**: Keep the admitted bounded acceptance capability separate from
  long-lived development capabilities in both
  configuration and CLI interaction. Preserve `svc dev` for existing dev
  targets and use `svc run` with separate top-level `dev` and `run`
  configuration namespaces.
- **Terminology**: A `dev target` is a long-lived development capability. A
  `declared run` is a bounded project operation, and its configuration member
  may be called a `run entry`. “Long-lived” is preferred over “long-run”;
  `run target` is avoided because target already names the dev lifecycle, and
  unqualified “task” is avoided because SVC task packets already name
  Human-Agent work.
- **Consequence**: D-007 supersedes the part of D-006 that described the
  existing `dev` family as the parent of the unified tool, and rejects the prior
  proposal to place capabilities and bounded operations under one declaration
  parent or shared public integration model. Any low-level code reuse remains
  an implementation judgment backed by concrete duplication. This topology
  decision did not itself justify or admit a new `run` feature; D-014 later
  supplied that admission.

## D-008 — Human and Agent Converge on One Execution State

- **State**: accepted product behavior
- **Authority and date**: Sir, 2026-08-05
- **Decision**: Agent and Human must not create separate declarations or
  execution instances merely because one enters through a CLI and another
  through an IDE or another carrier. The established value of `svc dev ensure`
  is convergence: concurrent callers coordinate on one capability identity,
  one caller provisions it, and the others wait for or reuse the same ready
  capability.
- **Consequence**: A CLI invocation is not necessarily a new underlying
  execution. The admitted `svc run` surface includes an explicit bounded
  execution identity that another caller can
  follow, inspect, or receive in a handoff without rerunning the native tool
  solely to obtain the same evidence. Therefore a caller that reaches an
  already-active execution follows that execution; queueing, cancelling it, or
  starting a duplicate would contradict this product definition and is not a
  separate policy decision.
- **Boundary**: This does not allow SVC to treat an old terminal result as fresh,
  infer input equivalence, or replace native build/test caching. A repeated
  execution remains valid when deliberately requested or when equivalence
  cannot be established safely.

## D-009 — Private Execution Coordination May Serve Both Domains

- **State**: accepted; refined by D-017 and D-019
- **Authority and date**: Sir, 2026-08-05
- **Decision**: Although `dev` and `run` remain separate public domains, the
  internal capability needed by a bounded run may become shared infrastructure.
  In particular, `dev` may benefit from the same mechanics that let multiple
  callers wait for, follow, and inspect one concrete execution.
- **Consequence**: Evaluate a private execution-coordination boundary with both
  `run` and existing `dev` as concrete consumers. Do not place the mechanism
  publicly under either domain merely because one implementation lands first.
- **Boundary**: Reuse applies only to process-attempt identity, ownership,
  observation, output, and settlement mechanics that are genuinely common.
  `dev` retains capability identity, readiness, reuse, scope, and no-takeover
  semantics; `run` retains bounded terminal-result semantics. No module, API,
  daemon, public persistence protocol, or generic public state machine follows
  from the reuse boundary.

## D-010 — Convergence Identity and Execution Identity Are Distinct

- **State**: accepted implementation contract
- **Authority and date**: Sir, 2026-08-05
- **Decision**: Internal execution coordination must distinguish the identity
  that decides whether independently arriving callers may converge from the ID
  of one concrete execution they can wait for, follow, inspect, and reference.
  `execution ID` is the public run observation handle and may remain internal
  for dev provisioning. `convergence key` remains a private implementation term
  and representation.
- **Consequence**: A workspace, dev capability, run-entry name, lock, process,
  or execution ID cannot silently stand in for both facts. The owning `dev` or
  `run` domain supplies the convergence semantics; shared infrastructure owns
  only the concrete execution record and its observation lifecycle.
- **Evidence**: Current `svc dev` has a capability-derived lock but no
  addressable provisioning attempt. PostHog/phrocs, Docker Compose, and Bazel
  likewise distinguish a shared runtime scope from concrete process,
  container, or invocation identity; serialization alone does not let another
  caller observe an existing execution.

## D-011 — Run Owns a Local Derived Active Slot

- **State**: accepted; representation resolved by D-016 and dossiers 07–10
- **Authority and date**: Sir, 2026-08-05
- **Decision**: The default `run` convergence authority is a local active slot
  mechanically derived by the `run` domain from the execution namespace,
  worktree identity, and resolved run-entry identity. Shared execution
  infrastructure receives the resulting opaque key and does not infer it.
- **Consequence**: Human and Agent callers in the same executable workspace can
  discover the same active execution without first exchanging a caller-created
  token. A different host or CI checkout uses the same public run entry but does
  not share the local live execution.
- **Boundary**: The key coordinates active work only. It does not prove source,
  dependency, environment, or result freshness and never reuses a settled
  result. A task-packet path and a native process/run ID are not convergence-key
  authorities. Exact hashing is private. The first slice uses the resolved
  committed entry and admits neither arbitrary caller arguments nor a
  caller-provided integration key.

## D-012 — Bounded Runs Use Foreground Process Ownership

- **State**: accepted; implementation resolved by D-020 and dossier 10
- **Authority and date**: Sir, 2026-08-06
- **Decision**: The CLI that starts a bounded run remains its foreground process
  owner and waits for settlement. It does not exit normally while leaving the
  native operation with a new background owner. A caller joining an already
  active execution is an observer, not another process owner.
- **Interrupt semantics**: `Ctrl+C` on the owner interrupts the shared
  execution. `Ctrl+C` on an observer stops that caller from following without
  interrupting the execution. `Ctrl+Z` and shell `bg`/`fg` retain their normal
  job-control meaning rather than becoming SVC lifecycle commands.
- **Boundary**: Unexpected owner loss invalidates the active execution and must
  remain observable as owner loss. No independent worker or daemon is justified
  unless a real consumer trajectory requires a bounded execution to outlive its
  initiating CLI.

## D-013 — A Run Entry Starts One Project-Owned Command

- **State**: accepted; representation resolved by D-016
- **Authority and date**: Sir, 2026-08-06
- **Decision**: One run entry starts one project-owned command. SVC may identify,
  coordinate, observe, and retain a receipt for that bounded execution, but the
  run declaration does not own an ordered step list or data flow between steps.
- **Rationale**: The SVC repository's real distribution acceptance passes wheel
  paths, digests, temporary paths, environments, and generated values between
  steps. A superficially simple command list cannot express it; adding variables,
  conditions, artifacts, and step-output references would create a workflow
  language.
- **Consequence**: A project uses a script, PDM composite, Make/just entry, or
  another project-owned driver when acceptance requires orchestration. Human,
  Agent, optional IDE Task, and CI may then invoke the same run entry without
  transferring the driver's semantics to SVC.
- **Boundary**: This does not constrain the internal behavior of the project
  command or prevent it from invoking specialist tools. The accepted
  representation is exact argv without a shell plus optional cwd, env files,
  and inline environment.

## D-014 — Admit Narrow Shared Bounded Runs

- **State**: accepted; minimum design resolved by D-016–D-020 and dossiers 07–10
- **Authority and date**: Sir, 2026-08-06
- **Decision**: Admit `svc run` as a narrow shared-execution surface for one
  project-owned bounded command. Independently arriving local Human and Agent
  callers may converge on one execution ID, follow its native output, and
  inspect its terminal execution facts without rerunning solely for handoff.
- **Evidence**: In the active Beluna Tick grant task, full Core verification
  failed during AIMock readiness before the project-native Agent Task harness
  produced a new case receipt. The Human handoff retained an Agent prose summary
  but no addressable outer command execution or output. An SVC command-level
  receipt would preserve that failure without interpreting Beluna artifacts.
- **Consequence**: The earlier conditional `dev` / `run` split is now active
  product topology. `svc run` still does not own test semantics, project
  artifacts, acceptance judgment, workflow graphs, caching, or context
  discovery.
- **Boundary**: Admission alone approved the outcome rather than a schema or
  implementation. Later decisions resolved the minimum grammar, projection,
  process contract, and local runtime; no daemon, artifact protocol, or general
  task runner was admitted.

## D-015 — Native Command Output and Execution Receipt Are Separate

- **State**: accepted; run-only rendering resolved by dossier 10
- **Authority and date**: Sir, 2026-08-06
- **Decision**: One bounded execution has two distinct semantic outputs. Native
  command output is the project tool's diagnostic and result stream, whose
  meaning remains project-owned. The execution receipt is a bounded SVC record
  containing the execution ID, resolved run entry, terminal lifecycle facts,
  and duration. Captured native output is bound to the execution ID so it can be
  followed or recovered; the semantic model does not require a second output
  locator.
- **Artifact boundary**: The receipt has no generic `artifact references` field.
  A path, URI, or identifier printed by a command remains opaque native output;
  SVC does not infer that it denotes an artifact, verify it, track its lifetime,
  or assign it project semantics. Addressing captured output through the
  execution ID is SVC-owned and is not a reference to project artifacts.
- **Consequence**: The receipt does not embed or summarize unbounded native
  output, and native output does not have to carry SVC lifecycle facts. Dossier
  10 fixes the first-slice stdout/stderr, capture, and text/JSON projection;
  runtime evidence remains explicitly non-durable and has no automatic
  retention promise.

## D-016 — Run Resolves One Effective Launch Specification

- **State**: accepted implementation and configuration boundary
- **Authority and date**: Sir, 2026-08-06
- **Decision**: A committed run entry supplies one stable project name and a
  complete default launch specification. `svc.local.json` may sparsely override
  `argv`, `cwd`, `env_files`, and `env` for that existing entry, producing the
  one effective specification that is validated, identified, displayed, and
  executed. It cannot create a local-only run entry. Arrays and scalars replace;
  environment maps merge.
- **Environment resolution**: Relative cwd and env-file paths resolve from the
  workspace root. Every declared env file is required. Child environment
  precedence is owner ambient, then env files in listed order, then inline
  `env`, so inline values always win. Raw environment values are not emitted in
  receipts or command display.
- **Consequence**: Effective argv, resolved cwd, ordered resolved env-file
  inputs, and declared environment participate in local convergence identity.
  Dotenv syntax is delegated to a maintained parser with interpolation disabled;
  SVC owns only path, precedence, validation, privacy, and identity composition.

## D-017 — Dev Readiness and Shared Process Mechanics Stay Separate

- **State**: accepted implementation boundary
- **Authority and date**: Sir, 2026-08-06
- **Decision**: `svc dev` continues to own HTTP, TCP, and exec readiness,
  polling, capability scope, conflict, and reuse. A neutral private execution
  engine may own the lower process-attempt mechanics shared by `dev` and `run`:
  launch, execution identity, capture, attributed stream fan-out, follow, wait,
  inspect, owned interruption, settlement, and explicit ownership release.
- **Lifecycle boundary**: `released` records only the mechanical relinquishment
  of process ownership after the dev controller has proved readiness. It is not
  a generic ready state, and public bounded runs never request it.
- **Consequence**: The first slice adds no public readiness, background,
  pattern, or hook schema and no generic hook API. A future proven consumer may
  use attributed stream observations without transferring readiness or success
  semantics into the private execution engine. Established protocols and
  formats should be delegated to mature libraries; SVC-specific code remains
  responsible for domain authority and composition.

## D-018 — Cross-Command Agent-Friendly Output Is a Later Unit

- **State**: accepted sequencing decision
- **Authority and date**: Sir, 2026-08-06
- **Decision**: Complete `svc run` first. Treat optimization of output across
  existing SVC CLI functions as a separate unit afterward.
- **Consequence**: This task defines the minimum public output projection needed
  by the new run interaction but does not redesign existing command output or
  establish a cross-command envelope.

## D-019 — Shared Execution Mechanics Have Neutral Private Ownership

- **State**: accepted implementation boundary
- **Authority and date**: Sir, 2026-08-06
- **Decision**: The shared process-attempt mechanics are not owned by the public
  `run` domain. They live in a neutral private implementation boundary consumed
  by the distinct `run` and `dev` controllers.
- **Consequence**: The implementation must not place the reusable engine under
  `svc_cli/run/`, expose it as a public command/configuration namespace, or let
  it infer either domain's convergence, readiness, reuse, or result semantics.

## D-020 — Run and Dev Use Distinct Concrete Launch Policies

- **State**: accepted implementation contract
- **Authority and date**: Sir, 2026-08-06
- **Decision**: Reuse process-attempt mechanics without forcing one process
  launch policy. A foreground bounded run remains in the terminal foreground
  process group and inherits stdin. A long-lived dev process is isolated from
  the caller's terminal and may be released only after dev-owned readiness. A
  bounded dev activation command uses isolated logged execution but must settle
  before readiness evaluation continues.
- **Consequence**: Launch, input, capture, interrupt, and release are explicit
  policy inputs to the private engine. Public run never releases ownership;
  manual dev targets do not use the engine.
