---
name: svc-verification
description: "Use when designing or performing verification, judging whether results meet requirements and user goals, or reusing or changing tests, checks, and evidence."
metadata: {"version": "16.0.1"}
---

# Verification

Start with the consuming decision and the claim it depends on. Connect product purpose → behavior constraint → observable evidence → judgment rule (oracle). A green build or check cannot repair a broken connection; allow any implementation preserving the required result.

Verification asks whether behavior meets the owned constraints. Validation asks whether those constraints and the result serve the intended goal in context. They can interleave: a valid implementation may expose an inadequate requirement, and a good requirement a weak check. Neither grants Human acceptance or authority for external effects.

## Establish the Claim and Criterion

State the intended result, Product or Technical owner, relevant conditions, and consequences. Separate required behavior from design assumptions. The oracle must reject requirement violations and accept changes preserving all relevant requirements. Routes, DOM shapes, collaborator calls, and internal events may carry observations without becoming requirements.

For example, a save-success prompt is too weak to establish persistence across logins; requiring `/dashboard` may reject a valid route change. Observing the saved value after a new session tests the promise. A precise, repeatable check can still encode a wrong interpretation; checks sharing that interpretation, especially from one Agent, are not independent confirmation. Read [Requirements and oracles](references/requirements-and-oracles.md) when the behavior or judgment rule is unclear, over-specific, or too weak.

## Assess Existing Evidence

Find the smallest existing observation that distinguishes the claim from a material alternative. Local rules, component compositions, connected product paths, and production observations answer different questions. Test or E2E labels and independent opinions do not establish sufficiency. Choose conditions for decision-changing uncertainty, preserve the boundary being judged, and distinguish acceptance evidence from diagnostics.

Reuse a qualified guarantee when its scope, assumptions, and consumer connection still cover the decision; proceed directly to the conclusion if evidence is adequate. Read [Evidence](references/evidence.md) when observation, boundary, dependency, measurement, reproducibility, reuse, or conclusion scope is the missing part.

## Obtain Missing Observations

If evidence is inadequate, obtain or repair a proportionate observation under known, authorized conditions. Combine fast feedback with broader product evidence: a check failing for expected missing behavior can guide a small coherent change; premature executable detail can freeze an accidental design during product discovery. Explain criterion changes rather than silently fitting them to results. Read [Feedback](references/feedback.md) when arranging feedback, applying test-first ideas, interpreting mismatches, reusing evidence, or evolving checks.

## Return a Bounded Conclusion

Return the supported or contradicted claim, examined scope, trusted assumptions, material residual, and changes that would require requalification. Stop when evidence supports the consuming decision; do not add observations to complete a ritual. If no feasible, authorized, proportionate continuation exists, return partial or unavailable evidence, the unmet condition, and the smallest viable next action. Do not relax the obligation or claim Human acceptance.

## Authority and Task Continuity

For every non-trivial Task, preserve the surrounding Task Packet's obligations and recover or create its smallest packet at the project's authorized location. This Skill does not create a competing task or mandatory evidence document. Human intent, preference, permission, material trade-offs, and acceptance remain Human authority; this Skill supplies no write, delegation, external-effect, or acceptance authority. Other Skills may provide optional guidance when available, but this directory is self-contained and remains actionable when they are absent.
