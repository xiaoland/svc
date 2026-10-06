# Framework Migrations

Use these living guides when a Consumer project adopts a newer SVC framework release. Version 15 remains the compatibility anchor for the retained release chain; there is no adoption chain from pre-v15 baselines. An Agent and Human evaluate and update Consumer-owned truth before adoption; SVC never rewrites or claims to have verified those documents.

Capability-named guides describe a semantic transition. The framework now has six Skill entries and an independent source version; CLI installation and current-only CLI configuration contracts are not owned here.

Current guides:

- [Agent collaboration](agent-collaboration.md): replace the `svc-sub-agents` address and role-based guidance with collaboration across execution forms, including installation and adoption changes.
- [Six Agent Skills](agent-skills.md): replace concept-directory and CLI-mediated navigation, replace Methods with Workflow while retaining independent V&V, and align draft installations while preserving task and authority obligations.
- [Coding Agent debugger and profiler evidence](analysis-debugger-corpus.md): adopt the current evidence and analysis contracts when exporting or consuming that evidence.

Version classification follows Consumer behavior:

- **major** changes an obligation, default, authority or permission boundary, Task Packet semantic, Consumer layout, or supported framework address
- **minor** adds a backward-compatible optional capability
- **patch** restores or clarifies the existing contract

Every release-relevant change has a Towncrier fragment. Migration guides and the root `[tool.svc.corpus].version` setting are authored framework sources, independent of CLI release notes.
