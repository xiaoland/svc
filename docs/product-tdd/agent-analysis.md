# Agent Evidence Query Contract

Use this [Product TDD](index.md) depth when telemetry acquisition, bundle
validation, query, read, provider adapters, and Agent callers must share one
evidence identity and wire contract. Product meaning and runtime capture remain
with Product Truth and Deployment.

This contract is admitted because telemetry acquisition, bundle validation,
query, read, provider adapters, and Agent callers must share one authority and
compatibility boundary. Product TDD owns the cross-unit wire and authority
rules; executable schemas, tests, and runtime code own field-level enforcement.
Product rationale remains in Product Truth, and `svc analysis --help` owns the
calling Agent's interpretation guidance.

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
- Query/read schema and response format v2 carry no packaged method reference.
  Each schema points to `svc analysis --help`; machine success is emitted on
  stdout and structured errors on stderr, while help text is not part of the
  machine response.

Verification is owned jointly by executable models/tests and the affected
runtime units: contract fixtures prove the three-member authority core,
single-digest identity, optional-cache rebuild, strict intent unions,
deterministic order, reference/cursor scope binding, native fidelity, structured
status/errors, and the distinction between empty-complete, partial,
unavailable, and pagination. The installed wheel must expose self-sufficient
analysis help and v2 query/read schemas.

If the [multi-repo extension](../../src/specs/multi-repo/index.md) is active,
shared Product TDD remains owned in the shared source rather than copied
independently into each repository.
