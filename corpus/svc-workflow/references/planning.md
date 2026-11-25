# Planning

Use this Workflow method to develop or update useful increments and an executable order. Carry the intended result, selected route, and judgment basis into the sequence; use the shared judgment to resolve a choice before committing its dependent steps.

## Choose Useful Results

Work backward from the intended result and actual state. For a feature, choose a narrow behavior that works through its necessary layers and can be observed. One input with real persistence can be a useful slice, grouping database, API, and UI changes by the behavior they deliver. Increments order the work toward the whole authorized result; they do not reduce its scope.

Group related requests around the result and shared choices before dividing edits. A mechanical rename can be one coordinated transformation; a migration may need intermediate states. Keep parts together when they must continually correct one another, and preserve unaffected work when a choice is revised.

## Resolve and Order the Draft

Draft concrete changes with their results, prerequisites, and feedback. Derive dependencies from required inputs, state, interfaces, permissions, or guarantees. Distinguish hard prerequisites from an order chosen for easier feedback and recovery. Exercise a shared contract before spreading its assumptions through dependent consumers.

Before splitting work across parallel Tracks or owners, name each work line's primary inputs: the code regions, files, and domain context it must understand to do its work. Work lines that share most primary inputs belong in one Track; a single owner builds that understanding incrementally at lower total cost than parallel owners who each load the same context independently.

Trace each step's output into the next against relevant code, interfaces, and failure paths. Check intermediate compatibility, ownership, and recovery. Name a route-deciding question exposed by that rehearsal, resolve it through investigation or a concrete candidate, and revise the draft.

For independently deployed consumers that must coexist, a possible migration order is:

1. Readers accept both forms while writers use the old form.
2. Writers adopt the new form.
3. Existing data is migrated and observed under the intended invariant.
4. The old form is removed after accounting for remaining consumers.

Derive this from actual compatibility needs. Coordinated replacement may be cheaper when coexistence is unnecessary.

Run a preparation experiment only when its possible outcomes can change the route. State that difference and exercise the smallest boundary that distinguishes it. Before planning replacement after owner loss, for example, observe lock ownership and whether the prior work can still produce effects. Keep experimental state isolated or recoverable and feed findings into the plan.

Use paper rehearsal to check coherence and experiments to resolve the route-deciding question.

## Finish a Ready Sequence

An investigation plan can contain questions. A ready implementation plan must select its intended result, route, and judgment basis. When actual use is needed to test an upstream premise, plan an authorized, isolated or reversible learning increment with a clear question and feedback. Keep unsettled later commitments outside the ready sequence.

Arrange ready work as linearly and clearly as practical, naming external dependencies and providers and keeping useful independent work visible. Include feedback that can challenge the reasons for consequential choices. When evidence changes the framing or route, revise that judgment and its dependent steps; retain valid progress. Preserve the route, ordering reasons, and reconsideration conditions in the existing Packet; `svc-task-packet` owns its structure.
