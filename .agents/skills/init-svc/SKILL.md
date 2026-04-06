---
name: init-svc
description: 'Initialize or migrate Sustainable Vibe Coding (SVC) for greenfield, partial-doc, or mature-doc projects. Default output is a quick checklist. Self-contained: use local assets/resources only. Use when: init svc, apply svc, bootstrap docs, retrofit documentation, migrate to SVC.'
argument-hint: 'project state + target depth (minimal or expanded)'
---

# Init SVC

## Skill Contract
- Produce an actionable SVC initialization or migration checklist for three project states:
  - greenfield
  - partial-doc
  - mature-doc
- Keep output short and execution-focused by default.
- Provide explicit quality gates before promotion.

## Non-negotiable Rule: Self-contained References
1. Do not reference framework sources outside this skill folder during skill execution.
2. Use only local copies in this skill folder:
  - ./assets
  - ./resources
3. If required knowledge is missing in local copies, ask for confirmation before extending files.

## Default Assumptions
- Scope: workspace-level skill.
- SVC documentation root in target projects: docs.
- Output style: quick checklist (upgrade to full workflow only when requested).

## When to Use
- Starting SVC from scratch in a new project.
- Retrofitting SVC into a project with output but weak or fragmented documentation.
- Aligning a project that already has extensive docs to SVC ownership and routing rules.

## Required Inputs
Collect these first. If missing, ask concise follow-up questions.
1. Project state: greenfield, partial-doc, or mature-doc.
2. Target depth: minimal or expanded.
3. Current sources of truth: code, tests, runbooks, architecture docs.
4. Main pain points: drift, repeated incidents, handoff cost, risky changes.

## State Classification
1. Classify as A (Greenfield) when documentation baseline is near zero.
2. Classify as B (Partial Docs) when outputs exist but ownership is incomplete or mixed.
3. Classify as C (Mature Docs) when documentation is broad but has overlap or owner conflicts.

## Quick Checklist (Default Execution)
1. Classify current work as Intent, Constraint, Reality, or Artifact.
2. Identify durable owner and blast radius before changing files.
3. Choose target depth:
  - minimal: AGENTS + docs/00-meta + docs/10-prd + tasks
  - expanded: add docs/15, docs/20, docs/30, docs/40, and local AGENTS only under real pressure
4. For non-trivial tasks, require MVT anchors:
  - Objective and Hypothesis
  - Guardrails Touched
  - Verification
5. Execute the matching branch playbook (A, B, or C).
6. Promote only after quality gates pass.

## Branch Playbooks

### A. Greenfield
1. Create minimal skeleton: AGENTS, docs/00-meta, docs/10-prd, tasks.
2. Set root dispatcher behavior: typed input first, mode second.
3. Start with one task packet that includes all MVT anchors.

### B. Partial Docs
1. Inventory current assets and map each major claim to exactly one owner layer.
2. Keep unresolved or conflicting items in tasks first.
3. Promote only expensive-to-rediscover truths, not everything.

### C. Mature Docs
1. Build an equivalence map from current doc families to SVC layers.
2. Keep existing authoritative docs and add compatibility mapping before major rewrites.
3. Enforce one-way PRD derivation and remove implementation leakage from PRD.

## Quality Gates (Definition of Done)
All checks must pass:
1. Every non-trivial task has MVT anchors.
2. Every durable claim has exactly one owner.
3. PRD contains what and why, not mechanism or topology internals.
4. Reality work stays evidence-first before edits.
5. Promotion happens only after verification.
6. Target shape (minimal or expanded) is internally consistent.

## Output Format
1. State classification with evidence (A, B, or C).
2. Selected target depth (minimal or expanded).
3. Action checklist ordered by owner layer.
4. Risks and unresolved ambiguities.
5. Immediate next 1 to 3 actions.

## Upgrade to Full Workflow When
- Migration spans multiple teams or repositories.
- Owner conflicts are high and require phased governance.
- User explicitly asks for a detailed migration program.

## Local Resources (Use These Only)

### Templates in assets
- [AGENTS root template](./assets/AGENTS.root.template.md)
- [AGENTS local template](./assets/AGENTS.local.template.md)
- [Input intent template](./assets/input-intent.template.md)
- [Input constraint template](./assets/input-constraint.template.md)
- [Input reality template](./assets/input-reality.template.md)
- [Input artifact template](./assets/input-artifact.template.md)
- [Mode A explore template](./assets/mode-a-explore.template.md)
- [Mode B solidify template](./assets/mode-b-solidify.template.md)
- [Mode C execute template](./assets/mode-c-execute.template.md)
- [Mode D diagnose template](./assets/mode-d-diagnose.template.md)
- [Concepts template](./assets/concepts.template.md)
- [Task packet template](./assets/task-packet.template.md)
- [PRD file set template](./assets/prd-file-set.template.md)
- [Product TDD file set template](./assets/product-tdd-file-set.template.md)
- [Deployment runbook template](./assets/deployment-runbook.template.md)
- [Alignment change request template](./assets/alignment-change-request.template.md)
- [Task diagnostics matrix template](./assets/task-diagnostics-matrix.template.md)

### References in resources
- [SVC framework index](./resources/index.md)
- [Minimal filesystem guidance](./resources/filesystem.md)
- [Typed taxonomy and mode engine](./resources/meta-engine.md)
- [Ontology](./resources/ontology.md)
- [PRD guidance](./resources/prd.md)
- [Product TDD guidance](./resources/product-tdd.md)
- [Unit TDD guidance](./resources/unit-tdd.md)
- [Deployment guidance](./resources/deployment.md)
- [Tasks guidance](./resources/tasks.md)
- [Promotion rules](./resources/promotion-rules.md)
- [Alignment guidance](./resources/alignment.md)
- [Migration guidance](./resources/migration-guidance.md)
- [Durable destination map](./resources/durable-destination-map.md)

## Example Prompts
- /init-svc This is a greenfield project. Bootstrap minimal SVC now.
- /init-svc We have outputs but fragmented docs. Build a partial-doc migration checklist.
- /init-svc We already have mature docs. Create a low-risk SVC alignment checklist.
