# Design Dossier — Run Product Admission

## Status

`svc run` was admitted by Sir on 2026-08-06 as a narrow shared-execution surface
for one project-owned bounded command. Its minimum public and implementation
contract is now resolved by dossiers 07–10; canonical and code mutation still
await an explicit start instruction.

## Admission Question

Does a bounded SVC acceptance interface materially improve both:

1. an Agent's ability to maintain a large software project; and
2. the efficiency and fidelity of Human-Agent collaboration;

compared with invoking the project's existing tools directly?

“One unified CLI” is not an answer. The feature must earn its complexity through
an observable outcome that existing tools do not already provide cheaply.

## Rejection Baseline

Reject `svc run` if its behavior is substantially:

```text
resolve a name -> execute argv -> forward stdout/stderr -> return child exit code
```

Also reject it if every Agent, Human, IDE, or CI invocation necessarily creates
a separate native execution. A carrier-neutral command name alone does not
create Human-Agent collaboration; it can simply make duplicated work easier to
trigger.

npm scripts, Make, just, VS Code Tasks, Vite Task, Nx, Turborepo, and
Bazel already cover overlapping combinations of named execution, discovery,
dependencies, parallelism, workspaces, affected selection, caching, output
control, Human UI, machine-readable state, and local/CI reuse. SVC should not
build a weaker cross-language version of those systems.

Agent-readable JSON is also not differentiation: several mature tools already
expose configuration, graphs, dry runs, summaries, or event protocols to
machines and Agents.

## Responsibilities That Remain Elsewhere

- Project tools own test, build, lint, typecheck, smoke, cache, dependency,
  affected-selection, workspace, shell, and artifact semantics.
- The Agent owns project-context acquisition, run selection, result
  interpretation, and whether the task is sufficiently verified.
- The Human-Agent relationship owns permission, confirmation, acceptance, and
  high-value judgment.
- IDE Tasks and CI workflows remain invocation carriers.

These existing boundaries cannot be reused as invented `svc run`
differentiators.

## Admitted Distinct Outcome

The admitted outcome is a **shared project acceptance interface**, not a general
task runner:

```text
small committed set of project acceptance entries
-> one explicit bounded execution identity
-> local Agent, Human, and optional IDE Task converge on that identity
-> one native-tool execution attempt remains the execution authority
-> every caller can follow or inspect the same bounded receipt
-> a deliberate repeat creates a new identity instead of silently reusing truth
```

CI invokes the same declared operation and produces the same kind of receipt in
its own execution namespace. It does not join a live process in another host or
checkout.

The receipt identifies both the bounded execution and the
declared acceptance entry, effective declaration/workspace identity, resolved
native entrypoint, settled invocation status, terminal lifecycle facts, and a
binding between the execution ID and its recoverable native output. It must not
parse logs into product truth, issue a quality score, claim that command success
equals task acceptance, or claim that an earlier result is fresh for changed
inputs.

This outcome may differ from a runner because its purpose is not to execute a
graph faster. It makes “which execution are we collaborating around, what
verification did it invoke, with what observable result, and how can another
collaborator follow or inspect it without rerunning it?” cheap and stable across
heterogeneous project tools.

## Why It Could Serve SVC's Purpose

### Large-Project Agent Maintenance

A small, mechanically declared acceptance facade may keep stable project-level
verification entrypoints while the underlying monorepo tools, package managers,
commands, and directory layout evolve. The Agent still uses specialist tools
for context and selection, but it need not reconstruct the supported
acceptance invocation or raw-output recovery procedure each time.

### Human-Agent Collaboration

A shared execution identity and compact receipt may let an Agent report exactly
what is running or ran without pasting an unbounded log or relying on prose
memory. A Human can join an in-flight check or inspect its terminal evidence
instead of repeating it solely for review, distinguish the native check result
from the Agent's interpretation, and deliberately request a fresh run only when
needed.

The SVC repository's two-second pytest case showed that this outcome is not
valuable for every command. The Beluna case established value when an outer
command failed before a nested project harness produced its own receipt and a
later Human needed the exact execution evidence.

## Admission Result

The SVC and Beluna consumer cases produced this result against the admission
tests:

1. **Agent maintenance return**: fewer wrong or missing verification commands,
   less repeated rediscovery, or more accurate next actions.
2. **Collaboration return**: less ambiguity about what ran and what it means,
   cheaper Human scan/reproduction, or better interruption/handoff recovery.
3. **Single-execution convergence**: Agent, Human, IDE, and CI callers can
   follow or inspect one explicit bounded execution instead of repeating the
   native operation merely because they use different carriers.
4. **Cross-carrier stability**: all callers can address the same acceptance and
   execution identities without carrier-specific semantic translation.
5. **Native-tool authority**: SVC does not duplicate dependency graphs,
   caching, affected selection, scheduling, result semantics, or artifact
   ownership.
6. **Net simplicity**: declaration, synchronization, output, migration, and
   maintenance cost is lower than the rework and ambiguity removed.

The Beluna case passes the narrow test; the SVC pytest case remains a useful
negative boundary. Admission does not imply that every project command deserves
a run entry.

## Explicit Non-Differentiators

- one command name across projects
- a generic list command
- compact JSON by itself
- strict argv/cwd/timeout by itself
- child-process cleanup by itself
- dependencies, DAGs, caching, affected analysis, concurrency, or remote runs
- TUI, IDE problem matchers, log viewers, or CI dashboards
- Human authorization, project-context inference, or semantic acceptance

Some may be implementation requirements after admission; none independently
justifies the product surface.

## Evidence Method Before Schema Design

Take one real project trajectory at a time. Reconstruct its native command,
available output/evidence, interruption or review boundary, and what a later
participant had to rediscover or repeat. Then replay the same trajectory with
the minimum shared-execution hypothesis and account for its declaration and
coordination cost. Similar tools may supply implementation precedents, but
cannot substitute for this consumer evidence. Until a trajectory improves
materially, do not design public syntax.

## Overlap Baseline, Not Consumer Evidence

- npm scripts already declare and run named package operations:
  <https://docs.npmjs.com/cli/v12/commands/npm-run>
- VS Code Tasks already provides Human discovery, composition, presentation,
  and problem matchers:
  <https://code.visualstudio.com/docs/debugtest/tasks>
- Vite Task already provides scripts/tasks, dependency ordering, workspace
  execution, caching, and local/CI reuse:
  <https://viteplus.dev/guide/run>
- Nx already provides inferred tasks, pipelines, affected selection, caching,
  TUI, and machine-readable project/task data:
  <https://nx.dev/docs/features/run-tasks>
- Turborepo already provides task graphs, caching, bounded log modes, dry-run
  JSON, and run summaries:
  <https://turborepo.dev/docs/reference/run>
- Bazel Build Event Protocol already provides programmable build/test progress
  and result events:
  <https://bazel.build/remote/bep>
