# Align Agent Collaboration Guidance

Use this guide if an earlier v15 development checkout or draft installation used `svc-sub-agents`, and now needs the final `svc-agent-collaboration` entry. These layouts belong to the same unreleased v15 development line; they are not successive released versions. The old Skill address and its Explorer/Executor reference paths are removed; the new Skill is independently installable and covers delegation, independent sessions, dependency coordination, result adoption, and responsibility transfer. No old-name alias or forwarding entry remains.

## Update Working Guidance

Replace Consumer pointers and discovery instructions that name `svc-sub-agents` with the actual installed `svc-agent-collaboration/SKILL.md`. Replace direct pointers to `references/explorer.md` and `references/executor.md` with the new entry; it routes to delegation/adoption or coordination/handoff according to the current pressure. Do not mechanically rename runtime Agent roles: the Skill's address does not configure the host's available roles or tools.

Review project-owned collaboration rules that copied the old guidance. Overall task integration and Human authority remain, but a fixed Primary/Child star is no longer required: authorized dependency owners can coordinate directly, and an independent session may hold newer Human decisions. Keep coupled investigation, implementation, operation, repair, and verification with one responsible owner whose authorized effects cover the result. Ordinary progress or an intermediate delivery does not transfer responsibility.

An independent validator, complete file list, and retry budget are no longer universal prerequisites for delegation. Preserve actual project or tool authorization and effect gates. Adopt returns using observations or arguments suited to their claims; another Agent's agreement is not independent evidence, and repeating all original work is not the default. Open judgment remains open rather than becoming a fabricated Boolean check. The standing rule to use a Task Packet for every non-trivial task is unchanged.

## Replace Installed Files and Refresh Adoption

The v15 CLI accepts only the final six-name archive contract, including the Methods transition to Workflow and independent Verification described in the [Skills adoption guide](agent-skills.md). Earlier development archives using `svc-sub-agents` are not supported release inputs. Explicit inspection and removal of the old installed name remain available because installation records retain their original identity. An update of current names does not rename or remove the old installation.

Prepare the new CLI and confirm the target release can be read and its new entry can be installed before removing the old files. At the same host and scope as the old installation, inspect and remove it using the existing plan mechanism. These project/Codex examples are read-only until the reviewed mutation command is repeated with `--apply <plan-digest>`:

```console
svc skills status --repo /path/to/project --agent codex --skill svc-sub-agents --json
svc skills install --repo /path/to/project --agent codex --version 15.0.0 --skill svc-agent-collaboration --json
svc skills remove --repo /path/to/project --agent codex --skill svc-sub-agents --json
svc skills install --repo /path/to/project --agent codex --version 15.0.0 --skill svc-agent-collaboration --json
```

Use the target release version actually being adopted; preparation of these sources does not establish that a release is already published. Add `--global` for the original global scope or select `--agent claude` for that host. Apply removal before installing the replacement and review fresh plans after state changes. These are separate transactions, not an atomic cross-name migration; inspect and replan after a failure. A removal refusal indicates modified, unrecorded, incomplete, or conflicting state: preserve it and resolve ownership or incorporate local customizations before proceeding. Do not delete the directory or its record merely to bypass protection.

Update the other installed Skills to the same Corpus release with explicit `--skill` selections when using a partial installation. A default update includes the new six names and requires their existing SVC-owned installations; use install for any missing entry. Keep the released version shared across Skills without imposing full installation.

After file replacement, run `svc skills adopt` at each affected project to plan and apply refreshed entry pointers. Use `--skills-dir` when the selected installation root differs from the host's default project root. Existing managed blocks are refreshed only when unmodified; Consumer content outside them is preserved. Removing a Skill does not update adoption, and global installation does not refresh every project's instructions. Consumer-authored pointers outside the managed block need separate review.

For Vercel Skills, OpenSkills, or another manager, remove the old entry and install the new name through that manager's supported workflow, preserving local customizations. The original manager retains ownership of its files and lock state. SVC project adoption may still point to that installation, but the CLI must not take over its file ownership.

Confirm the new entry is available through the host, current Consumer pointers resolve, the retired entry is no longer discoverable at the replaced location, and the intended responsibilities and effect boundaries remain clear. Static path checks do not establish that an Agent will select or execute the Skill correctly in actual work.
