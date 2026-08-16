# Deployment

Deployment is an optional owner for non-trivial runtime and operational truth: packaging, environment configuration, migrations, rollout, telemetry, mitigation, rollback, recovery, and runtime data locations.

Create it only when operators or developers need stable information that code, configuration, automation, or platform definitions do not expose clearly enough.

Reality work may use logs, metrics, traces, and runbooks as evidence, but the diagnosed cause selects the final owner. Keep code-local recurrence tripwires in the nearest local `AGENTS.md` and product promises in product truth.

## Local Execution Runtime

Shared execution evidence lives under the platform user runtime directory in
an `svc/execution` tree. Each UUIDv4 execution has one strict atomically
replaced schema-v2 JSON record and policy-selected byte logs; domain
coordination pointers and locks are derived from semantic coordination keys. Paths,
records, and domain identifiers are validated before access. Files request
user-only permissions where supported, but this is the established same-user
trust boundary, not protection from a hostile process under the same account.

The runtime is local operational evidence, not archival storage. It may be
removed by reboot or platform cleanup, and the first slice adds neither an
automatic retention policy nor a reset command. Settled records are not
automatically deleted. Missing, malformed, mismatched, or partially published
authority fails closed so SVC cannot start a duplicate or fabricate a receipt.
Writes use same-directory temporary files and atomic replacement.

The initiating run CLI retains the lifetime lock and child handle. If it is
lost uncatchably, an orphan child may remain; the next caller may record
`owner-lost` only after acquiring the abandoned lock and must not replace the
execution in that invocation. Dev ensure may deliberately persist `released` after
readiness and then relinquish its handle. After release, later dev authority
comes from capability probes rather than the historical PID, and complete
process-lifetime log capture is not promised.

On POSIX, isolated dev attempts use null stdin, merged log redirection, and a
new session so a ready released capability is not tied to the starter terminal.
Windows uses `DETACHED_PROCESS`, `CREATE_NEW_PROCESS_GROUP`, and
`CREATE_BREAKAWAY_FROM_JOB`: console detachment and job breakaway are separate
requirements, and process-group creation alone does not preserve a child when
an OpenSSH session job closes. A parent job that forbids breakaway makes launch
fail instead of silently weakening persistence. While SVC still owns an
unsettled isolated attempt, interruption targets only that exact process group
or tree; Windows uses `taskkill /T /F` because a detached process cannot receive
the starter console's control event. Once released, only Consumer-declared stop
plus readiness verification may clean it up.

## Double Runtime

Each successful `svc double start` owns one UUIDv4 run beneath the platform
user runtime directory's `svc/double/runs` tree. The module's resolved location
selects and records its workspace identity; later commands locate the strict
self-describing run record by ID rather than interpreting the caller's current
directory. The run contains the normalized IR and workspace-contained
asset/contract snapshots, replay and digest facts, a bounded merged carrier log,
private control coordinates/capability, and carrier-written observation data.
Directories and files request user-only permissions under the established
same-user local trust boundary.

The carrier binds responder and control listeners to numeric loopback
addresses. Startup retains the exact isolated child handle until an
authenticated readiness receipt proves the expected run and snapshot; only
then may the mechanical launch attempt be released. Before readiness, failure
or interruption may terminate only that still-owned attempt. After release,
the execution record and historical PID are never double lifecycle or cleanup
authority.

Carrier memory alone owns active bindings, match counts, and journal state.
Startup and command-triggered files remain explicitly `sealed: false`
projections. Graceful stop closes response intake, settles owned work, writes
one same-directory atomically replaced `sealed: true` final snapshot, returns
the stop receipt, and exits. That sealed snapshot owns later observe and
idempotent stop. Journal projections always report total, retained, and omitted
counts. Missing, malformed, mismatched, or unreachable active control returns a
bounded `control-unavailable` result with the last labeled projection; the
client writes no terminal fact and performs no PID or process-tree action.

Default event targets are numeric loopback origins. A remote origin is admitted
only when both the scenario declares `explicit-remote` and start names the
target in an explicit remote allowlist; delivery follows no redirect and makes
one attempt. The responder, built-in generators, managed assets, and built-in
event injector have no undeclared egress path. The unsandboxed external
materializer and the independently launched Consumer retain explicit
`egress: not-enforced` operational non-claims, so safe CI also removes real
write credentials and supplies network isolation where required.

Double run data is volatile local evidence, not archival storage. Every start
is fresh, no latest-run or reuse lookup exists, and no automatic provider event,
timer, retry, stale-run takeover, or cleanup policy is inferred. Missing
volatile data fails closed rather than reconstructing authority from a module,
workspace, log, or process table.

## Agent Evidence Runtime

The telemetry runtime owns exact provider-source selection, bounded read-only capture, successful bundle validation, migration, and recovery. A schema-v3 authority core contains minimal `manifest.json`, captured `native.bin`, and validated `native-index.jsonl` framing. One evidence digest binds native and framing bytes. Optional `trajectory.jsonl` is rebuildable projection cache; its counts, capabilities, and loss summary are not authority. Export opens the selected source read-only, creates only an absent output, never overwrites, and keeps source and output distinct. An interrupted process may leave an invalid partial target; consumers validate before use, and the caller removes that target before retry.

The runtime relies on the operating system, SQLite read-only transactions, and
ZIP validation as its local authorities. It does not inspect every path
component or promise atomic visibility, symlink/reparse exclusion, hostile
same-user defense, or time-of-check protection. The native member may contain
all selected provider content; projection is derived structural navigation,
not redaction or confidentiality.

Schema-v1 raw archives and schema-v2 normalized bundles are historical cutoffs, not query/read authorities. Query/read require recollection into schema v3 from an available provider-local source; SVC does not convert an old archive, treat a lossy trajectory as native content, or claim recollection when the source is gone. Migration guidance belongs in the release migration note, while this owner records the runtime consequence and recovery path.

Source growth, read interruption, source/frame bounds, and an incomplete final frame are capture facts. Unsupported or malformed records affect only the derived projection. A retained incomplete frame remains readable but cannot silently produce a projection record. Missing or invalid cache is rebuilt from the native core; a failed rebuild makes structural query unavailable without blocking native read. Response pagination is ordinary continuation and remains distinct from capture state. Recovery is explicit recollection from the original source after core validation fails; no network, model, or provider-source mutation is used as a shortcut.
Concurrent source change is therefore an ordinary consistency condition: use a
validated successful export, and retry explicit collection when acquisition
reports loss or fails.

Operational verification covers malformed and changing sources, minimal-core validation and cache rebuild, absent-target/no-overwrite behavior, migration and recollection smoke checks, recovery status, and installed-wheel access to the packaged method and evidence contract. Deployment does not own task intent, semantic findings, or query field schemas.

Use [the deployment runbook template](../assets/templates/deployment-runbook.template.md) when an operational response needs a repeatable evidence, mitigation, and recovery path.
