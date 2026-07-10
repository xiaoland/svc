# Product TDD

Product TDD is an optional owner for technical contracts that multiple units must share to interoperate safely while product truth remains separate.

Admit it only when:

- another unit depends on the contract
- changing it can break compatibility, authority, or topology
- code, schemas, and tests alone do not make the contract cheap to recover
- real cross-unit content exists now

It may own unit topology, system state and authority, cross-unit interfaces, compatibility rules, and realization pointers from product claims. It does not own product why or one unit's private implementation.

A Constraint lens does not select Product TDD automatically. Environment, dependency, repository-policy, deployment, source, configuration, or test owners may be correct instead.

Start with one document. Split only when topology, authority, contracts, or realization have distinct consumers or cadence. Use [the Product TDD template](../assets/templates/product-tdd.template.md).

If the [multi-repo extension](extensions/multi-repo.md) is active, shared Product TDD remains owned in the shared source rather than copied independently into each repository.
