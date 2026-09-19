# Adopt Coding Agent debugger/profiler analysis v3

Use this guide when a project exports Agent evidence or calls `svc analysis` v2.

Export new self-contained evidence explicitly by provider:

```text
svc telemetry agent-thread export --provider codex|pi (--id <id> | --source <path>) --output <evidence-v4.zip> --json
```

Then send explicit v3 requests. Start with `{"version":3,"intent":"overview"}` and use one `trace` or `profile` request for the diagnostic question. Use `read` only for content/blob recovery or native audit. Discover exact request/response schemas with `svc analysis --schema`.

Requests without `version` continue to use analysis v2 with evidence v3. Analysis v2 rejects evidence v4. Query v3 reports `re-export-required` for evidence v3 because that bundle lacks the required payload-bearing trajectory; read v3 still supports its native references. Evidence v1/v2 must be recollected.

Replace code that joins native frames, reconstructs parent/sub-agent relationships, or sums token counters. Analysis v3 now owns those mechanical operations and reports coverage, ambiguity, and unknown values explicitly. Keep semantic diagnosis and task-quality conclusions in the calling Agent.

Legacy `--codex-home` and `--thread-id` flags remain aliases. Pi subagent extensions, additional provider adapters, arbitrary query/grouping DSLs, online control, and automatic causal conclusions are not part of this release.
