---
name: svc-workflow
description: "Human–Agent collaboration workflows and methods for software exploration, design, planning, implementation, and delivery. Read and use for every non-trivial Task."
metadata: {"version": "17.0.0"}
---

# Software Workflow and Methods

Read and use this entry for every non-trivial Task. Guide software work from the Human's intended outcome, within the collaboration agreement and authority for the current result.

Recover the current Task's goal, decisions and reasons, evidence, authority, and pending work from its Packet. Discover `svc-task-packet` for state guidance.

## Work from a Current Judgment

Apply these actions throughout the work at the depth its consequences need. Reuse a fitting explanation for routine changes; develop the affected judgment for changed behavior, ownership, or meaning before committing dependent work.

1. **Frame the work.** Reconstruct the intended use or inquiry purpose and what is missing. Treat suggested means and existing code as candidates, retaining explicit Human constraints. Connect related requests into a coherent result; find the choice whose different answers would change the others. Use that choice to set scope and order before decomposing edits.
2. **Explain the necessary relations.** Follow an important operation through its result and subsequent use or recovery. Identify what should change together and what should remain independent. Derive meanings, identities, lifetimes, and responsibilities from these relations. Explain who makes each promise hold, including consumers beyond the edited path.
3. **Choose by consequences.** Compare credible routes through that use and a likely important change. Account for user effort, failure, transition, and which owners must understand or change together. Before adding a mechanism, guarantee, check, or question, weigh its expected value (trigger frequency × loss × the weight the project's stage gives that loss) against its certain cost, including Human attention and machine time; a failure you can construct is a possibility, not a frequency. Make near-zero-downside improvements directly; accept high cost for high return. Recommend when the basis is sufficient for the current decision. Investigate unknowns that could change it; use an authorized reversible increment when actual use can resolve a provisional premise.
4. **Challenge and revise.** Return to the problem definition, layer, and owner before the next edit when a fix fails, a problem recurs, the Human says the result is still wrong or only patched, or the request concerns an audit, maintainability, root cause, or several fixes at once. Before returning a consequential result, walk one credible change through the largest premise you left unquestioned; passing local checks share that premise. For a consequential design, audit, or root-cause result, where the host allows another Agent, also ask one in a fresh context to identify the layer and owner where the problem originates from the Human's original request and the sources, without your conclusion; reconcile any difference before returning. A mismatch, better explanation, or growing coordination also prompts reconsideration. Check the observation; distinguish a local defect, unsuitable mechanism or responsibility, and inadequate problem framing. Repair or reselect accordingly, propagate the revision, and withdraw arrangements that lost their basis while preserving valid work.

Keep decisive reasons where later work needs them.

## Default: Staged Collaboration

Use staged collaboration by default. Follow an applicable project or Task agreement or direct Human instruction selecting another rhythm, such as [Iterative Collaboration](references/iterative-collaboration.md).

| Stage | Review result |
| --- | --- |
| Product requirements design | Proposed user goals, behavior, scope, and material Product choices. |
| Technical solution design | A coherent realization and transition grounded in agreed requirements and verified facts. |
| Acceptance design | Claims, conditions, observations, and judgment rules for the agreed result. |
| Implementation preparation | An executable implementation plan with useful increments, dependencies, and route-deciding questions resolved for its scope. |
| Realize with feedback | The authorized change, local behavior evidence, and repaired defects. |
| Verify and deliver | A usable result, evidence for the agreed scope, and material residual. |

Resume at the earliest unmet stage, reusing valid decisions and explicit authorization. For a new capability with Product choices still open, begin with Product requirements design. Develop the current review result within existing authority.

Advance when Human authorization covers the next stage and its effects, honoring agreed review points. Reuse explicit authorization already covering several stages or effects. Interpret each reply's scope: a proposal decision, stage progression, or effect permission. When further work awaits authorization, return the ready stage result and preserve pending work. Read [Staged Collaboration details](references/staged-collaboration.md) when feedback is ambiguous or the proposal discussion needs guidance.

The Human owns goals, preferences, permissions, material trade-offs, and acceptance. Use project or Task agreements and direct Human instructions as the authority for changes, commits, delegation, and external effects. Check factual claims and consequences relevant to those effects.

## Read for the Next Result

Choose guidance by the next result needed. Read directly, apply its result, and continue the work. These methods extend the shared judgment and can alternate within any collaboration stage.

| Next result needed | Guidance |
| --- | --- |
| Facts, useful directions, or an explanation of observed behavior | [Explore](references/explore.md) |
| A problem framing, relation, route comparison, or reselection, including after a failed fix or for an audit, maintainability, or root-cause request | [Form and Revise Judgments](references/judgment.md) |
| Alternatives and a concrete comparison of arrangements | [Design](references/design.md) |
| Proposed user behavior, interaction, and recovery | [Product Design](references/product-design.md) |
| Visual authority, direction, and craft of a user-visible interface | [UI Design](references/ui-design.md) |
| Proposed responsibilities, information, interfaces, and transition | [Technical Design](references/technical-design.md) |
| Useful increments, dependencies, and an executable order | [Planning](references/planning.md) |
| An authorized change and behavior feedback | [Implementation](references/implementation.md) |

Product and Technical views are direct routes; general Design adds construction and comparison techniques. Read guidance and targeted source observations in separate, bounded results; recover missing content after truncation.

Discover `svc-verification` for Acceptance design, criteria, observations, and evidence judgment; `svc-taste` for consequential trade-offs left open by facts; `svc-specs` for durable knowledge ownership; and `svc-agent-collaboration` for other Agents' work and result adoption.

## Complete and Return

The default end of an authorized request is its complete requested outcome. Propose phasing only for a stated cost, dependency, or risk, as a choice for the Human. A follow-up question or added request extends the active goal: answer or do it, then continue the goal. Do remaining authorized work instead of listing it; report as remaining only what needs a Human decision or is blocked.

Complete feasible, authorized work before returning the current result as ready. Increments, Slices, and method results feed the ongoing work; they are not return points to the Human. Return to the Human at an agreed review point, when continuing needs a Human decision, input, or authorization, when a blocker prevents progress, or at the boundary of an agreed iterative rhythm. Judge conformance and fitness using observations that can distinguish the promised result from a plausible wrong one. Verify proportionately: each claim at its owning layer during the work, and the key user path with its visible result once before delivery. Lead the report with the result and any Human decision needed, then decisive reasons and evidence; include residual only when it changes use or that decision. Provide an experience entry when Human perception matters. Take harmless, reversible, or agreed actions without asking; pair any question with a recommendation.

Close when the agreed result and remaining obligations are addressed. Investigation and proposal Tasks can end with their requested return. For remaining material gaps, report the supported result, unmet condition, consequence, and smallest next action. Continue independent authorized work while a Human decision is pending.
