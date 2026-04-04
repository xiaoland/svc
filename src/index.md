# Sustainable Vibe Coding Framework v9.4

> Version: v9.4
> Last edit on: 2026-04-04T14:51+08:00

Sustainable Vibe Coding exists to make AI-assisted software development maintainable for a small team or a one-person company.

The framework is not a document-heavy process system. It is a selective memory system for preserving truths that are expensive to rediscover and risky to lose. 

The framework is intentionally small:

- PRD remains the single source of truth for product intent
- Code and tests remain the single source of implementation truth
- TDD-style docs exist only where code and tests are not enough
- Tasks absorb volatility instead of polluting durable docs

Its core job is to help humans and agents answer:

- what the product must be and why  
- what technical truths must remain stable across iterations  
- what local complexities are dangerous enough to deserve explicit design memory  
- what runtime truths matter operationally  
- how to align at the correct level of granularity when natural language alone is not enough  
- what should stay ephemeral in tasks rather than being promoted into durable docs  
- how agents should dynamically navigate ambiguity without falling into rigid waterfall processes or chaotic guesswork

The framework should remain as small as possible. Every durable document must justify its existence.

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
- how agents should dynamically navigate ambiguity without rigid waterfall behavior
- how to colocate complexity-dissolving memory as close to target code as possible
- how to isolate architectural structure (slow-moving) from tactical hazards (fast-moving)
- how to dynamically load mutually exclusive workflows without bloating context windows

### Core Principles

- PRD is the SSoT for product what and why: PRD is pressure-driven and follows one-way derivation from drivers to behavior to derived domain structure. Domain structure cannot push obligations upstream, and PRD does not own implementation structure.
- Code, tests, and guardrails are the SSoT for implementation truth: implementation truth should live in code, tests, type systems, lint rules, CI checks, and runtime assertions.
- TDD exists only where code alone is not enough: technical design docs are not mandatory ceremony. They exist only when code and tests cannot cheaply preserve or communicate critical truths.
- Tasks absorb volatility: exploration, temporary reasoning, and unstable decisions belong in tasks.
- Docs are for expensive unknowns: A durable doc should exist only when future humans or agents would otherwise make costly mistakes.
- Do not build a second software system out of docs: documentation is support structure, not a parallel runtime.
- Alignment docs are coordination artifacts, not a new truth layer: an alignment pack may be justified when drift repeats due to references, naming, or granularity mismatch.
- Use medium-native address systems: different project media need different maps (for example frontend and backend).
- Pacing Layers for architecture: slow-moving logical boundaries must be decoupled from fast-moving physical code directories.
- Progressive disclosure: dynamically loads by context.

## Layer Model

1. Meta Engine Layer (00-meta/): dynamic skills, SOPs, and MECE workflow protocols
2. PRD Layer (10-prd/): product what and why
3. Alignment Substrate (15-alignment/): optional pressure-driven coordination support
4. Product TDD Layer (20-product-tdd/): cross-unit technical truth and global topology
5. Unit TDD Layer (30-unit-tdd/): logical structural design independent of src folder movement
6. Local Context Layer (Local AGENTS.md): tactical hazards tied to exact code areas
7. Deployment Layer (40-deployment/): runtime and operations truths
8. Task Layer (tasks/): volatile work and temporary reasoning

> Product truth and implementation truth remain separate by design.
> Unit TDD and Local AGENTS are complementary, not substitutes. (separates Logical Unit Architecture from Physical Local Context so refactoring does not erase macro design memory.)

### Pacing Layers Map

| Layer | Evolution Speed | Scope | Ownership | Typical Storage |
| --- | --- | --- | --- | --- |
| Structure | Slow | Logical architecture of a unit | Unit TDD | docs/30-unit-tdd/ |
| Stuff | Fast | Local tactical code hazards | Local AGENTS | src/**/AGENTS.md |
| Product Intent | Medium | User-facing what and why | PRD | docs/10-prd/ |
| Cross-unit Design | Medium | Contracts and topology | Product TDD | docs/20-product-tdd/ |
| Runtime Ops | Event-driven | Telemetry and runbooks | Deployment | docs/40-deployment/ |
| Volatile Work | Fastest | Exploration and diagnostics | Tasks | tasks/ |

Rule of thumb:

- If truth should survive directory refactors, put it in Structure.
- If truth protects a fragile local seam, keep it near code in Stuff.

## Section Index

- [Minimal Filesystem](sections/filesystem.md)
- [Meta Engine](sections/meta-engine.md)
- [Alignment Pack](sections/alignment.md)
- [PRD](sections/prd.md)
- [Product TDD](sections/product-tdd.md)
- [Unit TDD and Local Context](sections/unit-tdd.md)
- [Deployment](sections/deployment.md)
- [Tasks](sections/tasks.md)
- [Promotion Rules](sections/promotion-rules.md)
- [Migration Guidance](sections/migration-guidance.md)

## Anti-patterns

- Using docs to compensate for missing tests: if correctness can be guarded mechanically, prefer that.
- Creating doc families before pain exists: start minimal and grow on evidence.
- Documenting known-knowns: do not store facts that are easier to read directly from code.
- Turning root AGENTS into constitutional law: keep root AGENTS as dispatcher. Use 00-meta for dynamic protocol loading.
- Violating MECE in meta modes: do not create overlapping mode protocols that confuse decision-making.
- Bypassing the Task Layer: do not update PRD or code from vague prompts without opening a temporary task space first.
