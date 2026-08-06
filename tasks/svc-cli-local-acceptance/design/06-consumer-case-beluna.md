# Consumer Case — Beluna Core Acceptance Handoff

## Purpose and Boundary

This case inspects an active, dirty Beluna worktree without running commands or
changing project state. It tests `svc run` against a real multi-component
project whose native test harness already produces strong domain artifacts.

## Project-Owned Operation

Beluna Core defines this full bounded verification command:

```text
cargo test --manifest-path core/Cargo.toml
```

The Core Agent Task harness runs deterministic replay cases inside that command.
Each completed case writes a project-owned run directory containing
`result.json`, `evidence.jsonl`, and world before/after/diff artifacts. The
directory path contains a case-specific run ID.

Primary evidence:

- `/Volumes/WorkSSD/Development/Beluna/core/tests/AGENTS.md`
- `/Volumes/WorkSSD/Development/Beluna/core/tests/agent-task/AGENTS.md`

These artifacts own case semantics. SVC must not parse them into its own pass or
acceptance verdict.

## Real Task Trajectory

The active `core-tick-grant-modes-20260618` task reports:

- focused Core library and non-Agent-Task integration tests passed;
- the full Core command reached Agent Task replay;
- AIMock exited before readiness with status 190;
- the failure appears outside the Tick grant mode change;
- the next action is Human review of the final diff and a stage/commit decision.

Historical Motor verification records the same boundary and later works around
it with an explicit npm cache plus a longer readiness window. Startup can take
more than ten seconds and is allowed thirty seconds, making blind repetition
materially more expensive than the SVC repository's two-second pytest case.

Primary evidence:

- `/Volumes/WorkSSD/Development/Beluna/tasks/core-tick-grant-modes-20260618/packet.md`
- `/Volumes/WorkSSD/Development/Beluna/tasks/issue-31-motor-mvp-20260527/VERIFICATION.md`

## Evidence Discontinuity

The project currently contains 94 case-level `result.json` receipts, including
failed case results. The latest receipts are dated 2026-06-17, before the active
Tick grant task's 2026-06-18 verification. The active packet references no
concrete run directory, result file, command execution ID, or native output.

This is consistent with the reported failure boundary: if AIMock exits during
readiness before a case settles, the case harness need not produce a new
case-level receipt. The full `cargo test` process still has meaningful execution
facts—start, output, child failure, exit status, and settlement—but they survive
only in the initiating Agent's tool context and prose handoff.

## Direct Baseline and Candidate Difference

Direct invocation:

```text
Agent -> cargo test -> cargo/test output + case artifacts when produced
                    -> prose summary in task packet
Human -> reads summary or reruns to recover command evidence
```

Candidate shared execution:

```text
Agent -> svc run <core-full> -> execution E -> cargo test
Human -> inspect/follow E

E owns: command lifecycle, native output reference, exit/signal/owner-loss facts
Beluna owns: case result, evidence stream, world diff, semantic attribution
task packet owns: relevance to Tick change, residual unknown, acceptance/handoff
```

SVC remains useful even when the nested harness creates no result. Conversely,
when case artifacts exist, SVC does not copy, discover, index, or reinterpret
them. The native output may mention their paths; the Agent and task packet bind
those domain artifacts to the verification claim when needed.

## Case Result

This case supplies the first positive product-admission evidence for `svc run`:

- **Agent maintenance**: a command-level failure remains addressable even when
  a nested large-project harness fails before producing its own receipt.
- **Human-Agent collaboration**: the Human reviewing the task can inspect the
  exact execution the Agent reports instead of trusting prose or rerunning it.
- **Native authority**: Cargo and Beluna retain test and case semantics.
- **Net simplicity**: the candidate needs one command execution ID, captured
  output, and terminal facts; it does not need an artifact protocol, test
  adapter, workflow graph, or result parser.

The evidence supports narrow admission of command-level shared execution and a
recoverable receipt. This case alone did not approve syntax, configuration,
storage, or rendering; the later accepted decisions and dossiers 07–10 resolve
the first implementation slice.
