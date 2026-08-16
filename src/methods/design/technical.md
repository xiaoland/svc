# Technical Design

Use Technical Design when a solution must clarify responsibility or authority,
data and state lifecycle, interface or dependency, concurrency, failure and
recovery, migration, compatibility, deployment, operability, performance,
security, or changeability. It consumes owned Product/Technical claims and
returns the Technical projection of the same solution described by the parent
[Design method](index.md).

Model authority and dependency topology, lifecycle and sequence, propagation
obligations, representative failure, and future change scenarios when they
affect the choice. Keep ordinary change near its semantic owner; when a change
is intrinsically cross-boundary, expose the consumer, migration, composition,
and verification obligations instead of hiding them behind locality.

Load [Implementation Taste](../../taste/implementation/index.md) for deeper
judgment about authority, provenance, naming, data shape, module depth,
obscurity, and complexity return. Those are rebuttable defaults, not a demand
for bounded-context directories, ports/adapters, ADRs, or a modular monolith.
