# Alignment Substrate

## 6.1 Role

Alignment exists only when collaboration repeatedly fails because humans and agents are not sharing the same referential system at the right granularity.

The substrate is not a new truth layer. It is an invariant coordination grammar that helps compile fuzzy intent into low-entropy engineering actions.

## 6.2 Admission Rule

Create `15-alignment/` only when one or more of these drift patterns repeat:

- references or visual names are unstable
- object boundaries are interpreted differently
- operation verbs hide different side effects
- state or context changes whether a reference is valid
- agents keep proposing fixes without evidence or without a credible blast-radius estimate

If code, tests, or existing TDD docs already preserve the truth cheaply, do not add alignment docs.

## 6.3 What It Owns

- shared object and address conventions for coordination
- calculable surface maps derived from stable anchors
- controlled operation vocabulary bound to verification contracts
- request structures that make boundary, state/context, evidence, and protocol explicit before risky mutation
- change request templates for alignment-heavy work

It does not own product why, business rules, framework ontology, business glossary, runtime topology, durable invariants themselves, evidence sources, or reusable execution SOPs.

## 6.4 Coordination Primitives

The substrate becomes actionable only when the following seven primitives are explicit enough to verify:

1. Object: what kind of thing is being discussed
2. Address: where that thing is located in code or on a surface
3. Operation: what state transition is intended
4. Boundary and Invariants: what must not change
5. State / Context: when the reference and mutation are valid
6. Evidence: what objective proof justifies the mutation
7. Protocol: how human and agent confirm shared understanding before execution

A request is substrate-complete only when all seven are specific enough to constrain action, verification, and blast radius.

The substrate owns the need to make these primitives explicit, not the durable truth behind each one. Invariants stay owned by PRD, TDD, or local `AGENTS.md`; evidence stays in `tasks/`, tests, logs, or deployment docs; reusable protocol rules stay in `00-meta/`.

## 6.5 Core Engineering Rules

### Calculable Maps over Static Maps

Do not rely on hand-maintained screenshots, architecture drawings, or static UI trees as the main coordination surface.

Prefer stable anchors that let the current topology be computed from code and structure, for example semantic ids, route names, `data-region`, `data-block`, typed handles, or AST-addressable symbols.

### Declarative Desired State over Mixed Instructions

Keep object, operation, and constraints separate.

Express the intended mutation as a state diff:

- From: objective description of the current behavior or structure
- To: objective description of the desired behavior or structure

The agent's job is to reconcile that diff without smuggling in unrelated changes.

### Verbs as Verification Contracts

Operation words should be admitted only when they imply a verification contract.

Examples:

- `refactor` implies observable behavior stays equivalent
- `extract` implies topology changes without breaking callers and introduces a new verification seam

If a verb does not add a verification boundary, it is too weak for durable alignment.

## 6.6 Asymmetric Execution

Execution is intentionally asymmetric:

- humans may provide directional, partially implicit intent
- agents must deserialize that intent into substrate fields before boundary-crossing mutation

The reusable pre-execution Impact Handshake is the protocol consequence of this rule. Its trigger and pause behavior belong in `00-meta/`, not in alignment itself.

## 6.7 Stable Anchor Rule

The stable-anchor rule applies when natural-language references are not sufficient for frequently edited surfaces.

If a surface is edited frequently and natural language is insufficient, add stable semantic anchors that can be derived from code rather than positional descriptions.

## Related Assets

- [Alignment Substrate Request Template](../assets/templates/alignment-change-request.template.md)
