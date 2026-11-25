---
name: svc-writing
description: "Writing and revising substantial prose for human readers, including documentation, design documents, issues, PR descriptions, and reports. Use when drafting, condensing, or reviewing such text."
metadata: {"version": "17.0.0"}
---

# Writing for Human Readers

Use this Skill when drafting or revising prose whose reader is a person: documentation, design documents, issues, PR descriptions, reports, and similar deliverables. Apply it within the consuming Task; it governs the text, not the Task's authority.

## Carry Information

Every sentence must add something the reader cannot already derive: a fact, a mechanism, a constraint, or a decision with its reason. Apply the deletion test: if removing a paragraph leaves the reader's understanding of the facts, the reasoning, the constraints, and the conclusion unchanged, remove it.

State supported conclusions and established facts directly, without ramp-up framing. Explain the cause, mechanism, or relationship behind a claim rather than narrating the writing or research process, and rather than reasserting the claim's importance. A concluding passage earns its place only when it adds something the preceding facts do not already say, such as a causal explanation, a constraint, or a testable implication.

Express evidence strength through wording — "measured", "reported by the vendor", "inferred from one incident" — instead of separate caution paragraphs. Keep qualifications that change how a fact is interpreted or whether a conclusion holds; delete repetitions of them.

## Keep the Reader's Load Even

Density is not compression. Text fails its reader when too much information concentrates in one construction, even when every sentence is individually informative.

- Make the relation between adjacent judgments explicit when the reader would otherwise have to guess whether it is cause, contrast, or addition.
- Prefer concrete subjects — the person, system, or artifact that acts — over chains of abstract nouns paired with action verbs.
- Unpack a deeply nested modifier into its own sentence before building on it.

These rules serve the same standard from the opposite side: remove what adds nothing, expand what cannot be parsed. Judge each edit by whether the reader finishes with more understanding per unit of effort.

## Authority and Task Continuity

The Human's audience, tone, and acceptance retain their authority. This Skill grants no write, delegation, external-effect, or acceptance authority. Apply it within the existing Task and return the text and unresolved choices to the Task owner. Discover `svc-workflow` by name when the surrounding work needs process guidance; other Skills are optional guidance, not prerequisites.
