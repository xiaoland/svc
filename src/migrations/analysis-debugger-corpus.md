# Adopt payload-bearing Coding Agent debugger and profiler evidence

Corpus release: 15.0.0.

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

Versionless requests use analysis v3. Only evidence v4 is accepted; evidence
v1-v3 must be recollected. There is no query or read compatibility path for
older bundles.

### Verify
Run `svc analysis --schema`, export one Codex or standard Pi session, and
complete `overview` plus `trace` or `profile` without reading provider
state. Confirm usage unknowns and incomplete descendants remain explicit.

### Reference
Product and runtime boundaries are documented in
`docs/prd/agent-analysis.md`, `docs/product-tdd/agent-analysis.md`, and
`docs/deployment/agent-analysis.md` in the SVC source repository.
