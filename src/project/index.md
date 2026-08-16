# Project Truth Owners

Use this registry after the [Working Protocol](../working-protocol/index.md)
has identified a stable claim that must outlive the current Task. It names
available durable destinations; it does not select one from an input label,
Working Method, or requested document type.

| Truth | Durable owner | Admission |
| --- | --- | --- |
| Mechanically enforceable implementation fact | source, configuration, schema, test, assertion, or automation | prefer whenever it can prevent drift directly |
| Product promise, behavior, rule, scope, or business language | [Product Truth](prd/index.md) | keep a minimal Product owner; split only for a distinct consumer or cadence |
| Repository development, debug, contribution, or release workflow | root `AGENTS.md`, `CONTRIBUTING.md`, executable configuration, or release source | keep the instruction at the entry used by its consumer |
| Cross-unit authority, topology, or compatibility contract | [Product TDD](product-tdd/index.md) | another unit must rely on it to interoperate safely |
| Expensive internal invariant of one logical unit | [Unit TDD](unit-tdd/index.md) | it survives refactors and is not cheaply enforced or recovered |
| Durable technical decision and rationale | ADR beside the affected owner | real alternatives and long-lived consequences cannot be recovered cheaply |
| Repeated fragile seam in a physical subtree | nearest local `AGENTS.md` | nearby instructions and checks are likely to prevent recurrence |
| Runtime, packaging, observability, migration, or recovery truth | [Deployment](deployment/index.md) | operational behavior is non-trivial |

Before adding a durable surface, require stable useful content, a real
consumer, expensive rediscovery or risk, one canonical owner, and no cheaper
executable authority. Keep evidence, provisional decisions, active Plans, and
bounded artifacts in the [Task Packet](../task-packet/index.md).

Product Truth owns what and why. Product TDD owns admitted cross-unit technical
contracts. Unit TDD owns admitted unit-internal design. Deployment owns
operational reality. These are semantic projections, not a required document
ladder; one change updates only the owners whose claims actually changed.
