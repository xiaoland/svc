# DESIGN.md

DESIGN.md is the canonical owner of a project's durable visual truth: the visual system's identity, its component and token conventions, the decisions behind them, the patterns that have been rejected, and the references that calibrate future work. Create it only for a user-facing surface whose look is part of the product promise and would otherwise drift across sessions — sessions forget which button sizes were chosen, revive rejected styles, and let pages diverge until they read as different teams' work.

Admission fails when executable configuration already enforces the fact: tokens the build consumes, a component library with its own contracts, or automated visual checks own their own truth. DESIGN.md owns what those cannot express — why the system looks the way it does, what may not change without a Product decision, and what has been tried and rejected with the reason.

The file sits at the project root. Keep it minimal: a stable visual world needs few facts, and each entry should be a decision a future session would otherwise get wrong. When a design decision is overturned, update the file in the same change; a stale rejected-patterns list is how discarded styles return. Tools that manage their own visual context files, such as Impeccable's `DESIGN.md`, serve as the execution layer; this specification owns the admission and semantic requirements such a file must satisfy.

Use the [DESIGN.md starting shape](../assets/DESIGN.template.md) when creating one.
