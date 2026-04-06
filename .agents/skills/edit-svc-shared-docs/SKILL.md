---
name: edit-svc-shared-docs
description: 'Safely update Hub-owned SVC docs from a Spoke repo that mounts `docs/_shared/` through git submodule or an equivalent shared mount. Use when you need to avoid corrupting the mounted shared docs, capture local code pressure, decide shared vs local ownership, edit the Hub source first, and bump the shared ref second.'
argument-hint: 'shared gap + local seam + why the Hub truth must change'
---

# Edit SVC Shared Docs

## Skill Contract
- Lower the operational complexity of git submodule-backed shared docs.
- Protect mounted shared docs from unsafe in-place edits in a Spoke repo.
- Preserve source-first mutation for shared docs.
- Preserve Spoke-side code pain before switching away from local execution.
- Keep Product TDD and Unit TDD boundaries sharp in multi-repo setups.
- Keep shared truth singular; do not fork Hub truth into Spoke-local docs.

## Non-negotiable Rule: Self-contained References
1. Do not rely on `src/` during skill execution.
2. Use only local copies in this skill folder:
  - `./resources`
  - `./assets`
3. If the needed rule is missing here, confirm before expanding the skill.

## When to Use
- A Spoke task discovers that `docs/_shared/` is missing or contradicting a shared rule.
- The repo mounts shared docs through git submodule and the next step feels Git-fragile or easy to get wrong.
- You need to decide whether a technical truth belongs in Hub `20-product-tdd/` or Spoke `30-unit-tdd/`.
- You need a safe workflow for updating shared SVC docs and then bumping the Spoke ref.
- You need to review whether a proposed shared-doc change is actually local and should stay out of the Hub.

## Do Not Use
- The repo has no `docs/_shared/` mount or no equivalent shared-doc mount at all.
- The change is purely local to one unit and no other unit relies on it.
- The task is ordinary local coding with no shared-doc gap.
- You are already working directly in the Hub source repo and do not need Spoke-side safety rails.

## Required Inputs
Collect these first. If missing, ask concise follow-up questions.
1. Current repo role: Hub or Spoke.
2. Target path or missing rule.
3. Local seam that exposed the gap.
4. Whether another unit must rely on this truth to interoperate safely.
5. Whether `docs/_shared/` is clean and safe enough to inspect.
6. Verification pressure after the shared change lands.

## Preflight
Run this before touching any shared-doc path.

1. Confirm the repo is acting as a Spoke, not ordinary mono-repo.
2. Confirm `docs/_shared/` exists and is the intended shared mount.
3. Confirm the mount is clean enough to inspect and not being treated as ordinary local docs.
4. Confirm this is truly a shared-truth problem rather than a one-unit local design issue.
5. If any check fails, stop and resolve it before editing anything shared.

## Quick Ownership Gate
Use this before editing any durable doc.

Promote to shared Product TDD only when both are true:
1. another unit must rely on it to interoperate safely
2. changing it would break cross-unit compatibility, authority, or topology

Keep it local when one unit can change it without forcing another unit to update.

Minimal examples:
- payload format between two services -> Product TDD
- one service's internal DB table naming -> Unit TDD or local `AGENTS.md`

## Workflow

### A. Capture Local Pressure First
Apply this whenever a Spoke task discovers a shared-doc gap during execution.

1. Stop ordinary local execution.
2. Record the local pressure in the active task packet.
3. Capture at least:
  - local code path or seam
  - missing shared rule or ambiguity
  - local consequence if unresolved
  - verification pressure after return
4. Use `./assets/task-packet.template.md` and `./assets/edit-shared-docs.template.md` if you need structure.

### B. Decide Shared vs Local Destination
1. Use the quick ownership gate above.
2. Re-check `./resources/product-tdd.md` and `./resources/unit-tdd.md` if the boundary is unclear.
3. Do not centralize one-unit internals into shared docs just because they were painful locally.

### C. Update Shared Truth Source-First
Apply this when the truth is truly shared.

1. In a Spoke, treat `docs/_shared/` as read-only during ordinary local work.
2. Do not treat the mounted submodule worktree as a normal local docs folder.
3. Prefer editing in the Hub source repo directly; if you must act from the mount, make the Git state explicit before any edit.
4. Pause for human authorization before any shared-doc commit or push.
5. Commit and push the Hub change first.
6. Bump the Spoke shared ref as a separate, auditable change.
7. Return to the captured local task and finish the local work.

### D. Resume Local Execute
1. Reload the shared truth from the updated ref.
2. Resume the exact local task that captured the pressure.
3. Verify the local change against the recorded pressure, not against memory alone.

## Hard Rules
- Never mix Hub doc edits, Spoke ref bumps, and Spoke-local code in the same commit.
- Never edit shared truth in place inside `docs/_shared/` as if it were ordinary local docs.
- Never assume the mounted shared-doc worktree is safe to commit from without checking its Git state first.
- Never promote a one-unit internal naming or storage rule into Hub `20-product-tdd/` unless it is itself the cross-unit contract.
- Never leave the Spoke without capturing the local seam that justified the shared change.

## Local References
- [Typed taxonomy and cross-repo protocol](./resources/meta-engine.md)
- [Optional multi-repo extension](./resources/multi-repo.md)
- [Product TDD guidance](./resources/product-tdd.md)
- [Unit TDD guidance](./resources/unit-tdd.md)
- [Task routing and local-pressure capture](./resources/tasks.md)
- [Durable destination map](./resources/durable-destination-map.md)

## Local Assets
- [Task packet template](./assets/task-packet.template.md)
- [Product TDD file set template](./assets/product-tdd-file-set.template.md)
- [Mode B solidify template](./assets/mode-b-solidify.template.md)
- [Mode C execute template](./assets/mode-c-execute.template.md)
- [Shared docs edit protocol template](./assets/edit-shared-docs.template.md)

## Example Prompts
- /edit-svc-shared-docs I am in a Spoke repo. This payload shape is shared across two services and `docs/_shared/20-product-tdd/` is missing it.
- /edit-svc-shared-docs I found a missing PRD invariant while coding locally. Help me capture the local seam first, then update shared truth safely.
- /edit-svc-shared-docs Decide whether this rule belongs in Product TDD or Unit TDD before I edit docs.
