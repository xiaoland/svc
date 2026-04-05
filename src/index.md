# Sustainable Vibe Coding Framework v9.5

> Version: v9.5
> Last edit on: 2026-04-04T21:43+08:00

Sustainable Vibe Coding exists to make AI-assisted software development maintainable for a small team or a one-person company.

The framework is not a document-heavy process system. It is a selective memory system for preserving truths that are expensive to rediscover and risky to lose.

The framework stays intentionally small:

- Root AGENTS classifies the perturbation before acting.
- PRD remains the single source of truth for product intent and observable behavior.
- Code and tests remain the single source of implementation truth.
- TDD-style docs exist only where code and tests are not enough.
- Tasks absorb volatility, but non-trivial work still carries minimal guardrails.
- Concepts load progressively: cheat sheet first, full dictionary only on demand.
- Mode Dispatch is reusable SOP overlays rather than the only dispatcher.

Its core job is to help humans and agents answer:

- what the product must be and why
- what technical truths must remain stable across iterations
- what local complexities are dangerous enough to deserve explicit design memory
- what runtime truths matter operationally
- how to align at the correct level of granularity when natural language alone is not enough
- what should stay ephemeral in tasks rather than being promoted into durable docs
- how to classify incoming work before choosing a document owner or mutation path
- how to explore ambiguous work without drifting away from core guardrails
- how to keep core ontology available without bloating the context window
- how to switch mind-patterns during a task without confusing durable ownership

## Purpose and Core Principles

### Purpose

Sustainable Vibe Coding exists to make AI-assisted software development maintainable for a small team or a one-person company.

It is not a document-heavy process system. It is a selective memory system for preserving truths that are expensive to rediscover and risky to lose.

Its core job is to help humans and agents answer:

- what the product must be and why
- what technical truths must remain stable across iterations
- what local complexities are dangerous enough to deserve explicit design memory
- what runtime truths matter operationally
- how to align at the correct level of granularity when natural language alone is not enough
- what should stay ephemeral in tasks rather than being promoted into durable docs
- how to route work by input type before choosing the current SOP
- how to keep exploration bounded without killing creativity
- how to colocate complexity-dissolving memory as close to target code as possible
- how to isolate architectural structure (slow-moving) from tactical hazards (fast-moving)
- how to load only the concepts and protocols needed for the current step

### Core Principles

- Typed input taxonomy comes first: before changing docs or code, classify the perturbation as Intent, Constraint, Reality, or Artifact so blast radius and durable owner are explicit.
- Mode Dispatch is a mind-pattern layer: Explore, Solidify, Execute, and Diagnose are still valid SOPs, but they are not a one-task-one-mode pipeline.
- PRD is the SSoT for product what and why: PRD is pressure-driven and follows one-way derivation from drivers to behavior to derived domain structure. Domain structure cannot push obligations upstream, and PRD does not own implementation structure.
- Code, tests, and guardrails are the SSoT for implementation truth: implementation truth should live in code, tests, type systems, lint rules, CI checks, and runtime assertions.
- TDD exists only where code alone is not enough: technical design docs are not mandatory ceremony. They exist only when code and tests cannot cheaply preserve or communicate critical truths.
- Tasks absorb volatility with MVT anchors: every non-trivial task carries Objective & Hypothesis, Guardrails Touched, and Verification so exploration stays lightweight but grounded.
- Progressive ontology beats full-context dumping: keep only a cheat sheet in root AGENTS and load `00-meta/concepts.md` only when classification or boundary language becomes ambiguous.
- Docs are for expensive unknowns: a durable doc should exist only when future humans or agents would otherwise make costly mistakes.
- Do not build a second software system out of docs: documentation is support structure, not a parallel runtime.
- Alignment docs are coordination artifacts, not a new truth layer: an alignment pack may be justified when drift repeats due to references, naming, or granularity mismatch.
- Pacing layers protect clarity: slow logical boundaries must be decoupled from fast physical code directories.

## Front-Door Execution Loop

1. Classify the incoming perturbation as Intent, Constraint, Reality, or Artifact.
2. Identify the owning layer and blast radius before choosing how to work.
3. For non-trivial work, open a task packet with the three MVT anchors.
4. Select the current mode overlay: Explore, Solidify, Execute, or Diagnose. Revisit modes as the task evolves.
5. Load only the governing anchors needed for this route and mode: PRD, Product TDD, Unit TDD, local AGENTS, deployment runbooks, glossary, concepts, and the relevant SOP.
6. Make changes only inside the owning layer for that truth.
7. Promote new knowledge only when it passes the promotion test.

## Layer Model

1. Meta Engine Layer (00-meta/): typed dispatcher protocols, mode SOPs, on-demand concepts, and minimal route-specific scaffolds
2. PRD Layer (10-prd/): product what, why, observable behavior, and business glossary
3. Alignment Substrate (15-alignment/): optional pressure-driven coordination support
4. Product TDD Layer (20-product-tdd/): cross-unit technical truth and global topology
5. Unit TDD Layer (30-unit-tdd/): logical structural design independent of src folder movement
6. Local Context Layer (Local AGENTS.md): tactical hazards and recurrence tripwires tied to exact code areas
7. Deployment Layer (40-deployment/): runtime and operations truths
8. Task Layer (tasks/): volatile work, diagnosis, artifacts, and temporary reasoning

> Product truth and implementation truth remain separate by design.
> Unit TDD and Local AGENTS are complementary, not substitutes.
> Input type decides ownership; mode decides the current working posture.

### Pacing Layers Map

| Layer | Evolution Speed | Scope | Ownership | Typical Storage |
| --- | --- | --- | --- | --- |
| Structure | Slow | Logical architecture of a unit | Unit TDD | docs/30-unit-tdd/ |
| Stuff | Fast | Local tactical code hazards and tripwires | Local AGENTS | src/**/AGENTS.md |
| Product Intent | Medium | User-facing what and why | PRD | docs/10-prd/ |
| Cross-unit Design | Medium | Contracts and topology | Product TDD | docs/20-product-tdd/ |
| Runtime Ops | Event-driven | Telemetry and runbooks | Deployment | docs/40-deployment/ |
| Volatile Work | Fastest | Exploration, diagnosis, and transient artifacts | Tasks | tasks/ |

Rule of thumb:

- If truth should survive directory refactors, put it in Structure.
- If truth protects a fragile local seam, keep it near code in Stuff.
- If truth is still exploratory, keep it in Tasks until stability is proven.
- If ownership is unclear, do not let mode selection hide that ambiguity; resolve the route first.

## Section Index

1. [Minimal Filesystem](sections/filesystem.md)
2. [Typed Taxonomy and Mode Engine](sections/meta-engine.md)
3. [Progressive Ontology](sections/ontology.md)
4. [PRD](sections/prd.md)
5. [Alignment Pack](sections/alignment.md)
6. [Product TDD](sections/product-tdd.md)
7. [Unit TDD and Local Context](sections/unit-tdd.md)
8. [Deployment](sections/deployment.md)
9. [Tasks](sections/tasks.md)
10. [Promotion Rules](sections/promotion-rules.md)

## Anti-patterns

- Routing work by ambiguity alone: do not skip typed input classification and jump straight to a mode.
- Treating modes as durable owners: Explore or Diagnose never decides whether truth belongs in PRD, TDD, Deployment, or Tasks.
- Assuming one task equals one mode: a single task may loop between Explore, Solidify, Execute, and Diagnose.
- Task packets without verification: exploration without an executable completion proof invites hallucinated done-ness.
- Loading the full ontology by default: keep root AGENTS tiny and read `00-meta/concepts.md` only when needed.
- Mixing framework ontology with business language: keep framework terms in meta docs and business terms in `10-prd/glossary.md`.
- Using docs to compensate for missing tests: if correctness can be guarded mechanically, prefer that.
- Creating doc families before pain exists: start minimal and grow on evidence.
- Documenting known-knowns: do not store facts that are easier to read directly from code.
- Bypassing the task layer: do not update PRD or code from vague prompts without a bounded task packet.
- Fixing bugs without evidence: Reality work stays read-first until root cause is justified.

## Other
- [Migration Guidance](sections/migration-guidance.md)