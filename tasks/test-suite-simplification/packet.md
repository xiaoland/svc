# Test Suite Simplification

- **Objective**: Reduce the test suite to the smallest maintainable proof set that protects public behavior, safety boundaries, recovery semantics, and cross-platform process contracts without coverage-driven cases or repeated implementation checks.
- **Guardrails**: Do not weaken an externally observable CLI, project migration, file transaction, workspace, execution, `dev`, or `run` contract. Keep tests for security, concurrency, interruption, rollback, integrity, and platform-specific regressions when no cheaper gate proves them. Unit fixtures may exercise mechanics but never count as product acceptance. Preserve unrelated working-tree changes and do not commit without explicit authority.
- **Verification**: 166 tests pass. Enhanced test lint passes; mypy passes across 33 source/support files; all five import contracts pass; release projections, 22 Corpus documents, workflow lint, build, and diff checks pass. A repository-external venv loads the built wheel from site-packages and successfully executes help plus exact Corpus lookup. Critical process/concurrency tests remain executable, and the previously recorded real-project acceptance matrix remains the product acceptance authority.
- **Current Truth**: The reviewed suite now collects 166 cases from 151 test functions and contains 5,691 Python lines, down from 198 cases, 174 functions, and 6,420 lines when shared test support is counted consistently. Runtime remains about eight seconds. Removed proofs included mocked acceptance-harness internals, duplicate workspace Git scenarios, project-level transaction rollback repetitions, release snapshots already owned by `check-release-projections`, Pydantic frozen/extra behavior, private constant/helper checks, and synonymous invalid-input variants. Shared project-config builders removed schema-envelope repetition; activation timeout now enters through public `ensure_target`; shared test infrastructure is typechecked; test lint now enforces Pyflakes, Bugbear, safe simplifications, pytest correctness, and the existing import ban.
- **Next Step**: Present the audit result and retained proof rationale for Human review; do not commit without explicit authority.

## Review Rules

A test earns retention when it is the cheapest clear proof of at least one of:

- a public command, serialized protocol, or durable data boundary;
- a security, integrity, ownership, concurrency, interruption, rollback, or platform invariant;
- a non-trivial transformation whose mistake would silently lose or mutate user data;
- a regression that static analysis or a higher-level behavior test cannot express.

A test is removed or narrowed when it only mirrors implementation structure, re-tests a mature library, snapshots current repository data already checked by a dedicated gate, or repeats the same behavior at another layer without proving a distinct adapter boundary.

## Retained Proof Ownership

- CLI adapter and Agent/Human output protocol: 16 cases.
- Init/status/config migration/file transaction/upgrade behavior: 43 cases.
- Corpus lookup/catalog/document/release tooling behavior: 40 cases.
- Workspace/execution/dev/run coordination and process behavior: 38 cases.
- Telemetry and analysis protocols (not redesigned in this unit): 29 cases.

Parameterized boundary matrices account for the difference between 151 test functions and 166 collected cases. They remain only where cases represent different parser forms, migration-loss risks, protocol modes, or release state transitions.
