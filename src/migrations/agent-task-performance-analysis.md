# Migrate legacy Agent-thread evidence to the schema-v3 native authority

Corpus release: 12.0.0.

### Applies when
A project retains schema-v1 raw archives or schema-v2 normalized Agent-thread
bundles and expects current SVC analysis tools to read or convert them.

### Required change
Recollect from the provider-local source into an absent schema-v3 bundle:

```text
svc telemetry agent-thread list [selection options] --json
svc telemetry agent-thread export --thread-id <id> --output <absent.zip> --json
svc telemetry agent-thread export --source <rollout.jsonl> --output <absent.zip> --json
```

SVC does not convert v1/v2 bundles. If the provider source is gone, retain or
delete the old artifact under its owner's policy; it cannot become native
evidence. Treat `manifest.json`, `native.bin`, and `native-index.jsonl` as the
authority core. `trajectory.jsonl` is only a rebuildable navigation cache.

### Verify
Validate the new export with one `svc analysis read` request and one
`svc analysis query` request. Confirm saved automation binds refs and cursors
to that bundle's evidence identity.

### If migration is impossible
Record the unavailable provider source as an evidence boundary. Do not claim
the lossy historical bundle was upgraded.

### Reference
`sections/product-tdd.md` and `sections/deployment.md` own the complete
schema-v3 authority and recovery contracts.
