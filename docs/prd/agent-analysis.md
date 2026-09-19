# Coding Agent Debugging and Profiling

Use this [Product Truth](index.md) projection when a Consumer must diagnose a Coding Agent or agent harness from local execution evidence. It owns the observable analysis capability and non-goals; Product TDD owns the wire contract and Deployment owns capture and recovery.

SVC is an offline debugger and profiler for Agent executions. “Debugger” means reconstructing observable behavior, relationships, lifecycle, and resource use; it does not mean breakpoints, single stepping, online control, or model-generated causal verdicts. SVC performs the mechanical work required to associate executions, messages, reasoning, tool calls and results, history changes, parent/sub-agent relationships, and usage. The calling Agent combines those facts with task intent and owns explanations, quality judgments, and conclusions.

The primary evidence contract is a self-contained, payload-bearing best-effort trajectory. Provider-native material remains in the same immutable bundle for audit, provider-specific inspection, and future renormalization, but ordinary analysis does not replay provider state. Missing material, tentative mappings, unknown usage, and incomplete descendant collection are reported as coverage issues rather than zero or complete evidence.

The first supported providers are Codex rollout and standard Pi session. Codex collection follows captured parent/child descendants and attributes child usage. Pi collection preserves entry-tree predecessors, branches, compaction, fork history inheritance, and post-fork usage; Pi subagent extensions are not supported.

## CLI Contract

```bash
svc telemetry agent-thread list --provider codex|pi --home <provider-home> --json
svc telemetry agent-thread export --provider codex|pi (--id <id> | --source <path>) --output <absent.zip> --json

svc analysis --schema
svc analysis query --input <evidence.zip> --request <file|->
svc analysis read  --input <evidence.zip> --request <file|->
```

Analysis v3 has four closed query intents. `overview` returns execution topology, lifecycle, per-execution usage, coverage, issues, and drill-down references. `trace` returns associated normalized payloads. `profile` returns fixed execution, model, and tool breakdowns. `match` is a bounded low-level locator, not a query language. `read` consumes content, blob, or native references for exact recovery and native forward reading. Every public reference has a declared query or read consumer.

Usage remains a set of observations, not one invented total. Results distinguish owner, self versus subtree scope, delta/cumulative/gauge temporality, measurement inclusion, reported versus estimated source, metric coverage, ambiguity, and unknown baselines. SVC deduplicates identical samples and excludes inherited history from new fork consumption; it does not sum overlapping scopes, exchange currencies, or turn missing measurements into zero.

Existing requests without `version` retain analysis v2 behavior on evidence v3. Explicit analysis v3 consumes evidence v4; query v3 on evidence v3 reports `re-export-required`, while read v3 can still recover exact evidence-v3 native material. Analysis v2 rejects evidence v4 rather than misreading its multi-material shape. Legacy telemetry flags `--codex-home` and `--thread-id` remain aliases; an export without `--provider` retains the evidence-v3 compatibility path.

This is a same-user local workflow. Export reads selected sources without mutation, refuses output overwrite, and does not upload evidence or invoke a model. Native material can contain sensitive provider content; the caller owns selection, storage, retention, access, and disclosure.
