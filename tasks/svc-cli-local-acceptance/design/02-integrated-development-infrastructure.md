# Design Dossier — Separate Dev and Run Domains

## Accepted Domain Shape

`svc run` passed narrow product admission on 2026-08-06. Long-lived development
capabilities and bounded runs remain separate domains. They do not share one
public configuration namespace, command namespace, discovery surface, or
lifecycle model.

Admission evidence is recorded in
[`03-run-product-admission.md`](03-run-product-admission.md) and
[`06-consumer-case-beluna.md`](06-consumer-case-beluna.md).

The public split is:

```text
configuration                         interaction

svc.json                              SVC CLI
├── dev  ---------------------------> ├── svc dev
└── run  ---------------------------> └── svc run
```

The exact `run` configuration is resolved in
[`08-run-configuration.md`](08-run-configuration.md), and its first-slice
grammar and process behavior are resolved in
[`10-run-public-projection-and-process.md`](10-run-public-projection-and-process.md).
The existing `dev` contract remains the baseline rather than a type to
generalize.

## Terminology

### Dev Target

`dev target` is the existing public term for a named long-lived development
capability. Its success condition is readiness, and the capability remains
available after the command returns.

Examples include a frontend server, API server, database stack, emulator, or
another environment resource. `svc dev ensure frontend` may reuse an already
healthy instance or provision one and wait for readiness.

In design prose, the precise English description is **long-lived development
capability**. “Long-run capability” is not used: “long-run” more often describes
a long time horizon, while “long-lived” describes an entity that persists.

### Declared Run

`declared run` is the working public term for a named bounded project operation;
its configuration member is a `run entry`. Each execution instance starts,
executes, and reaches a terminal result. A CLI invocation is not necessarily a
new execution instance: multiple collaborators may converge on one explicitly
identified execution rather than rerunning it because they use different
carriers.

Examples include test, lint, build, code generation, smoke testing, and
migration validation. Its result is based on completion, such as passed,
failed, interrupted, unavailable, or timed out. It has no readiness endpoint,
reused instance, or ready-then-disown lifecycle.

In design prose, **bounded project operation** describes the semantic category;
**bounded run** is the shorter form. “Run target” is avoided because target
already names the long-lived dev lifecycle. “Task” is deliberately not the
primary public name because SVC already uses task and task packet for the
Human-Agent unit of work. “Action” is too broad and already carries several
unrelated meanings in SVC and CI systems.

### Command Names

`svc dev` and `svc run` are natural English CLI names:

- `dev` conventionally qualifies development-environment commands and is
  already established by SVC.
- `run` is the conventional imperative verb for executing a named operation.

Using `run` as the configuration namespace is also intentional. Configuration
namespaces describe product domains and do not need to be grammatical nouns;
matching `run` in configuration and CLI reduces translation cost.

## Why the Domains Stay Separate

| Concern | `dev` / dev target | `run` / declared run |
|---|---|---|
| Purpose | Make a development capability available | Execute one bounded operation |
| Terminal condition | Readiness succeeds | Invocation completes |
| State after CLI return | Capability may remain alive | Operation has ended |
| Reuse | Healthy instance may be reused | Terminal evidence may be inspected, but is not silently reused as fresh |
| Coordination | Scope, endpoint identity, lock, second probe | Execution identity, one native attempt, follow/inspect, terminal evidence |
| Core result | `reused`, `started`, conflict, readiness timeout | passed, failed, interrupted, timed out |
| Examples | frontend, API, database, emulator | test, lint, build, codegen, smoke |

Combining these domains would make discovery and verbs ambiguous even if a
tagged configuration union kept their fields technically distinguishable. The
separation is therefore product topology, not merely a schema implementation
choice.

## Interaction Topology

```text
Agent / Human / optional IDE Task
                  |
                  +--> svc dev ... ----> project-owned environment mechanisms
                  |
                  +--> svc run ... ----> project-owned bounded tools

CI workflow ------+--> svc dev ...  (when environment readiness is needed)
                  |
                  +--> svc run ...  (when a bounded operation is needed)
```

IDE Tasks and CI workflows remain invocation carriers. They do not merge the
two domains or define their semantics.

## Configuration Topology

Illustrative shape only:

```json
{"dev":{"profile":"local","profiles":{"local":{"targets":{"frontend":{"probe":"...","provision":"..."}}}}},"run":{"check":{"argv":["pdm","run","test"]}}}
```

The top-level `dev` / `run` separation remains the accepted fact. The minimum
run contents are now frozen in
[`08-run-configuration.md`](08-run-configuration.md).

## Implementation Reuse Is Not a Public Model

The two domains may later reuse low-level implementation utilities such as
configuration parsing, workspace resolution, exact argument-array execution,
bounded working directories, interruption cleanup, and output helpers. That is
an implementation judgment, not a reason to expose a common declaration,
command, discovery list, result type, or “integration spine” concept to users.

Concrete run and existing dev consumers have now justified one neutral private
execution boundary for process-attempt mechanics. It is accepted only at that
depth and remains invisible to public configuration and interaction. See
[`04-shared-execution-coordination.md`](04-shared-execution-coordination.md) and
[`09-dev-execution-reuse.md`](09-dev-execution-reuse.md).

## Shared Collaboration Invariant, Different Lifecycles

The meaningful relationship between `dev` and `run` is not a common
schema or generic runner. It is a Human-Agent collaboration invariant:

```text
several callers expressing the same explicit intent
-> one shared executable state
-> every caller can observe the same evidence
```

For `dev`, the shared state is a long-lived capability whose readiness probe
proves whether it can be reused. For `run`, the shared state is one bounded
execution identity and its eventual terminal evidence. The bounded case cannot
infer freshness or input equivalence from a run-entry name.

## Product Definition Status

The product definition is solidified. Native command output and the bounded SVC
execution receipt are separate semantic outputs; the run-only public projection
is frozen in
[`10-run-public-projection-and-process.md`](10-run-public-projection-and-process.md).

## Explicit Non-Goals

- one generic entry type or command spanning dev targets and declared runs
- reimplementation of project runtimes, test frameworks, build systems,
  linters, package managers, or diagnostic tools
- replacement of IDE Tasks or a CI workflow engine
- project context discovery or semantic impact inference
- a shell language, general DAG scheduler, automatic repair, or LLM
  interpretation by default
- ownership of merge policy, release orchestration, deployment, or the complete
  software-delivery lifecycle

Product admission does not pre-approve a public schema or implementation.
