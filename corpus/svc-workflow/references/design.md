# Design

Design shapes possible futures into one coherent proposed solution. Use it when intended product or system behavior, realization, or transition is materially underdetermined, conflicting, or likely to become incoherent through local choices. Design owns the evolving relation among forces, commitments, and consequences; it does not own authority to mutate, proof, implementation sequence, or durable project truth.

```mermaid
flowchart LR
  F["Intent, reality, constraints, resources, taste"] <--> S["Proposed product + technical solution"]
  S <--> C["Representative behavior, failure, transition, operation, and change consequences"]
  C -->|"contradiction"| F
  C -->|"invalid commitment"| S
  S --> R["Consumer-relative solution + material residual"]
```

Start with a representative journey or state transition where a decision matters. Trace the current claim through its entry point, owner of data and state, dependencies, and failure or recovery path. Propose one arrangement and challenge it with a plausible counterexample or change. If it fails, revisit the Product claim or Technical boundary and carry the consequences across the affected owners. Stop when the consumer can implement the current horizon without silently deciding a material requirement. Cheap, reversible, local choices remain Implementation freedom unless their consequence is material.

## Keep the Solution and Its Judgment Basis Coherent

- [Product Design](product-design.md) shapes what users and stakeholders can perceive, do, understand, trust, recover from, and value.
- [Technical Design](technical-design.md) shapes how the system realizes, sustains, changes, and operates those obligations.
- [Verification Design](verification-design.md) shapes how the promised result can be observed and judged under relevant conditions.

They are independent views of one solution, not phases or mandatory files. Start from the local design pressure, then load only the methods, taste, examples, and counter-pressure that could change that judgment.

When the solution needs a judgment basis or observable boundary, use [Verification Design](verification-design.md). It keeps expected behavior, technical arrangements, and the means of judging them coherent; discover `svc-verification` by name through the host when criteria, evidence, or feedback need specialist reasoning. Its guidance is optional rather than a required next phase; Design still owns a coherent solution and must expose any unresolved judgment or observation gap when that Skill is unavailable.

## Return at the Useful Resolution

Design enough for the current bounded implementation horizon: the consumer should not be forced to make a silent material Product, Technical, transition, or verification-solution decision. Preserve material assumptions, alternatives that remain live, consequences, and residuals; do not attempt a complete upfront specification.

Choose the cheapest truthful carrier for collaboration and memory: prose, table, topology, sequence, state model, pseudocode, prototype, or code. A document is not required, but code must not hide rationale, rejected material alternatives, or cross-owner obligations that future consumers cannot recover. Distinguish a proposed arrangement from behavior established by applicable evidence; a coherent design alone does not establish its realization or fitness for the intended need.
