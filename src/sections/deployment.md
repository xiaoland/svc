# Deployment

Deployment is an optional owner for non-trivial runtime and operational truth: packaging, environment configuration, migrations, rollout, telemetry, mitigation, rollback, recovery, and runtime data locations.

Create it only when operators or developers need stable information that code, configuration, automation, or platform definitions do not expose clearly enough.

Reality work may use logs, metrics, traces, and runbooks as evidence, but the diagnosed cause selects the final owner. Keep code-local recurrence tripwires in the nearest local `AGENTS.md` and product promises in product truth.

## Agent Evidence Runtime

The telemetry runtime owns exact provider-source selection, bounded read-only capture, immutable publication, migration, and recovery. A schema-v3 bundle contains authoritative `native.bin`, validated `native-index.jsonl` framing, a derived `trajectory.jsonl` projection, and a `manifest.json` binding identity, provenance, digests, capabilities, and loss. Publication is atomic, does not overwrite an existing target, keeps the source and output distinct, and retains source identity, symlink/reparse, and time-of-check defenses.

Schema-v1 raw archives and schema-v2 normalized bundles are historical cutoffs, not query/read authorities. Query/read require recollection into schema v3 from an available provider-local source; SVC does not convert an old archive, treat a lossy trajectory as native content, or claim recollection when the source is gone. Migration guidance belongs in the release migration note, while this owner records the runtime consequence and recovery path.

Capture races, bounded reads, and unsupported or malformed records are declared as evidence loss. If capture stops inside a native record, the retained fragment remains readable with an incomplete frame and partial status, but it cannot silently produce a normalized record. Response pagination is ordinary continuation and is kept distinct from acquisition or projection loss. Recovery is explicit recollection from the original source, followed by bundle validation and digest checks; no network, model, or provider-source mutation is used as a recovery shortcut.

Operational verification covers adversarial bundle/source-race tests, migration and recollection smoke checks, atomic absent-target publication, recovery status, and installed-wheel access to the packaged method and evidence contract. Deployment does not own task intent, semantic findings, or query field schemas.

Use [the deployment runbook template](../assets/templates/deployment-runbook.template.md) when an operational response needs a repeatable evidence, mitigation, and recovery path.
