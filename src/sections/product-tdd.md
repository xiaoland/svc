# Product TDD

Product TDD is an optional owner for technical contracts that multiple units must share to interoperate safely while product truth remains separate.

Admit it only when:

- another unit depends on the contract
- changing it can break compatibility, authority, or topology
- code, schemas, and tests alone do not make the contract cheap to recover
- real cross-unit content exists now

It may own unit topology, system state and authority, cross-unit interfaces, compatibility rules, and realization pointers from product claims. It does not own product why or one unit's private implementation.

A Constraint lens does not select Product TDD automatically. Environment, dependency, repository-policy, deployment, source, configuration, or test owners may be correct instead.

Start with one document. Split only when topology, authority, contracts, or realization have distinct consumers or cadence. Use [the Product TDD template](../assets/templates/product-tdd.template.md).

## Shared Execution Contract

`run` and `dev` are separate public/configuration domains that share only a
private mechanical execution boundary. Domain controllers derive convergence
identity and retain semantic authority: `run` owns one named bounded command
intent in a worktree; `dev` owns capability scope, probes, readiness,
provisioning, stop, and later reuse. The shared mechanism owns one concrete
execution ID, atomic lifecycle facts, process ownership, policy-selected
capture, observation, settlement, and explicit release. Its neutral persisted
identity is `domain`, `operation`, `subject`, `workspace_instance`,
`intent_digest`, and `coordination_key`; domain projections restore names such
as run entry/effective-entry digest or dev target/effective-target digest.

One coordination lock is the ownership authority. The winning caller holds it
from publication through domain settlement; contenders join only the same
operation and intent. A different intent at the same coordination boundary
waits, re-evaluates, then executes rather than running in parallel. The
execution record is authoritative for its neutral identity, resolved argv/cwd,
non-secret env-file paths, log addresses, owner PID, timestamps, and mechanical
state. Native output remains project-owned bytes addressed through exact log
references rather than being interpreted as SVC results.

Run lifecycle is `starting -> running -> exited | interrupted | start-failed |
capture-failed | owner-lost`. Dev may additionally request `released` only
after its own readiness proof. An abandoned lifetime lock plus an active record
proves owner loss; the first later caller records that fact without starting a
replacement in the same invocation. PID observation alone never grants
takeover or kill authority.

Dev capability identity is `scope`, `target`, resolved `endpoint_id`, selected
`scope_id`, and `capability_id`. The capability ID binds namespace, scope,
scope ID, and target and is the shared ensure/stop coordination key; endpoint
and action declarations belong to the operation intent digest. Thus ensure and
stop serialize over the same capability while only equivalent ensure or stop
intents converge. Stop executes only a target-local Consumer declaration and
uses its final readiness probe as a postcondition; released process IDs are
never fallback cleanup authority.

Foreground run inherits stdin and the terminal process group, captures stdout
and stderr separately, and stays owned until child exit plus both stream EOFs.
An owner interrupt affects the execution; a follower interrupt only detaches
that caller. Dev provisioners remain isolated with null stdin and merged logs.
No shared public lifecycle API, daemon, process-tree guarantee, output-order
invention, readiness state, or project-artifact model follows from this reuse.
Schema-v1 execution records are an unreleased local cutoff: a still-held legacy
lifetime lock blocks v2 publication, settled files remain untouched, and
explicit inspection fails with `execution-record-schema-unsupported` rather
than field aliases or PID action.

## Agent Evidence Query Contract

This contract is admitted because telemetry acquisition, bundle validation, query, read, provider adapters, and Agent callers must share one authority and compatibility boundary. Product TDD owns the cross-unit wire and authority rules; executable schemas, tests, and runtime code own field-level enforcement. Product rationale and the Agent's semantic method remain in Product Truth and the Working Protocol.

### Authority and topology

An explicitly selected provider source is captured read-only into an immutable schema-v3 evidence bundle. Minimal manifest facts, native captured content, and validated framing are authoritative for source order and recovery. One evidence digest binds the stored native and framing bytes. A trajectory is an optional rebuildable cache; its counts, capabilities, loss summary, and structural records are derived projection, not identity or native authority. The calling Agent owns semantic findings and task-quality judgments.

Acquisition remains under telemetry. Query and read accept one immutable schema-v3 bundle and never read a live thread, guess a latest thread, or substitute a normalized projection for unavailable native evidence. Query is set-oriented with one closed typed intent (`overview` or `match`) and deterministic descriptors/references. Read is sequence-oriented: it returns captured native content in source order from the beginning, an exact reference, or an opaque continuation; it does not filter, reorder, summarize, score, or interpret records.

The acquisition boundary trusts the calling user, selected local provider
location, local account, and operating system. Inventory reports provider
lifecycle and recognition metadata but does not claim live source
availability; export resolves the exact source when it runs. The native member
may contain all selected content, so projection allowlists and omissions are
structural/resource rules rather than privacy enforcement. SVC does not expose
a confidentiality, redaction, sandbox, hostile same-user, or adversarial path-
race contract.

### Wire invariants

- Query predicates are closed and typed. The contract does not grow an SQL, JSONPath, GraphQL, regex-program, join, aggregation, scoring, or natural-language DSL.
- `complete`, `partial`, and `unavailable` describe source/frame facts and answerability from the current derived view. Pagination is separate: an empty `complete` result is a trustworthy negative for that exact request, while `unavailable` is not a negative finding.
- Opaque cursors carry contract version, evidence digest, typed request scope, ordering, and the next record or fragment position. They are unsigned local continuation state, not authenticated capabilities. Continuation may change only the page budget; selector, snapshot, intent, or anchor changes fail with a scope error.
- A response may carry source metadata, stable evidence references, position, coverage, and continuation without rewriting the native payload. Oversized native records remain exactly reassemblable; response pagination does not turn complete evidence into partial evidence.
- Successful export leaves one strictly validated absent-target bundle without overwriting an existing path. Interrupted publication may leave an invalid partial target; every consumer validates before use, and the caller removes that target before retry.
- Every schema and query/read response carries the exact packaged Agent Task Analysis method reference (identifier, canonical path, section, and document digest). Machine success is emitted on stdout and structured errors on stderr; human text is not part of this contract.

Verification is owned jointly by executable models/tests and the affected runtime units: contract fixtures prove the three-member authority core, single-digest identity, optional-cache rebuild, strict intent unions, deterministic order, reference/cursor scope binding, native fidelity, structured status/errors, and the distinction between empty-complete, partial, unavailable, and pagination. The installed wheel must resolve the method reference through `svc lookup`.

If the [multi-repo extension](extensions/multi-repo.md) is active, shared Product TDD remains owned in the shared source rather than copied independently into each repository.
