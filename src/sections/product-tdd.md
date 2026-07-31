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

## Agent Evidence Query Contract

This contract is admitted because telemetry acquisition, bundle validation, query, read, provider adapters, and Agent callers must share one authority and compatibility boundary. Product TDD owns the cross-unit wire and authority rules; executable schemas, tests, and runtime code own field-level enforcement. Product rationale and the Agent's semantic method remain in Product Truth and the Working Protocol.

### Authority and topology

An explicitly selected provider source is captured read-only into an immutable schema-v3 evidence bundle. Native captured content and its validated framing/index are authoritative for original content and source order. A manifest binds identity, provenance, digests, capabilities, and declared loss. Any trajectory or structural index is a manifest-bound derived projection; query/read responses are projections with stable references, not new evidence authorities. The calling Agent owns semantic findings and task-quality judgments.

Acquisition remains under telemetry. Query and read accept one immutable schema-v3 bundle and never read a live thread, guess a latest thread, or substitute a normalized projection for unavailable native evidence. Query is set-oriented with one closed typed intent (`overview` or `match`) and deterministic descriptors/references. Read is sequence-oriented: it returns captured native content in source order from the beginning, an exact reference, or an opaque continuation; it does not filter, reorder, summarize, score, or interpret records.

### Wire invariants

- Query predicates are closed and typed. The contract does not grow an SQL, JSONPath, GraphQL, regex-program, join, aggregation, scoring, or natural-language DSL.
- `complete`, `partial`, and `unavailable` describe answerability and capture/projection coverage. Pagination is separate: an empty `complete` result is a trustworthy negative for that exact request, while `unavailable` is not a negative finding.
- Opaque cursors bind contract version, evidence digest, canonical request, ordering, and the next record or fragment position. Continuation may change only the page budget; selector, snapshot, intent, or anchor changes fail with a scope error.
- A response may carry provenance, stable evidence references, position, coverage, and continuation metadata without rewriting the native payload. Oversized native records remain exactly reassemblable; response pagination does not turn complete evidence into partial evidence.
- Every schema and query/read response carries the exact packaged Agent Task Analysis method reference (identifier, canonical path, section, and document digest). Machine success is emitted on stdout and structured errors on stderr; human text is not part of this contract.

Verification is owned jointly by the executable schemas/tests and the affected runtime units: contract fixtures must prove strict intent unions, deterministic order, evidence/reference and cursor scope binding, native fidelity, structured status/error semantics, and the distinction between empty-complete, partial, unavailable, and ordinary pagination. The installed-wheel surface must resolve the method reference through `svc lookup`.

If the [multi-repo extension](extensions/multi-repo.md) is active, shared Product TDD remains owned in the shared source rather than copied independently into each repository.
