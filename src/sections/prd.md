# Product Truth

Product truth owns what the product is for, what users or external systems can observe, which rules and scope apply, and why those commitments exist. It does not own implementation topology, internal sequencing, wire details, or local code contracts.

## Minimal Shape

Start with one `docs/10-prd/README.md` containing:

- product purpose and current pressure
- product claims and evaluation expectations
- capabilities and observable workflows
- rules, invariants, and scope boundaries
- business terms whose meaning must remain stable

Use [the product-truth template](../assets/templates/product-truth.template.md). Do not create an empty glossary or directory family.

## Derivation

Keep the reasoning direction explicit:

```text
drivers -> product behavior and claims -> derived domain structure
```

Market, user, business, hard-constraint, and operational pressures are upstream. Domain boundaries may stabilize language after behavior is understood, but they cannot invent new product obligations.

For each material claim, preserve enough of the following to evaluate it:

- the problem or outcome being committed to
- the driver or rationale
- observable success dimensions
- expected evidence

Do not add hard numeric gates unless the product actually requires them.

## Ownership Boundary

An Intent lens often points here, but only when the product promise changes. A dependency, environment, or implementation constraint can leave product truth unchanged. When product truth does change, update it before describing downstream realization.

Use Product TDD for admitted cross-unit technical contracts, Unit TDD for admitted internal unit design, and Deployment for non-trivial runtime or recovery truth.

## Agent Task-Performance Analysis

SVC provides a local, Agent-driven evidence capability for understanding whether an Agent produced a good, complete, and sufficiently verified terminal task result under changing scope, dependencies, interruption, and context pressure. The calling Agent selects evidence and owns content use, semantic interpretation, competing explanations, and any SVC-mechanism hypothesis; SVC does not issue a quality score, causal verdict, or model-generated conclusion.

The observable promise is bounded and evidence-led: an Agent can inspect immutable collected evidence, distinguish a supported observation from an unavailable boundary, and connect task outcome, possible contributors, verification or handoff horizon, and residual unknowns. Provider health, latency, token or memory use, throughput, and generic tool failure rates are not independent task-performance outcomes. Product evaluation requires evidence-grounded, decision-relevant insight from real task trajectories without forcing a defect or treating chronology as causality.

### Local trust and exposure boundary

Agent-thread evidence is an explicit same-user local workflow. SVC trusts the
calling user, the selected provider location, the local account, and the
operating system; it does not promise protection from root, a hostile process
running as the same user, or adversarial path replacement. Provider data may
still be malformed, oversized, unreadable, or changing, and SVC must report
those ordinary input and capture boundaries honestly.

SVC protects the selected source from its own writes, captured native fidelity,
snapshot identity, an existing output from replacement, Consumer-owned project
files, and release artifact integrity. Resource policy is limited to source,
frame, request, and response-page boundaries. The native evidence authority may
contain every selected provider byte. Structural projection and omission are
derived navigation, not redaction; SVC provides no confidentiality, privacy
mode, or sandbox. The caller owns source selection, output storage, access
control, retention, and disclosure.

## Expansion Rule

Split the single file only when real content has distinct consumers or change cadence. Common pressure-driven splits are drivers, behavior, scope, glossary, and derived domain structure. Every new file needs an owner and content at creation time.
