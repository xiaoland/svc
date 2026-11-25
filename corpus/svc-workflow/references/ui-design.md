# UI Design

Use this Workflow method when designing or reshaping a user-visible interface whose appearance is part of the result: app screens, dashboards, settings, and other Operate or Read surfaces. It consumes the behavior promises settled by [Product Design](product-design.md) — who arrives, what they do, how each state recovers — and settles the presentation promises: visual authority, direction, composition, and craft floor. A marketing or campaign surface may use it, but its persuasion goals make the method optional rather than expected.

## Name the Surface's Mode

Before choosing any visual element, name what the visitor's success looks like on this surface:

- **Operate:** the visitor completes a task. App UI, dashboards, editors, admin, settings. Scanability, consistency, and native expectations outrank expression.
- **Read:** the visitor understands something. Docs, guides, changelogs. Structure for comprehension first.
- **Persuade:** the visitor decides and acts. Landing and pricing pages. Attention and distinctiveness earn their cost.
- **Experience:** the visitor is inside the work itself. Portfolios and galleries. The artifact leads; the interface recedes.

Choose the mode from the surface, not the product: a tool's landing page is Persuade, its settings screen Operate. Ambition scales with the mode — on Operate and Read it appears as precision and restraint, and patterns the visitor already knows earn their place.

## Establish Visual Authority

Before designing, decide what is already true about this project's visual world, and record durable decisions in the project's `DESIGN.md` (discover `svc-specs` by name for its admission and format).

- **Established world:** inherit it. A missing `DESIGN.md` does not erase an identity already coherent in code; document that identity instead of inventing a replacement.
- **Redesign:** preserve product truth, content, function, and explicit brand commitments; replace the old visual world rather than polishing it halfway.
- **Incomplete brand:** preserve confirmed assets and traits, then expand the system with the Human for this surface.
- **Local addition:** a section, component, or state inside an established surface inherits that surface. Never turn a local addition into a new identity exercise.

## Derive Direction from References

When the direction is open, study two or three real interfaces the Human respects for this kind of surface. Extract their decisions — information density, navigation layering, how primary and secondary actions are told apart, what is deemphasized — not their appearance. Rebuild the useful structure in the project's own components, tokens, and content; never copy branding or layout verbatim.

Keep two layers of constraint distinct. Hard constraints are specific and checkable: contrast ratios, target sizes, complete state coverage, the design system's tokens. Judgment principles receive direction, reasoning, and counterexamples rather than fixed answers. Writing judgment down as fixed parameters makes every project converge to the same output.

When the direction is materially open, explore more than one before committing: render the credible directions side by side for the Human to compare — an artifacts artboard when that tooling is available — rather than converging on the first plausible one. Independently explored directions, not variations of one, are what break early convergence; the comparison, not the count, is the point. When the calling context is itself invested in an incumbent implementation, delegate the exploration to a fresh one: discover `svc-agent-collaboration` by name for the Design Explorer role.

## Plan, Then Challenge the Plan

Write the design plan before code: palette, type, layout concept, and the principles that make this surface specific to its brief. Then challenge it: if a similar request with a different subject would produce the same plan, the free axes were spent on defaults rather than decisions. Revise and state what changed. A pinned brief overrides this check — the Human's explicit aesthetic direction wins over any concern about familiarity.

## Distill Before Decorate

Every element must earn its place against the surface's one primary goal. Remove what adds no information or affordance before adding anything. When a screen seems to need helper text or a secondary label to be understood, repair the hierarchy or layout that created the confusion. Simplicity here means removing obstacles between the user and the goal, not removing capability.

## Verify the Render in Two Channels

DOM snapshots and rendered screenshots answer different questions; neither substitutes for the other. Snapshots verify structure, semantics, and states. Screenshots verify hierarchy, density, proportion, and composition. Inspect the built surface at the sizes it ships at, batch the checks — fix what one look shows before looking again — and operate the real flows, not only the default path. Do not claim a visible result complete without having seen it rendered. Discover `svc-verification` by name when the acceptance criteria for the surface need design.

## Authority and Task Continuity

Human aesthetic preferences, brand commitments, and acceptance retain their authority; a pinned brief overrides every default above. This method grants no write, delegation, external-effect, or acceptance authority. Apply it within the existing Task and return the direction, decisions, and unresolved choices to the Task owner. Discover `svc-taste` by name when a consequential visual trade-off resists the facts.
