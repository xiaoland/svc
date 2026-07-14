# Sustainable Vibe Coding

Sustainable Vibe Coding (SVC) is a selective-memory framework for small teams using AI-assisted development. It preserves truths that are costly to rediscover or dangerous to lose without turning documentation into a second software system.

## Core Contract

- Product documentation owns product what and why.
- Code, configuration, schemas, tests, assertions, and runtime checks own mechanically enforceable implementation truth.
- Durable technical documents exist only where those surfaces cannot preserve an expensive contract clearly enough.
- Active task state remains volatile under the working protocol and the consumer project's retention rule.

The [working protocol](sections/working-protocol.md) owns routing, task state, mutation permission, and verification. [Implementation taste](sections/implementation-taste.md) is loaded only when a change requires non-trivial implementation judgment.

## Versioned Consumer Kernel

The release manifest installs four durable documents:

```text
AGENTS.md
docs/00-meta/working-protocol.md
docs/00-meta/implementation-taste.md
docs/10-prd/README.md
```

- `AGENTS.md` contains repository identity, the crucial map, knowledge-owner references, development/debug fast paths, and project-specific execution rules.
- `working-protocol.md` is the single operational contract.
- `implementation-taste.md` is present but loaded only on its trigger.
- `10-prd/README.md` holds the current product truth in the smallest useful form.

It also generates one non-authoritative control file:

```text
.svc/state.json
```

The four durable paths define the knowledge topology, not completeness. Generated state records installed version, release-manifest digest, managed-file digests, applied migrations, plan digest, and verification result; deleting it loses provenance but never deletes product or technical truth.

The kernel is complete only when root instructions contain real repository owners, executable development/debug entries, and a concrete task-retention rule; the protocol is referenced without a local fork; and product truth contains current claims rather than an empty template. Remove every unused placeholder during adoption.

Create `tasks/` only when active work needs a packet. Do not create empty glossaries, route or mode files, archives, TDD layers, Deployment, Alignment, multi-repo surfaces, or local `AGENTS.md` files.

The machine-readable [release manifest](manifest.json) declares every artifact's stable identity, source, consumer target, file class, initialization action, upgrade action, and digest or generator. Paths never imply authority.

| File class | Authority | Initialization | Upgrade |
| --- | --- | --- | --- |
| SVC-managed | Versioned SVC release | Create from the declared payload | Replace only when current content matches installed provenance; otherwise block as drift |
| Consumer-owned | Consumer repository | Seed from a template only when absent | Preserve; validate or advise without overwrite |
| Generated | Declared generator and authoritative inputs | Generate and record provenance | Rebuild explicitly; never treat as a knowledge owner |

Consume SVC through the version-addressable `svc` CLI:

```text
svc status <repo> [--json]
svc init <repo> [--apply <plan-digest>] [--json]
svc migrate <repo> --to <version> [--from-version <version>] [--apply <plan-digest>] [--json]
```

`init` and `migrate` are non-mutating plans by default. Apply requires the exact current plan digest. A migration resolves only registered adjacent steps, validates preconditions, stages and verifies the result before writing, persists a recoverable commit journal, verifies postconditions, and restores the pre-run tree if commit fails or the next invocation finds an interrupted commit. Recovery is reported in command output. Missing provenance, managed drift, Consumer-owned work, stale plans, and failed conditions block with no durable writes.

Machine output includes `schema_version`, stable operation/status names, artifact identities, digests, blockers, and verification results. Exit codes are `0` for healthy/ready/applied, `2` for invalid CLI syntax, `3` for required action or conflict, and `4` for an invalid release or failed operation. SVC emits no outbound telemetry.

The release payloads remain source-first:

- [Root AGENTS template](assets/templates/AGENTS.root.template.md)
- [Working protocol](sections/working-protocol.md)
- [Implementation taste](sections/implementation-taste.md)
- [Product-truth template](assets/templates/product-truth.template.md)

## SVC Behavioral SemVer

Version classification follows declared consumer behavior rather than document wording or accidental buggy behavior:

- **MAJOR** changes a required obligation, default behavior, authority or permission boundary, task-packet semantics, required consumer layout, stable CLI or manifest machine contract, or removes a supported capability.
- **MINOR** adds an optional backward-compatible capability or expands accepted inputs without changing existing obligations or defaults.
- **PATCH** clarifies the contract or fixes implementation to satisfy it without changing consumer obligations, defaults, authority, required layout, or stable machine contracts.

An optional additive layout may be MINOR. A fix may change observed faulty behavior and remain PATCH when it restores an already-declared contract. Every release declares its behavioral impact in the manifest; mechanical checks validate bump compatibility, while review remains responsible for classification truth.

## Knowledge Owners

Use the working protocol to resolve the owner from claim semantics, provenance, and diagnosed cause. The registry below names available durable destinations; it does not assign one from the input label alone.

| Truth | Durable owner | Admission |
| --- | --- | --- |
| Mechanically enforceable implementation fact | Source, configuration, schema, test, assertion, or automation | Prefer this owner whenever it can prevent drift directly |
| Product promise, behavior, rules, scope, business language | [PRD](sections/prd.md) | Always keep a minimal product truth; split only for distinct consumers or cadence |
| Repository development, debug, contribution, or release workflow | Root `AGENTS.md`, `CONTRIBUTING.md`, or executable project configuration | Keep the instruction at the entry used by its consumer |
| Cross-unit authority, topology, or compatibility contract | [Product TDD](sections/product-tdd.md) | Another unit must rely on it to interoperate safely |
| Expensive internal invariant of one logical unit | [Unit TDD](sections/unit-tdd.md) | It survives refactors and is not cheaply enforced or recovered |
| Durable technical decision and rationale | ADR beside the affected technical owner | Real alternatives and long-lived consequences cannot be recovered cheaply; accepted history is superseded, not rewritten |
| Repeated fragile seam in a physical subtree | Nearest local `AGENTS.md` | A local tripwire or mandatory verification prevents likely recurrence |
| Runtime, packaging, migration, observability, or recovery truth | [Deployment](sections/deployment.md) | Operational behavior is non-trivial |

Active reasoning, evidence, provisional decisions, and bounded artifacts are not durable destinations. Keep them in the [task control surface](sections/working-protocol.md#keep-a-task-control-surface) while work is active.

Before adding any durable surface, require all of the following:

- the claim is stable enough to outlive the current task
- losing it would be expensive or risky
- code, tests, schemas, or automation cannot preserve it better
- a canonical owner and real consumer exist
- useful content exists now

No empty placeholder passes this test.

## Optional Extensions

- [Alignment](sections/extensions/alignment.md): repeated coordination drift remains after normal owners and stable anchors are used.
- [Multi-repo](sections/extensions/multi-repo.md): one product spans repositories and shared truth has a mechanically enforceable freshness contract.

Mono-repo is the default. Extensions add only their distinct pressure-driven contract; they do not replace the core owner model.
