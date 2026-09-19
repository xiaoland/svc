# Adopt payload-bearing Coding Agent debugger and profiler evidence

Corpus release: 14.1.0.

### Applies when
A project exports Agent evidence or calls the versionless `svc analysis`
query/read contract and wants parent/sub-agent or usage diagnostics.

### Required change
Export new self-contained evidence explicitly with `--provider codex|pi`
and send analysis requests with `version: 3`. Start with `overview`, then
use one `trace` or fixed-breakdown `profile` request. Remove caller code
that reconstructs provider logs, joins tool calls/results, or sums token
counters; analysis v3 owns those mechanical operations. Keep semantic
diagnosis and task-quality conclusions in the calling Agent.

Versionless requests continue to use analysis v2 with evidence v3.
Analysis v2 rejects evidence v4. Query v3 reports `re-export-required`
for evidence v3; read v3 retains native access. Evidence v1/v2 must be
recollected.

### Verify
Run `svc analysis --schema`, export one Codex or standard Pi session, and
complete `overview` plus `trace` or `profile` without reading provider
state. Confirm usage unknowns and incomplete descendants remain explicit.

### Reference
Product and runtime boundaries are documented in
`docs/prd/agent-analysis.md`, `docs/product-tdd/agent-analysis.md`, and
`docs/deployment/agent-analysis.md` in the SVC source repository.
