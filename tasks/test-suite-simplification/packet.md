# Test Suite Simplification

- **Objective**: Reduce the test suite to the smallest maintainable proof set that protects public behavior, safety boundaries, recovery semantics, and cross-platform process contracts without coverage-driven cases or repeated implementation checks.
- **Guardrails**: Do not weaken an externally observable CLI, project migration, file transaction, workspace, execution, `dev`, or `run` contract. Keep tests for security, concurrency, interruption, rollback, integrity, and platform-specific regressions when no cheaper gate proves them. Unit fixtures may exercise mechanics but never count as product acceptance. Preserve unrelated working-tree changes and do not commit without explicit authority.
- **Verification**: 159 tests pass in about eight seconds. Enhanced test lint passes; mypy passes across 36 source/support files with the Pydantic plugin; all seven import contracts pass; output-schema and release projections, 22 Corpus documents, workflow lint, and build pass. A repository-external venv loads the built wheel from site-packages, retrieves all nine packaged command schemas as one compact line each, and performs exact Corpus lookup. Five real project roots accept typed status/init-plan/upgrade-plan/identity results without mutation; three adopted Consumers correctly stop at their pending schema-v2 configuration migration. Critical process/concurrency tests remain executable; fixture-only checks are not counted as product acceptance.
- **Current Truth**: The reviewed suite collects 159 cases from 144 test functions and contains 5,419 Python lines, down from 198 cases, 174 functions, and 6,420 lines when shared support is counted consistently. Runtime remains about eight seconds. Removed proofs included mocked acceptance-harness internals, duplicate workspace Git scenarios, project-level transaction rollback repetitions, release snapshots already owned by `check-release-projections`, Pydantic frozen/extra behavior, private constant/helper checks, synonymous invalid-input variants, and JSON key-set/field-presence assertions now owned by the output-schema projection. `test_cli.py` now has 10 adapter tests instead of 17 mixed-layer tests: it owns help/grammar, compact framing, channel/exit routing, schema discovery, Agent/Human text, and native-output isolation. Lookup/init/upgrade JSON semantics remain with their typed controllers; manual dev probe evidence and unknown run-entry evidence were folded into existing domain tests without adding cases. Shared project-config builders removed schema-envelope repetition; activation timeout enters through public `ensure_target`; shared test infrastructure is typechecked; test lint enforces Pyflakes, Bugbear, safe simplifications, pytest correctness, and the existing import ban.
- **Next Step**: Review the implementation and verification record. The core CLI machine boundary is implemented; analysis and telemetry remain explicit legacy/unscoped protocols outside this core-business unit. Do not commit without explicit authority.

## Review Rules

A test earns retention when it is the cheapest clear proof of at least one of:

- a public command, serialized protocol, or durable data boundary;
- a security, integrity, ownership, concurrency, interruption, rollback, or platform invariant;
- a non-trivial transformation whose mistake would silently lose or mutate user data;
- a regression that static analysis or a higher-level behavior test cannot express.

A test is removed or narrowed when it only mirrors implementation structure, re-tests a mature library, snapshots current repository data already checked by a dedicated gate, or repeats the same behavior at another layer without proving a distinct adapter boundary.

## Retained Proof Ownership

- CLI adapter and Agent/Human output protocol: 14 cases.
- Init/status/config migration/file transaction/upgrade behavior: 41 cases.
- Corpus lookup/catalog/document/release tooling behavior: 38 cases.
- Workspace/execution/dev/run coordination and process behavior: 37 cases.
- Telemetry and analysis protocols (not redesigned in this unit): 29 cases.

Parameterized boundary matrices account for the difference between 144 test functions and 159 collected cases. They remain only where cases represent different parser forms, migration-loss risks, protocol modes, or release state transitions.

## Machine JSON Contract Redesign — Implemented

The intended authority chain is:

```text
typed output model -> Pydantic serialization -> command JSON
                   -> packaged JSON Schema projection -> consumer discovery
                   -> projection/change gate -> CLI Behavioral SemVer evidence
```

- Strict, frozen Pydantic boundary models own core command results and the shared machine error. Shared workspace, capability, probe, execution-state, log-reference, plan-action, and rollback names are typed once and reused; closed protocol sets use `Literal` rather than opaque strings. Domain controllers may keep simpler internal representations, but no core stdout/stderr JSON is emitted from an arbitrary dictionary.
- One serialization `TypeAdapter` union is registered per public JSON command. Commands with multiple terminal shapes use explicit literal discriminators. `_emit_json` accepts only the registry's result/error union; analysis and telemetry use a separately named unscoped emitter until their independent unit redesigns those protocols.
- `svc <command> --json-schema` exits successfully without executing the command or requiring normal positional arguments and emits that command's compact packaged Draft 2020-12 schema. It is available for `lookup`, `init`, `status`, `upgrade`, `dev identity|status|ensure|stop`, and `run`.
- Packaged schemas are generated from Pydantic's **serialization** mode. The packaged projection, not a dynamically generated schema from whichever compatible Pydantic minor happens to be installed, is what consumers retrieve. Stable protocol model names and schema identifiers are public names.
- A dedicated projection check requires deterministic model generation to reproduce committed schemas. When a packaged schema differs from the comparison ref, the same change must add or modify a `component: cli`, `kind: major` Changie fragment and advance that command family's result-schema version. It compares the stable packaged artifact and deliberately avoids a bespoke semantic-diff engine.
- Treat the first published schema set as a bootstrap projection, not as a change to a previously published schema contract. Its release still needs ordinary CLI change evidence; only later diffs against an existing packaged projection require a new or modified CLI-major fragment.
- Keep a command/family `schema_version` literal and require it to advance with a changed packaged schema. The CLI package version reports the release; the output schema version tells a consumer which machine contract it received.

This replaces per-command field-presence and exact-key assertions. It does **not** replace the smallest CLI adapter proofs for compact one-object framing, stdout versus stderr routing, exit-code mapping, native-output suppression, or follower/owner process behavior. A semantic differential check against the pre-refactor source confirmed unchanged lookup, real-project status/init/upgrade, and workspace-identity output; a mismatch in default-field serialization was fixed in the model layer rather than memorialized with another field assertion.
