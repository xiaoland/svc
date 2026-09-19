# Specifications

| Truth                                                           | Durable owner                                                                    | Admission                                                                   |
| --------------------------------------------------------------- | -------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Mechanically enforceable implementation fact                    | source, configuration, schema, test, assertion, or automation                    | prefer whenever it can prevent drift directly                               |
| Product promise, behavior, rule, scope, or business language    | [Product Requirement Document](prd/index.md)                                     | keep a minimal Product owner; split only for a distinct consumer or cadence |
| Cross-unit authority, topology, or compatibility contract       | [Product TDD](product-tdd/index.md)                                              | another unit must rely on it to interoperate safely                         |
| Expensive internal invariant of one logical unit                | [Unit TDD](unit-tdd/index.md)                                                    | it survives refactors and is not cheaply enforced or recovered              |
| Repeated fragile seam in a physical subtree                     | nearest local `AGENTS.md`                                                        | nearby instructions and checks are likely to prevent recurrence             |
| Runtime, packaging, observability, migration, or recovery truth | [Deployment](deployment/index.md)                                                | operational behavior is non-trivial                                         |
| Repository development, contribution, or release workflow       | root `AGENTS.md`, `CONTRIBUTING.md`, executable configuration, or release source | keep the instruction at the entry used by its consumer                      |

Before adding a durable surface, require stable useful content, a real consumer, expensive rediscovery or risk, one canonical owner, and no cheaper executable authority. Keep evidence, provisional decisions, active Plans, and bounded artifacts in the [Task Packet](../task-packet/index.md).

Product Requirement Document owns what and why. Product TDD owns admitted cross-unit technical contracts. Unit TDD owns admitted unit-internal design. Deployment owns operational reality. These are semantic projections, not a required document ladder; one change updates only the owners whose claims actually changed.


## Extensions

Extensions are optional, they add pressure-specific coordination contracts without replacing the core owner model or Working Protocol. Use one only when its admission rule is satisfied; mono-repository work and ordinary semantic ownership remain the default.

- [Alignment](./alignment/index.md) addresses repeated costly coordination drift in references, boundaries, operations, state, or evidence after normal owners and stable anchors are already insufficient.
- [Multi-repo](./multi-repo/index.md) addresses one product spanning repositories when shared truth otherwise drifts and freshness can be enforced mechanically.

An extension does not own Product/Technical/runtime truth, evidence, Working Methods, or acceptance. Do not create an extension for a one-off Task or to hide an unresolved core owner.
