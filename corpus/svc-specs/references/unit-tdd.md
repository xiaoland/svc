# Unit TDD

Unit TDD is an optional owner for expensive internal design truth of one logical technical unit. A unit is a stable responsibility boundary, not a directory name.

Admit Unit TDD only when the truth:

- can change without forcing another unit to update
- describes internal authority, storage, sequencing, naming, technology, or contracts
- should survive physical directory refactors
- is not cheaply preserved by code, types, schemas, tests, or assertions

Cross-unit dependencies belong in Product TDD when its admission rule is met. Repeated fragile seams in a physical subtree belong in [local instructions](local-instructions.md).
