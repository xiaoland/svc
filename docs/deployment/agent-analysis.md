# Agent Evidence Runtime

Use this [Deployment](index.md) depth when telemetry capture, bundle storage,
cache rebuild, migration, or recovery behavior matters. Agent conclusions and
query/read wire semantics remain with Explore and Product TDD.

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

Use the [deployment runbook template](../../src/specs/deployment/deployment-runbook.template.md)
when an operational response needs repeatable evidence, mitigation, and
recovery.
