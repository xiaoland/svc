# Adopt the public Skills release

Use this guide to move an SVC-managed Corpus installation from `corpus-v17.0.0` to `skills-v1.0.0`. The first public Skills release keeps the seven v17 Skill names and their host discovery paths. The tag distinguishes the new release line from the earlier Corpus releases. The public CLI resolves `skills check` and explicit `--version` requests in the `skills-v` line.

## Update a managed installation

Install the [public CLI](../../USER_MANUAL.md) and use the host and scope of your current installation. Keep the [v17 release assets](https://github.com/xiaoland/svc/releases/tag/corpus-v17.0.0) if you may need to roll back. For each installed Skill, keep its ZIP alongside `svc-skills-17.0.0.json` and `svc-skills-17.0.0.json.sha256`.

Check the selected installation and preview the update. For example, use these commands for a Codex project installation.

```sh
svc skills status --agent codex
svc skills check --agent codex --version 1.0.0
svc skills update --agent codex --version 1.0.0
```

Add `--global` throughout for a user-level installation, or select `--agent claude` for Claude Code. For a partial installation, repeat `--skill <name>` for each Skill you want to update. Plan any missing Skills separately with `skills install`. Resolve modified files or installations owned by another manager before applying an update. An update requires an unmodified SVC installation record for each selected Skill.

Repeat the update with `--apply <plan-digest>`, then run the same check and confirm the selected Skills are current. The file update preserves Consumer instructions and active Task Packets. Review any Consumer-authored reference that pins a release tag or version and update it if you intend to follow the public line. For earlier releases, also consult the applicable [framework migration guides](index.md).

## Roll back to v17

Use `skills update` with the saved v17 ZIP for each Skill you want to restore. For example, preview `svc skills update --agent codex --archive /path/to/svc-workflow-17.0.0.zip`, then repeat it with the displayed plan digest. Keep the catalog and its checksum beside the ZIP, or pass the catalog path with `--catalog`. Check the restored Skill with `skills check` using the same archive, host, and scope.
