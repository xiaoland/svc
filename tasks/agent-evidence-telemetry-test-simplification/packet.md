# Agent Evidence and Telemetry Test Simplification

- **Objective**: Preserve the complete externally observable Agent evidence,
  telemetry, and analysis behavior while reducing implementation and test
  ownership through mature libraries, provider-native authorities, simpler
  internal boundaries, and higher-value analysis capabilities.
- **Guardrails**:
  - This is a fresh current-source review. Do not read, reuse, compare with, or
    derive conclusions from any other `tasks/` packet or historical audit.
  - Slice 1 test restructuring is authorized and complete. Do not modify runtime
    code, dependencies, or durable product documents until the user explicitly
    starts another approved implementation slice.
  - Existing CLI commands, inputs, outputs, archive formats, references,
    cursors, status/error semantics, determinism, and supported workflows are
    immutable compatibility contracts. Internal replacement must be proven by
    black-box characterization, not by deleting or weakening those behaviors.
  - Static typing, the compiler, linters, schemas, and mature library contracts
    own what they can prove; do not duplicate those facts in pytest.
  - Do not reinterpret earlier permission to question product requirements as
    permission to remove current external behavior. New analysis capability may
    be proposed, but compatibility remains the floor.
  - Preserve unrelated modified and untracked task material.
- **Verification**:
  - Measure production LOC, test LOC, pytest item count, fixture complexity,
    subprocess/filesystem/concurrency use, and implementation-private coupling.
  - Classify every focused test as retained contract, redundant static proof,
    mature-library duplication, low-value product guarantee, or high-cost seam.
  - Identify mature libraries or simpler platform architecture that can delete
    both implementation and tests; use current official documentation.
  - Replace implementation-private tests with black-box compatibility tests,
    schema/model validation, type/static proofs, and upstream-library contracts.
  - Identify which current `svc analysis` results genuinely synthesize evidence
    beyond raw JSONL selection, and specify the product gap if `jq`/`rg` plus
    documentation can reproduce them completely.
  - Estimate implementation and test reduction without counting any external
    contract deletion as savings.
- **Current Truth**:
  - The scoped surface includes `svc_cli.analysis`, `svc_cli.telemetry`, their
    provider adapters, `tools/accept_agent_thread.py`, and the directly owned
    `tests/test_analysis_*`, `tests/test_telemetry_*`, and
    `tests/test_accept_agent_thread.py` files.
  - The focused surface is 10,360 lines: 6,371 lines in `svc_cli.analysis` and
    `svc_cli.telemetry`, 753 lines in the installed-wheel acceptance harness,
    and 3,236 lines in ten focused test files.
  - The focused suite collects 123 pytest items, 62% of the repository's 198
    remaining tests. Parameterization expands 88 written test functions into
    that item count.
  - The largest production owners are Codex trajectory projection (1,209),
    generic trajectory schema/validation (1,140), Codex rollout acquisition
    (892), analysis query (759), and evidence ZIP validation (746).
  - Product documents currently require an immutable four-member schema-v3 ZIP,
    byte-exact native framing, a normalized trajectory projection, stable refs,
    scoped opaque cursors, closed query/read protocols, bounded-loss taxonomy,
    provider inventory, and installed-wheel acceptance. These are product-owned
    custom protocols, so their tests cannot be removed honestly without first
    deleting or reducing the promises.
  - Of the 123 focused pytest items, 106 exercise the nine runtime test files
    and 17 exercise the installed acceptance harness. Most runtime tests import
    private analysis/telemetry modules directly; the supported product surface
    is the CLI and its emitted ZIP/JSON contracts.
  - Current `svc analysis` is a verifiable, provenance- and coverage-aware
    navigation layer. Its additional value over raw `jq`/`rg` is evidence
    authority, loss visibility, stable references, bounded deterministic
    continuation, and exact native recovery—not greater query expressiveness or
    semantic task analysis. Semantic normalization happens during acquisition;
    `query` and `read` only select, aggregate, and slice it.
- **Superseded Direction**:
  - The earlier full-removal and native-locator-only proposals are rejected by
    the user's compatibility constraint. Their deletion estimates remain useful
    only as a measure of product ownership, not as admissible implementation
    plans.
- **Current Candidate Direction**:
  - Characterize the current surface as a black-box compatibility suite before
    refactoring internals.
  - Use Pydantic strict, frozen, extra-forbid models for query/read request
    unions and suitable manifest/index/trajectory shapes. Translate validation
    failures back into the exact existing stable error protocol. Pydantic is
    already a locked runtime dependency, so this adds no dependency surface.
  - Retain the current strict JSON decoder and canonical serializer. Pydantic's
    JSON parser accepts duplicate keys by keeping the last value and can admit
    non-finite values through open nested data; its serializer does not own
    SVC's sorted canonical digest bytes.
  - Do not add JMESPath to implement the current five closed predicates. It
    cannot replace native byte text semantics, refs, ranges, budgets, cursors,
    coverage, or canonical ordering, and the compatibility adapter would be at
    least as complex as the current filter loop. Reconsider it only if a future
    internal projection has materially richer fixed expressions.
  - Do not put Codex app-server or the native recorder on the evidence-authority
    path. App-server provides version-specific list/read/item/search DTOs and an
    unstable thread path, but not exact raw frames, malformed-line retention, or
    SVC cursor/loss semantics. The recorder is an internal asynchronous writer
    that may add a newline, materialize compressed data, and skip malformed
    records; using it would violate read-only exact-byte capture.
  - App-server may be evaluated later as an optional metadata adapter, after a
    second implementation proves the same list result corpus. It cannot replace
    the offline compatibility path while external behavior is immutable.
  - Treat `jq` and `rg` as investigation escape hatches over native JSONL, not as
    the value proposition of `svc analysis`.
  - Extend SVC analysis with a new, closed, deterministic case/episode intent;
    do not change `overview`, `match`, or `read`. It should reconstruct bounded
    evidence chains, join tool calls/results, expose verification/handoff and
    terminal horizons, calculate coverage-qualified observations/metrics, and
    return evidence-linked unknowns/gaps. It must not fabricate a causal verdict,
    quality score, or natural-language summary; the calling Agent remains the
    semantic owner.
- **Test Classification**:
  - Delete after black-box coverage exists: exact SQLite transaction mechanics,
    private collector accounting, private normalizer scheduling/probing order,
    tempfile choices, process-umask output-mode assertions, and direct tests of
    private dataclass/helper behavior.
  - Consolidate at boundaries: strict duplicate/non-finite JSON rejection, ZIP
    member/integrity corruption, SHA-bound native coverage, UTF-8/base64 exact
    reassembly, partial/unavailable distinctions, and provider shape/loss
    variants. These remain product behavior but do not need repeated helper-
    level assertions.
  - Delegate ordinary shape proofs to Pydantic and mypy: closed keys, field
    primitive types, bounds, and discriminated request/record unions. Retain one
    valid/invalid adapter case per public error family, not a test for each
    Pydantic-owned branch.
  - Product-created compatibility protocol: exact ZIP members, native frame coverage/digests,
    normalized record taxonomy, task references, capability/loss diagnostics,
    query predicates, references, cursors, pagination, and status distinctions.
    These behaviors remain. Their verification should be consolidated into
    boundary-level compatibility cases rather than repeated across internal
    helpers.
  - High-value retained contracts: correct source selection,
    source bytes not mutated, a successful snapshot matches its source, an
    existing output is not replaced, and one installed CLI smoke.
- **Compatibility Test Shape**:
  - Freeze one small Codex JSONL corpus covering complete, malformed, partial,
    opaque, tool-link, task-ref, binary/UTF-8, and archive-state cases.
  - Verify only public CLI/ZIP/JSON results for inventory, export, query, and
    read, with a compact table of stable structured-error cases.
  - Keep roughly 10–15 deep validator cases for properties that cannot be
    reached cheaply through the CLI; replace the remaining internal tests with
    roughly 25–35 black-box scenarios. Target 35–50 focused tests total, a
    55–70% item reduction from 123, without removing a public behavior.
  - During refactoring, differentially run the old and new implementation over
    the frozen corpus. Delete the old implementation and differential harness
    only after outputs, error classes, archives, and native bytes agree.
- **Slice 1 Result**:
  - Production and tool implementation code is unchanged. The change is limited
    to ten focused test files plus one shared test-only evidence corpus builder.
  - Focused pytest items fell from 123 to 37 (70%); the repository suite fell
    from 198 to 112. Focused test/support code fell from 3,236 to 2,401 lines
    (835 lines, 26%) despite adding the shared corpus authority.
  - Analysis tests now cross a real schema-v3 ZIP through public
    `execute_query`/`execute_read` boundaries. Provider tests assert final public
    descriptors, captured bytes/indexes, validated projections, and manifest
    loss rather than private scheduling or SQLite transaction mechanics.
  - Archive, CLI, evidence, trajectory, and installed acceptance tests retain
    exact members/native bytes, no-overwrite, structured JSON errors,
    canonical/digest validation, loss/status distinctions, and installed-wheel
    inventory/evidence/query/read coverage.
  - Removed proof duplication includes process umask, exact SQLite `BEGIN`,
    private collector accounting, helper ordering, whitelist permutations, and
    exhaustive parameter expansion over library/model-owned branches.
  - One representative invalid case remains per public error family; exhaustive
    min/max permutations are intentionally not restored merely to increase
    branch counts.
- **Slice 1 Verification**:
  - Focused suite: 37 passed in 0.21 seconds.
  - Full suite: 112 passed in 1.49 seconds.
  - Ruff tests, mypy, import-linter, document validation, and `git diff --check`
    pass.
  - A fresh wheel built as 11.0.1 and the independent installed acceptance
    harness passed all four slices (`inventory`, `evidence`, `query`, `read`)
    with cleanup passed.
- **Analysis Product Gap**:
  - Existing `query` cannot traverse relationships into an Agent-move → tool →
    observation → update chain, segment a case/episode, join call/results into
    retry or unresolved facts, locate verification/terminal horizons, or qualify
    a metric by field-level evidence coverage.
  - A new case/episode response should contain rule and method versions, request
    fingerprint, bounded scope, stable episode IDs, ordered evidence-linked
    observations, coverage-qualified metrics, horizons, unknowns, and gaps.
    Empty-complete, not-observed, partial, ambiguous, and unavailable must remain
    distinct. Native payload stays refs-first and is read through the existing
    `read` tool.
- **Implementation Slices Requiring Approval**:
  1. Freeze the public compatibility corpus and replace implementation-coupled
     tests with the black-box test shape; no production behavior change.
  2. Introduce Pydantic request and evidence/trajectory boundary models behind
     exact error/serialization adapters; run old/new differential verification,
     then remove hand-written shape branches and redundant tests.
  3. Design and add the new case/episode analysis contract as an additive
     Behavioral SemVer feature, with real-thread dogfood before implementation.
  4. Only after the first three slices, prototype an app-server metadata adapter
     and retain it only if it deletes more compatibility code/tests than it adds.
- **Success Measure**:
  - Zero externally observable regressions under a frozen compatibility corpus.
  - Fewer hand-written validators, parsers, query branches, fixtures, and
    implementation-coupled tests.
  - A smaller set of end-to-end contract cases plus model/property/static checks
    that cover the same externally reachable behavior.
  - `svc analysis` has explicit semantic outputs that cannot be reproduced by a
    direct `jq`/`rg` selection recipe alone.
- **Next Step**: Review Slice 1 results, then obtain explicit approval before
  Slice 2 introduces Pydantic boundary models. The analysis case/episode
  contract remains a separate product-design decision and must not be smuggled
  into that compatibility refactor.
