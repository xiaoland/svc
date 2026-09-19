# Implementation Taste

Use this guidance when Technical Design or Implementation shapes authority,
data, state, boundaries, durable naming, dependency, abstraction, performance,
or complexity. Skip it for mechanical edits whose owner and verification are
already clear. These are rebuttable defaults for lowering change cost, not a
style guide, pattern catalog, or universal architecture.

## Preserve One Authority

Every durable fact, state, relationship, and decision needs one authority.
Treat replicas, caches, views, client state, denormalized fields, and generated
output as projections unless explicitly authoritative. Resolve competing
authority before adding synchronization logic because synchronization cannot
repair an undefined source of truth.

Values crossing a boundary should remain distinguishable as authority facts,
stable references, commands or proposals, user-authored values, or derived
projections. Pass the smallest value that preserves the contract. A reference
or command is often safer than copied detail because the receiver can resolve
current authority. Users own their input, expression, preference, and intent;
they do not own server- or business-controlled permissions, price, inventory,
eligibility, or existing entity state.

Counter-pressure: deliberate snapshots and caches reduce lookup and recovery
cost. Keep them selective, labeled by authority and freshness, and avoid
copying the complete owner contract.

## Make Semantics Searchable

Use direct, consistent names for durable models, fields, commands, events, and
business operations. Use one name for one semantic unless an explicit boundary
translation exists. Difficult naming often reveals prematurely collapsed
concepts or authority states; resolve that ambiguity instead of hiding it in a
generic noun.

Documentation, comments, and interfaces are informal and formal parts of the
module boundary. Explain non-obvious why, invariants, and counter-pressure
where code cannot make them clear; do not narrate mechanics already obvious
from the implementation.

## Shape Deep Boundaries

Software complexity comes mainly from dependency and obscurity. Prefer deep
modules: a small, stable interface should hide substantial coherent capability
and local policy. Push complexity behind the semantic owner rather than
spreading partial knowledge across callers. A shallow wrapper that merely
renames another interface adds dependency without hiding complexity.

Counter-pressure: an intrinsically cross-boundary behavior cannot be made
local by hiding its consumers. Expose authority transfer, compatibility,
migration, propagation, and composition obligations when they materially
change together. Semantic locality does not require a particular directory,
DDD boundary, port/adapter shape, event architecture, or modular monolith.

## Shape Data and State Before Control Flow

Before adding retries, fallback heuristics, orchestration, or generalized
machinery, inspect authority, data shape, state representation, lifecycle, and
boundary contract. Prefer representations that make valid behavior obvious
and invalid behavior hard to express. Use topology, sequence, or state models
when the relation is otherwise obscured.

Keep only the state required to preserve the contract. Each extra state holder
creates synchronization, invalidation, recovery, and observation obligations.
Remove an entity only after accounting for both impediments—its consumers,
compatibility, data, and recovery roles—and attractions—the complexity,
latency, failure surface, or maintenance cost its removal actually saves.

## Spend Complexity for Consequence

Each abstraction, layer, state holder, protocol, switch, dependency, and
indirection must earn its lifecycle cost through behavior, reliability,
clarity, maintainability, performance, or evolvability. Compare the status quo
and include migration, learning, verification, and forgone-option cost.
Measure before optimizing and prefer simple algorithms and structures until a
material bottleneck or correctness need appears.

Use patterns when they clarify authority or stable variation, not because a
pattern name is available. A local exception may be cheaper than a premature
abstraction; repeated change scenarios may later justify the deeper boundary.

## Project the Design into Reality

APIs, data transfer objects, props, commands, events, state, control flow,
tests, assertions, and observability should expose the chosen authority and
boundary model. Tests protect the contract rather than mirror incidental
implementation. When realization repeatedly contradicts the design, revise
the model or proof shape instead of accumulating adapters and exceptions.

Review by asking: Where is authority? What provenance crosses each boundary?
Does the data shape make intended behavior simpler? Do names expose durable
semantics? What consequence pays for every added complexity? Which observation
can discriminate the contract, and what material future change remains hard?
