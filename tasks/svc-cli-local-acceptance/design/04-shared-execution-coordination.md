# Evidence Dossier — Shared Execution Coordination

## Status

Neutral private reuse across `run` and `dev` is accepted for concrete
process-attempt mechanics. It creates no public shared domain, daemon, or
persistence protocol. Dossiers 07, 09, and 10 define the implementation
boundary; this dossier preserves the evidence that led to it.

## Accepted Identity Distinction

Internal coordination distinguishes these two facts:

1. **Convergence key**: the domain-supplied identity deciding whether two
   callers express the same explicit intent and may share work.
2. **Execution ID**: the identity of one concrete process attempt that callers
   can wait for, follow, inspect, and reference during handoff.

The semantic split was accepted by Sir on 2026-08-05. `execution ID` is now the
public run observation handle and may remain internal to dev provisioning; the
convergence-key spelling and representation stay private to the owning domain.

## Current SVC Evidence

`svc dev ensure` already has a declaration-specific capability identity and a
file lock derived from workspace namespace, scope subject, profile, target, and
endpoint identity. Concurrent callers contend on that lock; the winner
provisions, while a later caller re-probes and returns `reused` when the endpoint
has become healthy.

The implementation does not create a persistent execution ID. The waiting
caller cannot observe the winner's phase or log; it only blocks on the lock and
then probes again. The starter alone receives the timestamped log path and PID,
and SVC deliberately relinquishes process authority after readiness. `dev
status` independently probes the capability and has no knowledge of an active
or completed provisioning attempt.

Primary local evidence:

- `svc_cli/dev/identity.py:114-148` — capability, lock, and runtime keys
- `svc_cli/dev/runtime.py:222-294` — probe, lock, second probe, provision
- `svc_cli/dev/runtime.py:348-469` — process, log, and readiness attempt
- `svc_cli/dev/runtime.py:532-557` — disown and one-shot result
- `tests/test_dev_runtime.py:161-216` — two callers start once, then reuse

The test proves single provisioning for concurrent in-process callers. It does
not yet prove separate CLI-process contention, persistent observation, log
following, crash recovery, or handoff.

## Consumer-Project Evidence

The existing Agent-thread audit contains eight privacy-preserving real-project
cases. They do not prove every proposed `run` behavior, but they establish the
consumer problems against which the hypothesis must be tested:

- `OPS-B` uses focused checks, broader scenarios, external probes, and later
  independent review. A later review finds material risks after earlier green
  gates, and the case explicitly leaves uncertain whether a different person or
  future task could recover without the same operator context.
- `REC-E` crosses long implementation and recovery episodes. Interaction-level
  checks expose regressions after structural checks, and an interrupted turn is
  retained as interruption rather than completion before later Human review.
- `SVC-A` ends one episode after an execution request whose outcome is absent
  from the captured stream. The correct terminal fact is `unknown`, despite the
  presence of a completed tool-call record.
- `WIN-F` uses package, story, browser, and direct visual evidence as distinct
  horizons; an unstable browser harness causes the evidence method to change
  rather than being mistaken for a product failure.

Primary task-local sources:

- `tasks/v10/70-agent-thread-audit/case-cards/ops-b.md`
- `tasks/v10/70-agent-thread-audit/case-cards/rec-e.md`
- `tasks/v10/70-agent-thread-audit/case-cards/svc-a.md`
- `tasks/v10/70-agent-thread-audit/case-cards/win-f.md`
- `tasks/v10/70-agent-thread-audit/cross-case-synthesis.md`

These cases support an addressable execution result whose output, settlement,
and evidence horizon survive a participant's conversational context. They do
not directly observe Human and Agent launching the same native operation twice
because they entered through different carriers, nor do they show that a
bounded execution must outlive its initiating CLI. Those remain hypotheses to
test, not findings.

## Implementation Precedents, Not Consumer Evidence

### PostHog: hogli and phrocs

PostHog's hogli command layer remains primarily a dispatcher; shared runtime
state is supplied by phrocs. In detached mode, phrocs owns the process stack,
publishes a workspace-derived IPC socket, and exposes readiness, process status,
exit facts, and logs to other clients. `hogli wait` polls that shared state, and
the phrocs MCP server exposes the same process status and logs to coding Agents.

PostHog's entrypoint rejects a second start rather than joining the first start
invocation. A later caller can wait on or inspect the already-running stack, but
there is no per-run execution identity. The socket identifies the workspace
process manager, not one bounded execution.

Primary sources:

- [PostHog local development](https://github.com/PostHog/posthog/blob/master/docs/published/handbook/engineering/developing-locally.md)
- [phrocs detached ownership](https://github.com/PostHog/posthog/blob/master/tools/phrocs/detached.go)
- [phrocs workspace IPC and state protocol](https://github.com/PostHog/posthog/blob/master/tools/phrocs/internal/ipc/server.go)
- [phrocs wait/attach polling](https://github.com/PostHog/posthog/blob/master/tools/phrocs/subcommands.go)
- [phrocs Agent observation](https://github.com/PostHog/posthog/blob/master/tools/phrocs/mcp_server.py)

This proves that a Human-facing launcher, headless caller, and Agent can observe
one long-lived development state through different clients. It does not prove
bounded-run convergence or that SVC needs a daemon, IPC server, TUI, or MCP.

### Docker Compose

Compose separates project/service identity from container identity. Repeated
`up` calls reconcile the same project resources; detached resources remain
owned by the Docker daemon. Other CLI processes can query `ps`, follow `logs`,
consume `events`, or wait using the same daemon and project namespace.

Primary sources:

- [Compose project and commands](https://docs.docker.com/reference/cli/docker/compose/)
- [Compose up and reconciliation](https://docs.docker.com/reference/cli/docker/compose/up/)
- [Compose logs](https://docs.docker.com/reference/cli/docker/compose/logs/)
- [Docker Engine ownership](https://docs.docker.com/engine/)

This supports separating a convergence namespace from concrete runtime
instances. It is runtime-daemon evidence, not a reason for SVC to absorb
container orchestration.

### Bazel

Bazel separates its shared server domain (`output_base`) from an invocation UUID.
One server serializes concurrent commands by waiting for its lock or rejecting
the caller; it does not join the existing build. A Build Event Protocol stream
can expose one invocation to IDE or dashboard consumers, while cache identity
and artifact reuse remain separate mechanisms.

Primary sources:

- [Bazel client/server model](https://bazel.build/run/client-server)
- [Bazel command options](https://bazel.build/reference/command-line-reference)
- [Bazel Build Event Protocol](https://bazel.build/remote/bep)

This is a useful counterexample: serialization and an invocation ID do not by
themselves create Human-Agent collaboration. A second caller still needs an
observation path to the existing execution.

## Evidence-Led Inference

The smallest shape consistent with the accepted product definition is:

```text
domain declaration
-> convergence key
-> zero or one active execution ID
-> one process owner
-> multiple observers of progress, output, and settlement
```

The consumer cases justify recoverable execution observation; the active-slot
and execution-ID split projects the already accepted no-duplicate-work product
definition onto that need. PostHog, Compose, Bazel, Temporal, and GitHub Actions
are only precedents for particular identity or process mechanics. They do not
admit SVC functionality by resemblance.

## Convergence-Key Authority Review

### Evidence from mature execution systems

Temporal separates a caller-defined, business-meaningful Workflow ID from a
system-generated Run ID. At most one execution with the Workflow ID may be open;
an open-ID conflict may fail, use the existing execution, or terminate it and
start another. Closed-history reuse is a separate policy. This is close to the
accepted SVC distinction, but Temporal's workflow engine, retries, retention,
and conflict-policy catalog are not SVC requirements.

- [Temporal Workflow ID and Run ID](https://docs.temporal.io/workflow-execution/workflowid-runid)

GitHub Actions requires the workflow author to define a concurrency group as a
literal or expression. GitHub still creates a distinct run ID for every
trigger; the group controls pending/running concurrency by queueing or
cancellation and does not join callers to one run. This demonstrates that a
platform cannot safely infer the grouping boundary from the command alone.

- [GitHub Actions concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)
- [GitHub workflow runs](https://docs.github.com/en/rest/actions/workflow-runs)

Both cases keep the semantic grouping identity with the application/workflow
domain and the concrete execution identity with the execution platform.

### Accepted Direction — Run-domain-derived active slot

The `run` domain can mechanically derive a local active-slot key from:

```text
local execution namespace
+ worktree identity
+ resolved run-entry identity
```

The resolved entry identity must change when the declaration that determines
the native invocation changes. If caller-supplied operation arguments are ever
allowed, they must either participate in this identity or disable convergence;
arbitrary arguments cannot be ignored safely.

This candidate has the lowest collaboration cost. A Human and Agent can
independently invoke the same declared run in the same executable workspace and
arrive at the same active slot without first exchanging a token. It also uses
the same kind of mechanically resolved namespace/worktree facts already proven
by `svc dev`.

Its scope is intentionally local. A separate host or CI checkout invokes the
same public run entry but does not share the same live execution. The key also
does not contain or claim source, dependency, environment, or result freshness.
It only coordinates an active execution. Once that execution settles, a later
invocation creates a new execution ID.

### Candidate B — Caller-provided opaque key

An explicit opaque key makes intent authority unambiguous and can bridge an
external collaboration system. It also forces Human and Agent to agree on and
transport a token before SVC can prevent duplicate work. Reuse, collision,
expiry, project binding, and accidental cross-task sharing all become new caller
responsibilities.

This may later be a useful integration override. It is a poor default because
it moves the collaboration problem that SVC is intended to remove back to its
callers.

### Rejected default authorities

- A task-packet path is not a key authority. The canonical packet is
  consumer-owned, disposable, movable, and has no stable ID field; CI and small
  tasks may not have one.
- A native process, job, or run ID is created after execution begins. It can be
  stored as or mapped to the execution ID, but cannot decide whether two
  independently arriving callers meant the same work.
- A run-entry name by itself is too broad. It omits execution namespace,
  workspace isolation, and declaration changes.

## Accepted Authority Decision

Candidate A is the default local convergence authority: `run` derives one
active slot from the local execution namespace, worktree, and resolved run
entry. Shared execution infrastructure receives that opaque domain key and
does not infer it. Candidate B remains an unapproved future integration option,
not part of the minimum product.

This is a semantic decision only; it does not select a public representation or
implementation mechanism.

## Derived Active-Slot Behavior

When a second caller resolves an already-active slot, it uses the existing
execution:

```text
caller A -> inactive slot -> create execution E -> follow E -> receipt E
caller B -> active slot E  -> join/follow E       -> receipt E
```

The second caller does not queue another execution, cancel the current one, or
start in parallel. Both callers observe the same underlying output and settled
result. Their own response may still state whether they started or joined the
execution so the interaction remains attributable.

This is not an additional conflict-policy choice. It follows from D-008: if a
second caller queued, cancelled, or started another execution merely because it
arrived through another carrier, the product would no longer converge Human and
Agent on one execution state.

The behavior is active-only and makes no freshness claim. If a caller
needs verification after further mutations, it waits for E to settle and then
starts a new execution.

## Minimum Foreground Ownership and Interrupt Semantics

The real-project cases do not show a need for a bounded acceptance execution to
outlive the CLI that started it. PDM 2.27.0 and pnpm 11.20.0 supply a simpler
implementation precedent for ordinary runs:

- PDM installs `SIGINT`/`SIGTERM` handlers, starts the child, forwards those
  signals, and waits for the child exit before returning.
- pnpm's lifecycle runner starts the script shell, forwards interrupt/terminate
  signals, kills the child when the runner exits, and waits for settlement.

Neither ordinary run creates an independent owner and exits early. The minimum
SVC model can preserve that familiar foreground lifecycle:

```text
starter CLI (process owner) -> native child -> wait until settlement
follower CLI (observer)      -> shared state/output of the same execution
```

The starter does not normally exit while the run is active. `Ctrl+C` is the
terminal's interrupt character: it sends `SIGINT` to the foreground process
group. On the owner interaction, it interrupts the shared execution; on a
follower interaction, it only stops that caller from following because the
follower has no child-process authority. `Ctrl+Z`, not `Ctrl+C`, is the normal
terminal suspend character; shell `bg` and `fg` resume a suspended job in the
background or foreground.

Unexpected owner loss invalidates the active execution. Later inspection must
report owner loss rather than pretending that an unowned native process is a
valid shared run; safe cleanup is an implementation obligation. An independent
worker or daemon earns consideration only if a real consumer trajectory requires
the execution to survive its initiating CLI.

## Boundary of Possible Internal Reuse

Potentially common mechanics:

- create and address one execution attempt
- elect exactly one process owner
- let other callers wait, follow bounded output, and inspect state
- settle an attempt and preserve a bounded evidence reference
- clean up only the attempt whose process authority SVC owns

Domain-owned semantics that must remain outside the common mechanism:

- `dev`: capability scope, readiness, endpoint provenance, reuse, and
  occupied-unhealthy no-takeover behavior
- `run`: operation declaration, deliberate repeat, terminal result vocabulary,
  and the boundary between command result and task acceptance
- project tools: dependency graphs, caching, affected selection, retries,
  artifacts, and native result semantics
- Agent/Human: selection, interpretation, freshness judgment, and acceptance
