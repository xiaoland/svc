# Agent Task-Performance Analysis

Use this [Product Truth](index.md) projection when a Consumer evaluates an
Agent's terminal task result from local evidence. It owns the observable
analysis capability and non-goals; the semantic method, wire contract, and
runtime authority remain with Explore, Product TDD, and Deployment.

SVC provides a local, Agent-driven evidence capability for understanding whether an Agent produced a good, complete, and sufficiently verified terminal task result under changing scope, dependencies, interruption, and context pressure. The calling Agent selects evidence and owns content use, semantic interpretation, competing explanations, and any SVC-mechanism hypothesis; SVC does not issue a quality score, causal verdict, or model-generated conclusion.

The observable promise is bounded and evidence-led: an Agent can inspect immutable collected evidence, distinguish a supported observation from an unavailable boundary, and connect task outcome, possible contributors, verification or handoff horizon, and residual unknowns. Provider health, latency, token or memory use, throughput, and generic tool failure rates are not independent task-performance outcomes. Product evaluation requires evidence-grounded, decision-relevant insight from real task trajectories without forcing a defect or treating chronology as causality.

### Local trust and exposure boundary

Agent-thread evidence is an explicit same-user local workflow. SVC trusts the
calling user, the selected provider location, the local account, and the
operating system; it does not promise protection from root, a hostile process
running as the same user, or adversarial path replacement. Provider data may
still be malformed, oversized, unreadable, or changing, and SVC must report
those ordinary input and capture boundaries honestly.

SVC protects the selected source from its own writes, captured native fidelity,
snapshot identity, an existing output from replacement, Consumer-owned project
files, and release artifact integrity. Resource policy is limited to source,
frame, request, and response-page boundaries. The native evidence authority may
contain every selected provider byte. Structural projection and omission are
derived navigation, not redaction; SVC provides no confidentiality, privacy
mode, or sandbox. The caller owns source selection, output storage, access
control, retention, and disclosure.

## CLI Contract

Telemetry acquires one explicitly selected local provider source; analysis reads
one immutable evidence bundle. Neither surface uploads data, contacts a network
service, invokes a model, or claims an audit-completeness verdict. The calling
Agent owns semantic interpretation and conclusions; SVC owns bounded capture,
native fidelity, snapshot identity, and deterministic structural navigation.

```bash
svc telemetry agent-thread list [selection options] [--json]
svc telemetry agent-thread export (--thread-id <id> | --source <path>) --output <absent.zip> [--json]

svc analysis query --schema
svc analysis query --input /path/to/evidence-v3.zip --request <file|->
svc analysis read --schema
svc analysis read --input /path/to/evidence-v3.zip --request <file|->
```

`list` is one bounded inventory surface. It exposes provider lifecycle,
recognition, and local provenance without predicting whether a source will
still be readable when export begins. `export` requires one exact thread ID or
source path and an absent destination, while keeping the source read-only and
refusing overwrite or source/output aliasing. A successful export is a
validated bundle; an interrupted process may leave an invalid partial target
that must be removed before retry. The caller owns where exported evidence is
stored and who may see it; there is no `--include-sensitive`
acknowledgement, `--repo` boundary, TTY gate, or private member-mode promise.

The schema-v3 ZIP authority is `manifest.json`, `native.bin`, and
`native-index.jsonl`. Native provider bytes remain in source order; framing
records only stable IDs, contiguous byte ranges, source coordinates, and
`complete|incomplete` state. One `evidence_id` binds native and framing bytes.
`trajectory.jsonl` may be included as a derived structural cache, but it is not
evidence authority and can be discarded and rebuilt. Its counts, capabilities,
and loss summary likewise remain derived. A schema-v1 or schema-v2 bundle is a
historical cutoff: query/read reject it after bounded identification; recollect
from the provider-local source.

This is a same-user local workflow, not a security sandbox. SVC does not
protect against root, a hostile process under the same account, or adversarial
path replacement. Native evidence may contain all selected provider content;
structural projection and omission are not confidentiality or redaction. The
caller owns storage, access, retention, and disclosure.

`query` is a closed machine-first protocol with `overview` and deterministic
`match` intents. It uses or rebuilds the structural cache and returns evidence
identity, source/capture facts, derived capability/loss status, stable native
and trajectory references, structural ranges, and bounded
predicate matches over record type, role, tool, relationship, native range, or
literal text. It does not accept arbitrary field selection, SQL/JSONPath,
regular-expression programs, joins, grouping, scoring, or natural-language
prompts. `read` is forward-only native reading: start at the beginning or an
exact native reference, optionally include bounded preceding records, and use a
scope-bound cursor to continue. It returns captured native bytes/values with
exact frame and fragment offsets, digests, provenance, and continuation.
Cursors carry typed request scope and are unsigned local state, not
authenticated capabilities. Frame and fragment digests are computed from the
native bytes when read rather than stored as framing authority.
Exact UTF-8 fragments are directly readable as text; arbitrary bytes use a
lossless base64 fallback. Read never filters, reorders, summarizes, or silently
returns normalized text.

Responses distinguish `complete`, `partial`, and `unavailable`; pagination is
not evidence loss. An incomplete acquisition frame remains readable but cannot
produce a projection record. A missing or invalid cache is rebuilt from native
evidence; failed rebuild makes structural query unavailable without preventing
native read. Query/read are JSON-first. Their machine contracts come from
`--schema`; interpretation guidance and its authority boundary come from:

```bash
svc analysis --help
```

The old `telemetry agent-thread analyze` command and Textual navigator are
removed; analysis is now the composition of explicit `query` and native
`read`, with the calling Agent deciding what the evidence means.
