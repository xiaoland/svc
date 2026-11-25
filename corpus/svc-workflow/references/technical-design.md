# Technical Design

Use this Workflow design view to propose responsibilities, information, interfaces, failure behavior, and transition. Return an arrangement whose owners can jointly deliver the promised result. Apply the shared judgment to existing code and credible alternatives.

## Assign the Necessary Responsibilities

Follow the promised use across callers, the system, and external participants. Identify the facts and decisions each step needs, who can establish them, and what the consumer must be able to rely on. Allocate these responsibilities before choosing packages, services, or bindings.

Decompose around knowledge that changes together. An importer's format rules can change independently of storage and progress presentation. Compare containing those decisions with spreading format details through callers. When several consumers must coordinate the same business guarantee, consider placing it at a shared responsibility; retain separate owners when their meanings or change pressures differ.

Make change cost concrete: walk a credible new consumer or policy through the candidate and identify which owners need new knowledge and must change together. Weigh a new API or package against the dependency and coordination it removes. A typed entry point wrapping an internal string protocol still leaves protocol consistency to runtime coordination.

## Choose Information and Interfaces

Follow normal repetition and recovery to find which information persists and which resets. Derive identity and lifetime boundaries from those differences. Define authoritative writers, readers, projections, and translations at the boundaries. A limited common capability may use a common model; full native operation may require more information. Sharing a type must preserve both consumers' meaning; separate types still need an agreed contract.

Walk a real caller through the proposed interface. State what it promises and what knowledge it hides, including failure and recovery obligations. Keep commands, accepted requests, committed facts, and displayed results distinguishable where those distinctions affect the promise.

## Trace the Relevant Operation and Failure

Follow an input or action to the result its consumer receives. For state changes, identify the writer, commitment point, persistence, and readers or projections that may lag. Locate the execution path: which operation may wait, and which other participants must continue? Choose blocking, asynchronous, and recovery mechanisms from those obligations. Use an ownership or data-flow sketch when sharing or synchronization needs explanation.

When history changes an action's meaning, describe the triggering event, producer, invariant, and observable result. Trace relevant races and effects already produced: cancellation requested differs from cancellation completed. Compare mechanisms under explicit Product assumptions, using the consequences to settle the Product choices before adoption.

Before adding retries or fallback, distinguish failure before acceptance from a lost reply after commit. Where duplicate effects matter, consider operation identity, result lookup, or an idempotent contract.

Challenge a defining relation under a relevant failure or normal later use. Show how the same owners keep the promise when a view disappears, a caller changes, or a reply is delayed, where applicable. Check associated identities and results together across translation boundaries. Resolve conflicting rules in the arrangement before dependent implementation. Use `svc-taste` when facts leave a consequential trade-off unresolved.

## Design the Transition

For a consequential change, describe current, intermediate, and target states. Trace affected reads, writes, consumers, invariants, failure detection, and recovery or compensation. Include removal of obsolete representations and coordination, subject to actual compatibility and data obligations. Use [Planning](planning.md) when ordering the selected transition needs work.

Return the arrangement, contracts, relevant state and failure behavior, transition, trade-offs, and remaining assumptions at the resolution the current consumer needs.
