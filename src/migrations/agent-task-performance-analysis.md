# Migrate Agent Task Analysis to SVC 12.0.0

SVC 12.0.0 is a Behavioral SemVer MAJOR cutover for agent-thread evidence.
The old normalized-only analysis surface is not a compatibility input to the
new tools.

## Recollect schema-v1 and schema-v2 evidence

Query and read accept only an immutable schema-v3 evidence bundle. A v1 or v2
bundle is identified from its bounded manifest and rejected with
`unsupported-agent-thread-bundle-schema`; SVC does not convert it, read its
native/index members as a fallback, or re-export it. If the provider-local
source still exists, select that source explicitly and recollect:

```text
svc telemetry agent-thread list [selection options] [--json]
svc telemetry agent-thread export --thread-id <id> --output <absent.zip> [--json]
svc telemetry agent-thread export --source <rollout.jsonl> --output <absent.zip> [--json]
```

The source remains read-only and the destination must be absent; do not use a
live source or a guessed latest thread as a substitute for explicit selection.
If the provider source is gone, the old bundle cannot be upgraded into native
evidence. Retain or delete it only under the owning repository's normal policy.

## Understand schema-v3 authority

The four-member export is:

- `native.bin`: captured provider bytes/values and source order;
- `native-index.jsonl`: validated contiguous native ordinals, byte ranges,
  source coordinates, per-frame digests, and `complete|incomplete` status;
- `trajectory.jsonl`: a digest-bound derived structural index;
- `manifest.json`: evidence identity, provenance, capture status, capabilities,
  member digests, and declared loss.

Read native material through `analysis read`; do not treat trajectory fields as
native content. A final incomplete acquisition frame remains readable but
cannot produce a normalized trajectory record. Projection loss can make query
coverage `partial` without deleting captured native bytes. Query/read responses
report `complete`, `partial`, or `unavailable`; ordinary pagination and cursor
continuation do not change evidence status.

## Replace `analyze` with `query` and `read`

The former `svc telemetry agent-thread analyze` command and Textual navigator
are removed. Use two machine-first tools:

```text
svc analysis query --schema
svc analysis query --input <evidence-v3.zip> --request <file|->
svc analysis read --schema
svc analysis read --input <evidence-v3.zip> --request <file|->
```

`query` accepts the closed `overview` or `match` intent and returns bounded,
deterministically ordered descriptors and stable refs. `read` starts at the
first native frame or an exact native ref, optionally includes bounded
preceding records, and continues only with a scope-bound cursor. It returns
captured native bytes/values, exact frame or fragment offsets, digests,
provenance, capture gaps, and continuation. UTF-8 fragments are exposed as
exact text, while arbitrary bytes use a lossless base64 fallback. Read does not
filter, summarize, score, reorder, or silently substitute normalized text.

Both tools emit JSON by default, return structured errors, and expose a compact
method reference. Load the packaged Agent Task Analysis method before
interpreting evidence:

```text
svc lookup --name 'sections/working-protocol\.md' --all --json
```

The calling Agent owns hypotheses, comparison, episode/case interpretation,
and conclusions. SVC supplies evidence and deterministic navigation; it does
not provide a semantic analyzer, quality score, causal verdict, or model
generated summary.

## Remove obsolete controls and update callers

Remove `--include-sensitive`, `--repo`, TTY-only analysis branches, and any
assumption that exported members are private-mode files. The caller now owns
content exposure and output location, while SVC retains source immutability,
absent-target/no-overwrite behavior, source/output separation, bounds,
canonical order, and integrity checks. SVC does not promise atomic visibility,
symlink/reparse exclusion, hostile same-user defense, or path-race protection;
see the local-trust-boundary migration note. Update automation from the old
`analyze --json` response to the query/read request and response schemas; bind
saved cursors and refs to the same evidence ID and request scope.
