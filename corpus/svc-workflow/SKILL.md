---
name: svc-workflow
description: "Organize software work with a Human and carry it through useful decisions, authorized changes, and product-relevant feedback. Use when choosing a collaboration approach; when investigation, requirements, design, planning, or implementation need reasoning; when feedback, changed premises, or incomplete evidence require a new route."
metadata: {"version": "15.0.0"}
---

# Software Work with a Human

Software work connects a Human's purpose to engineering action and a product result. A method can solve a local problem without establishing when to propose a direction, what has been committed, what action is authorized, or how new feedback changes the work. This workflow keeps those relationships explicit so the Human can control direction and consequential tradeoffs while the Agent takes responsibility for engineering progress and supported conclusions.

Recover the intended benefit behind the Human's wording. Distinguish a goal, preference, proposal, factual claim, and authorization: an example may point to a broader concept, and a list may not be an exhaustive requirement or a prescribed structure. Product intent, preference, permission, consequential tradeoffs, and acceptance remain Human authority. Factual, causal, technical, feasibility, and proposed-solution claims remain challengeable through evidence and reasoning; agreement or confidence does not settle them.

Begin by recovering the desired result, latest feedback and decisions, current commitment and authorization, actual state, and what prevents the next useful action. Continue ordinary investigation, engineering decisions, repair, and verification within existing authority. For an obvious authoritative query or mechanical action, act directly. Before durable mutation, establish its authorized effect, affected owners and consumers, relevant invariants, and proportionate feedback. This Skill and either collaboration approach grant no write, commit, delegation, external-effect, or acceptance permission. Do not ask again for authority already given, and do not infer new authority from feedback or silence.

## Connect Commitments and Feedback

Use the project's agreement and the Human's direct instruction to determine how collaboration proceeds. In staged collaboration, converge the current stage's goal, scope, important solution choices, and judgment basis before proceeding under its confirmed commitment. In iterative collaboration, revise the current scope and route continuously within the shared goal and authorization; beginning implementation does not freeze the requirements. Both require coherent decisions and useful evidence, can revisit design locally, and can deliver investigation or a proposal without changing source.

When the mode is clear, continue it without repeatedly selecting or loading both references. Read [Staged Collaboration](references/staged-collaboration.md) when stage commitments, reviewable proposals, or reopening an agreed premise need guidance. Read [Iterative Collaboration](references/iterative-collaboration.md) when experience feedback and evolving product choices need to shape the next increment. If the distinction would change the next consequential action and no agreement resolves it, explain the recommended approach and its consequence, then obtain the missing decision. Continue independent work permitted by either approach meanwhile; do not assume an unconfirmed change was accepted.

New feedback can reveal a defect in already agreed behavior, an invalid observation, an uncertain product choice, or a change in the promise itself. Repair an established behavioral defect within existing authorization instead of reopening the product decision merely because the report came from the Human. When feedback invalidates a material premise, stop only work depending on that premise, identify the affected commitment, and propose the needed revision. Continue independent authorized work. A user suggestion is input to interpret and evaluate, not automatically a new requirement or permission.

## Use the Method That Resolves the Current Gap

Collaboration approaches govern commitment and feedback; methods supply local reasoning, with specialist V&V guidance owned by `svc-verification`; the Task Packet preserves recoverable state. They are not a fixed phase sequence or new runtime states. Methods compose recursively: implementation can expose a design contradiction, design can require investigation, and verification can change a requirement or the next implementation route. Read only what can change the current action or return.

| Method | Use when | Useful return |
| --- | --- | --- |
| [Explore](references/explore.md) | A relevant answer or way to obtain it is non-obvious. | Supported information enabling the next decision, with material unknowns. |
| [Design](references/design.md) | Product or technical choices do not yet form a coherent solution. | A proposal the current consumer can use without silently deciding a material requirement. |
| [Planning](references/planning.md) | The next work, dependencies, or point for reconsideration are unclear. | A limited, executable route with reasons for ordering and feedback that may change it. |
| [Implementation](references/implementation.md) | An authorized intended change needs to become real. | The actual changed state, useful feedback, achieved scope, and residual. |
| Verification and Validation (`svc-verification`) | Criteria, evidence, or feedback need specialist reasoning. | Additional guidance for a supported or contradicted claim, its conditions and assumptions, and what remains unestablished. |

Product purpose, behavior requirement, observation, and judgment rule (oracle) must remain connected. Verification asks whether behavior conforms to the owned requirements; validation asks whether those requirements and the result serve the intended use. The oracle must reject requirement-relevant violations while continuing to accept implementation changes that preserve all relevant requirements. A precise, automated, repeatable check can still encode the wrong promise, and checks sharing the same interpretation are not independent confirmation. This minimum responsibility applies during design, implementation, and result judgment, not just at a final test stage. The independent `svc-verification` Skill owns detailed V&V methods; discover its installed entry by name through the host when specialist reasoning is needed. Without it, retain the responsibilities here, use applicable project mechanisms, and state an actual criterion, observation, or capability gap rather than relaxing the obligation.

## Return Supported Progress and Preserve Obligations

Complete the authorized and feasible work needed for the agreed result, including feedback the Agent can obtain, before returning. Do not transfer all product verification to the Human; offer a useful experience entry when their preference or perception matters. Distinguish actual effects, observed behavior, conclusions supported by evidence, and Human acceptance. Passing a check or completing a stage does not establish the entire product outcome or discharge remaining obligations.

When no feasible, authorized, proportionate continuation can resolve a material gap, return supported progress, the unmet condition and consequence, and the smallest viable decision or action. Preserve unknowns instead of declaring success or acceptance. If Human acceptance is unavailable, deliver the usable state and existing evidence, mark what still requires it, and continue independent authorized work rather than freezing everything.

For every non-trivial task, recover the existing Task Packet or create the smallest `packet.md` at the project's authorized task location. Keep the objective, decisions and authorization, current facts and owners, next action, and completion evidence sufficient to resume. An invocation or assignment does not create a competing task or Packet. Planning here determines and revises the route; persistent plan structure and task closure remain with the Packet. Preserve durable project truth at its actual owner, preferring source, configuration, schema, assertions, or automation for facts they enforce directly.

When available, discover `svc-task-packet` for persistent task state, `svc-specs` for durable knowledge, `svc-taste` for consequential product or implementation judgment, or `svc-agent-collaboration` for arranging work across Agents and adopting their results through the host's Skill interface. These are optional sources of additional guidance, not installation dependencies. Continue with the responsibilities here and qualified project mechanisms when absent; report a real capability or authority gap without relaxing the obligation.
