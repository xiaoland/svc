# Explore

Use this Workflow method to learn unfamiliar facts or relations, discover possible directions, or obtain evidence distinguishing explanations. Read an obvious authoritative source directly.

## Frame the Question

Start with what you want to understand or discover. When the question is open, inspect contrasting examples, uses, or approaches; follow unexpected differences to find a useful question or opportunity. Refine the problem, terminology, and question as findings reveal what matters.

When the inquiry serves a specific decision, identify that decision and what different answers would change about the next action. Locating a handler needs less support than explaining a recurring failure across environments. Check versions, state, and observation windows when they can change the answer. Distinguish observations, interpretations, and provisional hypotheses as they guide investigation.

## Build a Useful Model

Build a model when relationships need explanation. For system behavior, follow a representative operation through relevant data and state owners to the result its consumer receives. Inspect definitions, callers, configuration, and runtime behavior where those connections need explanation.

Choose the representation for the question:

| Question | Useful representation |
| --- | --- |
| Where does a change belong? | Owners, writers, readers, affected consumers, and repeated knowledge. |
| Why does behavior change over time? | A sequence or state transition showing waiting, interruption, and commitment. |
| What explains a mismatch? | Possible mechanisms and the conditions they predict differently. |
| Which policy applies? | A decision table of relevant identities, states, and allowed transitions. |

Connect Product meaning to implementation where the question needs both. Mark observed and expected relations distinctly; preserve evidence anchors, uncertainty, and mismatches. Use the model to locate a change, explain a contrasting case, or predict an observation. Follow unexplained relations when they could improve the answer or reveal a useful direction for the inquiry.

## Generate and Separate Explanations

Distinguish missing candidates from missing evidence about existing candidates. To find alternatives, change the mechanism, boundary, or assumption behind the first idea; use a contrasting case or a different evidence source. Keep relevant candidates that are plausible under known constraints and differ in consequences. Develop a useful range of candidates covering important possibilities, then compare their consequences.

When comparing explanations, state what each predicts and choose a feasible observation whose outcomes would change the next action. After a save appears to fail, establish which state the same operation reached:

| Observation | Supported conclusion |
| --- | --- |
| A complete acceptance record for the relevant window contains no matching operation | The operation was not accepted at that boundary. |
| Acceptance is recorded, but the outcome is unresolved | Acceptance occurred; completion or failure is still unknown. |
| The durable result exists under the same operation identity | The write committed; investigate the response or display if the user still sees failure. |

A committed write can coexist with a lost reply, a stale view, or both. Inspect reply receipt and view updates if that distinction changes the repair. Repeating the write can add ambiguity or duplicate effects.

For a causal question, seek a relevant contrast with and without the symptom, then challenge the mechanism that could explain the difference. If all predictions fail, check the observation and reopen the candidate set. Seek evidence supporting the explanation you adopt. Preferences between otherwise adequate experiences need Product judgment.

## Decide Whether to Continue

Judge progress against the inquiry's purpose. A useful return may be a clearer problem, promising directions, a model, or a supported answer. For a specific decision, recommend once the available basis is adequate. Continue investigation for an uncertainty that could change the choice or a material recovery or long-term consequence; weigh another observation against its total cost.

Choose further work by what it could teach and its cost. An open inquiry can end when it has found useful questions or directions worth pursuing.

Return what was learned, why it is useful, the supporting observations or reasoning, and consequential uncertainty. If the requested result remains incomplete, name the missing condition and useful continuation. For an inquiry into recurring rework or future working practice, use [work-system learning](work-system-learning.md).
