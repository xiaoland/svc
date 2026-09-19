# Task Packet Information Modules

Use an information module when a distinct task-local semantic owner reduces
reconstruction, stale-state, or conflicting-edit cost. Keep the information
inline in `packet.md`, a Plan, or a Slice while that is cheaper. Module files
may grow behind a stable entry and same-stem directory; file count does not
define the module.

## Inquiry

Inquiry owns the current answer to a material question: boundary and freshness,
evidence versus inference, current synthesis, competing explanations, and
residual. Diagnosis is Inquiry about why a mismatch occurred, not a separate
top-level module. A diagnostic matrix is an optional discriminator artifact,
not an alternate Task Packet type. The inquiry does not own how freshness is
measured or the Explore method used to improve it.

## Design

Design owns the current coherent proposed solution, forces, material live
alternatives, representative consequences, and residual. It is a result
surface; Task-map and Plan files own the process of producing or realizing it.
Use the cheapest truthful carrier—a diagram, pseudocode, prototype, or code
may carry part of the design—without hiding material rationale or obligations.

## Decision

Decision records an authoritative choice separately from the evolving Design:
subject and state, deciding authority and date, selected option, causal
rationale, consequences, and reopen or supersession condition. Mechanically
shard a large register when that lowers editing and retrieval cost; keep one
stable entry and do not confuse shard size with semantic modularity.

## Verification

Verification state is normally distributed through Claims, Slices, Plans,
Cells, and effect gates. Add a root `verification.md` only when claims,
evidence, residuals, or requalification span several returns and require a
shared synthesis. It is not a final Task phase and does not own acceptance.
Use the [Verification capability](../verification/index.md) for its semantics.

Do not create default Implementation, Delivery, Acceptance, Retrospective,
Agent, Track, Phase, Slice, or generic module files. Add a surface because its
owner and management return are real, not because a template exists.
