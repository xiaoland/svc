# Designing Roles

Read this when considering a new Agent role or evaluating an existing one. It expands the entry's role guidance; return an admitted, revised, or rejected role with its reasons.

## A Role Is a Deep Work Module

A useful role resembles a deep software module: a small dispatch and return interface that preserves context isolation, substantial internally coherent work behind it, dependencies and authority narrow enough to avoid continuous synchronization with the caller, a credible local acceptance or escalation path for its output, and a specialized method that improves results beyond a generic prompt.

The best delegation boundary is not a small task; it is a low-coupling cut where the internal work is large relative to the context that must cross the boundary. Delegation value rises with useful internal work, context noise avoided, and independent evidence; it falls with boundary bandwidth, unstable dependencies, weak oracles, integration burden, and effect risk.

## Keep Three Context Layers Separate

1. The role's stable method and invariants, carried by the role itself.
2. The task-specific objective, authority, snapshot, and return contract, carried by the assignment.
3. Source handles, loaded progressively when the work encounters a concrete need.

Preloading the third layer defeats the isolation the role exists for; omitting the second leaves the role guessing at scope.

## Rejected Roles

- **Reviewer or validator Agent:** independent review is a verification strategy, not a standing role. A generic second opinion reproduces the trust paradox instead of resolving it; assign review when a specific residual risk needs a fresh evidence path, and let a trusted mechanism or the Human remain the validator.
- **Current-rule resolver:** an Agent that filters which rules apply risks false omission — the caller may never notice a relevant rule was filtered out.
- **Document writer:** integrating a change into durable truth follows the canonical-owner path (`svc-specs`); a writer role generalizes file count into a delegation boundary, which it is not.

## Authority and Continuity

Roles do not accumulate authority. A role shapes an assignment's boundaries and return; the assignment grants what it grants. Return admission, revision, or rejection decisions to the Task owner, and keep durable role truth with the consuming project's own library when the role is domain-specific.
