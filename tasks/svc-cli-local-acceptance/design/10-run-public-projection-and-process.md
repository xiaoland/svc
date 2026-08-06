# Implementation Contract — Run Projection and Process Policies

## Status

This is the implementation contract derived from the accepted product and
configuration decisions. It does not authorize canonical or code mutation.
Cross-command Agent-friendly output remains a later unit; this document defines
only what the new `svc run` interaction needs to be coherent and testable.

## Public Grammar and Domain Boundary

```text
svc run <entry> [--repo <repo>] [--json]
svc run --follow <execution-id> [--repo <repo>] [--json]
svc run --inspect <execution-id> [--repo <repo>] [--json]
```

The three forms are mutually exclusive. Entry execution resolves an existing
committed run entry and either owns a new process attempt or follows the attempt
already occupying its active slot. Explicit follow replays captured output and
continues following until settlement. Inspect returns the current facts without
replaying native output or waiting for settlement.

Every stored execution includes an internal domain discriminator. Public
`run --follow` and `run --inspect` reject a dev-domain execution ID as a
selection/domain error; dev observations remain mediated by the dev controller.
The private engine therefore does not accidentally create a shared public
execution namespace.

Follow and inspect validate the execution against the workspace resolved from
`--repo`, but use the published record as authority; they do not require the
entry to remain in today's configuration or re-resolve changed env files. Entry
execution alone resolves current configuration and chooses a convergence slot.

There is no list, dependency, arbitrary argv, force-new, background, cancel,
timeout, readiness, hook, or pattern-matcher surface in the first slice.

## Text Projection

Text mode keeps wrapper-owned facts on stderr and forwards native bytes to the
corresponding stdout or stderr stream:

```text
stderr: svc run core-full: owner <execution-id>
stderr: cwd: /resolved/workspace
stderr: $ cargo test --manifest-path core/Cargo.toml
native: project stdout and stderr on their original channels
stderr: svc run core-full: exited 1 in 12.4s <execution-id>
```

A follower header identifies `follower`; an inspector prints one bounded status
summary and no native output. The command display uses the resolved argv and
cwd, never environment values. Shell quoting is presentation only because the
actual launch remains an argv array with no shell interpretation. It uses
`shlex.join` on POSIX and `subprocess.list2cmdline` on Windows rather than an
SVC-specific quoting grammar.

## Compact JSON Projection

`--json` suppresses live wrapper text and native display. Execute and follow
wait for settlement and emit exactly one compact JSON result on stdout. Inspect
emits exactly one compact current result on stdout. Captured native output stays
addressable by execution ID and is not embedded in JSON.

The common result fields are:

```text
schema_version, command, caller_role, execution_id, entry, workspace_id,
effective_entry_digest, state, argv, cwd, env_files, started_at
```

`command` is one of `run`, `run follow`, or `run inspect`; `caller_role` is
`owner`, `follower`, or `inspector`, and `schema_version` is 1. A settled result
also contains `finished_at` and `duration_ms`. An `exited` result contains
`exit_code`.
Interrupted results contain `requested_signal` when the owner observed an
interrupt request and `termination_signal` when the platform can prove the
child's terminating signal. These fields use symbolic names such as `SIGINT`,
not platform-dependent integers. Environment values are never emitted.
Optional or state-inapplicable members are omitted rather than filled with
`null`.

Execution IDs use the standard library's canonical lowercase UUIDv4 spelling
and are parsed back to that exact form before they can address a runtime path.
`workspace_id` is the existing opaque workspace `instance`, not a raw repository
path. Timestamps are UTC RFC 3339 values with `Z`; duration is measured by a
monotonic clock and projected as a non-negative integer number of milliseconds.

Configuration, entry-selection, execution-ID, and domain mismatches occur
before an execution can be selected and emit one compact error object on
stderr. Once an execution is published, start failure, capture failure, and
owner loss are execution outcomes: execute/follow JSON emits their result on
stdout and does not also emit a second JSON error value.

The unavoidable exception is failure of the authority store itself while
writing the terminal record. SVC cannot fabricate a receipt it failed to
persist; that caller emits one compact storage error on stderr and later callers
fail closed on the incomplete record.

If a JSON follower receives `Ctrl+C`, it emits one caller-local result on
stdout with `caller_status: "detached"` and the last observed
`execution_state`, then returns 130. Detachment is not written as execution
state. If an entry caller detaches during the short lock-won/publication gap,
before a new execution ID is knowable, the same caller result identifies the
entry and omits `execution_id` and `execution_state`. Text mode reports either
detachment on stderr.

## Exit Projection

| Outcome | CLI exit code |
|---|---:|
| child exited | child exit code |
| owner/follower interrupted by signal *N* | `128 + N` on POSIX; Ctrl+C is 130 on Windows |
| start failure, authoritative capture failure, owner loss | 4 |
| inspect succeeded, regardless of observed execution state | 0 |
| CLI usage error | 2 |
| configuration, selection, state/domain mismatch | 3 |

An observer's `Ctrl+C` maps to 130 but does not interrupt or mutate the shared
execution. The owner returns only after the child and capture streams settle.

## Concrete Launch Policies

The neutral engine accepts explicit policy; it does not derive behavior from
the public domain name.

| Consumer | Process isolation and stdin | Capture | Settlement/release |
|---|---|---|---|
| foreground `run` | same terminal session and foreground process group; inherit stdin | separate stdout/stderr pipes, separate byte logs, live fan-out | wait for terminal state; never release |
| dev `mode=run` provisioner | new session/process group; stdin is null | merged stdout/stderr redirected to one dev log | dev may release only after its readiness probe succeeds |
| dev `mode=activate` command | isolated like dev provisioner; stdin is null | merged output in one dev log | command must exit successfully before dev readiness evaluation; never release |
| dev `kind=manual` | no engine launch | existing manual interaction | not applicable |

This preserves the existing dev `log_path` and `process_id` fields, their
meaning, result behavior, and merged-log compatibility; the runtime filename is
not a stable public contract and may become the execution directory's
`output.log`. Adding an execution ID is additive internal evidence. The
migration does not add `env_files` or another run-only field to the public dev
schema merely to make implementation reuse look uniform.

## Terminal and Signal Semantics

On POSIX, an interactive terminal sends `SIGINT` and `SIGTSTP` to the entire
foreground process group. A foreground run therefore must not use
`start_new_session=True` or create a new process group. Its owner records
`SIGINT` intent and continues draining and waiting. When launch-time terminal
facts prove that the owner group is the terminal foreground group, the terminal
has already delivered the signal to the child and SVC does not send a duplicate.
Without that terminal-group proof, a targeted `SIGINT` is best-effort forwarded
to the direct child. SVC does not intercept `SIGTSTP`, so ordinary shell stop,
`bg`, and `fg` behavior applies to the owner and child together.

For a targeted owner `SIGTERM`, the owner makes a best-effort forward to the
direct child and settles normally. Uncatchable owner loss cannot guarantee
child-tree termination. The first later caller that proves owner death while
holding the domain lock records `owner-lost` and returns without starting a
replacement. Because it never owned the lost child, its public caller role is
`follower` for entry/follow interaction; an explicit inspect remains
`inspector`. Reconciliation authority remains internal. A subsequent explicit
call may start again. SVC does not promise to discover or kill daemonized
descendants and does not implement a miniature shell job-control layer.

Entry, follow, and inspect callers all perform this lazy reconciliation when
they can prove an active record's lifetime lock is abandoned. Inspect remains
non-executing but may atomically record this already-true lifecycle fact; it
still returns 0 because inspection succeeded. An entry invocation that performs
reconciliation returns the lost receipt and never treats the same invocation as
permission to start a replacement.

On Windows, foreground run remains in the caller's console group and does not
request a new process group. POSIX `Ctrl+Z` job control has no Windows
equivalent. Dev continues using its platform-specific isolated-process and
owned-tree cleanup behavior.

## Capture, Display, and Ownership Failures

Foreground run pipes are drained concurrently. Each native byte is appended to
its authoritative stream log before best-effort live display. If an owner's
stdout or stderr display sink closes, only that display sink is disabled;
capture, process ownership, and the other sink continue. A `BrokenPipeError`
from terminal/pipeline presentation is therefore not `capture-failed`.

Settlement waits for the direct child and EOF on both capture pipes. A project
command that exits while leaving descendants holding those descriptors has not
provided a closed bounded-output horizon, so SVC does not invent a hidden drain
timeout or claim a complete receipt. Such descendants remain subject only to
ordinary foreground-group signals and the documented no-process-tree guarantee.

`capture-failed` is reserved for failure to write the authoritative foreground
log after publication. The owner then stops its directly owned command and
records the outcome if state storage remains writable. For dev redirection,
failure to create/open the merged log occurs before attempt publication and
spawn; after a successful release, SVC does not promise complete ongoing log
capture because it no longer owns the process.

The lifetime lock descriptor is non-inheritable and subprocess launch closes
unneeded descriptors. Domain controllers derive and guard convergence slots;
the engine owns only the validated attempt transition requested under that
authority.

## Required Verification

- Use separate CLI processes to prove one active native run and one execution
  ID across owner and follower.
- Use a POSIX PTY to prove owner `Ctrl+C`, follower `Ctrl+C`, and ordinary
  `Ctrl+Z`/`fg` behavior without an isolated foreground child.
- Kill the owner PID uncatchably while its child remains alive; prove the first
  recovery reports `owner-lost` without replacement and a later explicit call
  may start anew.
- Close owner and follower display pipes; prove authoritative logs still drain
  and the child cannot be backpressured by a dead display consumer.
- Prove text channel separation, compact one-value JSON framing, active inspect,
  caller-local detach, terminal exit mapping, and run/dev execution-ID domain
  rejection.
- Preserve non-UTF-8 native bytes in stored logs without embedding them in the
  receipt.
- Cover dev `run`/`activate` modes and manual provision, existing `log_path` and
  `process_id`, readiness-gated release, startup failure, interruption cleanup,
  and later capability reuse/status.
