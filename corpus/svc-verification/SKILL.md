---
name: svc-verification
description: "Guidance for judging whether results meet requirements and serve user goals, using criteria, evidence, and feedback."
metadata: {"version": "17.0.0"}
---

# Verification

Design how a Product or Technical result will be judged, or assess the evidence for it. Start with the consuming decision and the claim it depends on. Connect product purpose → behavior constraint → observable evidence → judgment rule (oracle). A green build or check cannot repair a broken connection; allow any implementation preserving the required result.

Verification asks whether behavior meets the owned constraints. Validation asks whether those constraints and the result serve the intended goal in context. They can interleave: a valid implementation may expose an inadequate requirement, and a good requirement a weak check. Neither grants Human acceptance or authority for external effects.

## Establish the Claim and Criterion

State the intended result, Product or Technical owner, relevant conditions, and consequences. Separate required behavior from design assumptions. The oracle must reject requirement violations and accept changes preserving all relevant requirements. Routes, DOM shapes, collaborator calls, and internal events may carry observations without becoming requirements.

For example, a save-success prompt is too weak to establish persistence across logins; requiring `/dashboard` may reject a valid route change. Observing the saved value after a new session tests the promise. A precise, repeatable check can still encode a wrong interpretation; checks sharing that interpretation, especially from one Agent, are not independent confirmation. Read [Requirements and oracles](references/requirements-and-oracles.md) when the behavior or judgment rule is unclear, over-specific, or too weak.

## Proportion the Acceptance

Spend verification where a wrong result is likely and costly. Use these defaults unless the Human or project sets another acceptance scope:

- **Key path first.** List the main-path promises the user relies on; acceptance covers them and obvious visible defects. Select further conditions by likelihood × loss: drop rare, low-loss edges or move them to a cheaper layer.
- **Verify at the owning layer.** Check each claim at the layer that owns it: input rejection, protocol detail, and boundary values belong to unit or library checks; end-to-end runs anchor key user paths. After a change, recheck only layers whose evidence it invalidated.
- **Choose means by total cost.** Prefer, in order, reading code, programmatic entries (test frameworks such as XCTest, CLIs, adb, scripts), isolated environments (simulators, headless browsers), and finally foreground computer-use or browser-use. Total cost includes the Human's device, focus, input devices, and attention. Start acceptance environments when observations are due. When a needed observation lacks a programmatic entry, propose adding one.
- **Size tests to risk.** Write tests for contracts that consumers rely on; for reversible, low-impact behavior, skip tests that restate the implementation. Once the required checks pass, widen or repeat testing only for a new change, a failure, or an open question.
- **One complete acceptance at delivery.** During implementation, use local checks for the affected layers. Before delivery, walk the key path and the visible result yourself once, including UI; layered passes cannot show what the user will see.
- **Match evidence to the claim.** Artifact hashes, signatures, rereading written files, and toolchain runs are diagnostics unless the claim concerns them.

The Human may waive or take over acceptance; record what remains unverified.

## Assess Existing Evidence

Find the smallest existing observation that distinguishes the claim from a material alternative. Local rules, component compositions, connected product paths, and production observations answer different questions. Test or E2E labels and independent opinions do not establish sufficiency. Choose conditions for decision-changing uncertainty, preserve the boundary being judged, and distinguish acceptance evidence from diagnostics.

Reuse a qualified guarantee when its scope, assumptions, and consumer connection still cover the decision; proceed directly to the conclusion if evidence is adequate.

## Design Missing Observations

When new observations are needed, design them before implementation or to fill an evidence gap. Choose conditions that can expose relevant failures and the smallest observation boundary that preserves the promise. Identify facilities needed to make the result observable. Read [Evidence](references/evidence.md) for condition selection, observation facilities, dependencies, measurement, reproducibility, reuse, or conclusion scope.

When verification design is the result currently due, return the proposed claims, conditions, observations, judgment rules, required system changes, and gaps. A proposed observation is not evidence that the behavior occurred.

## Obtain Missing Observations

If evidence is inadequate, obtain or repair a proportionate observation under known, authorized conditions. Combine fast feedback with broader product evidence: a check failing for expected missing behavior can guide a small coherent change; premature executable detail can freeze an accidental design during product discovery. Explain criterion changes rather than silently fitting them to results. Read [Feedback](references/feedback.md) when arranging feedback, applying test-first ideas, interpreting mismatches, reusing evidence, or evolving checks.

## Return a Bounded Conclusion

Return the supported or contradicted claim and examined scope. Report trusted assumptions, residual, and changes that would require requalification when they change use or the next decision. Stop when evidence supports the consuming decision; do not add observations to complete a ritual. If no feasible, authorized, proportionate continuation exists, return partial or unavailable evidence, the unmet condition, and the smallest viable next action. Do not relax the obligation or claim Human acceptance.

## Authority and Task Continuity

Use the Task's existing goals, criteria, authority, and evidence. Return findings and remaining obligations to the Task owner; this Skill requires no separate Task or evidence document. Human intent, preference, permission, material trade-offs, and acceptance remain Human authority; this Skill supplies no write, delegation, external-effect, or acceptance authority. Other Skills are optional guidance; this directory remains actionable when they are absent.
