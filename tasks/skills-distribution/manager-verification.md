# 第三方 Skills manager 隔离验收

调查日期：2026-10-05。源码输入固定为已提交的 `794966f`（`fix(corpus): 使六个 Skills 可独立搬运和使用`）；没有读取当前工作区中 releaseworker 正在修改的 metadata。所有实验均使用临时项目、临时 `HOME`、临时 npm cache 和本地源码快照，未访问真实 `~/.agents` 或 `~/.claude`。

## 固定版本与安装命令

Vercel Skills：`skills@1.7.0`。从快照的 `corpus` 目录安装六个 Skill：

```sh
npx --yes skills@1.7.0 add "$SNAPSHOT/corpus" \
  --copy --agent codex --agent claude-code --yes --json
```

结果为六个 Skill 安装到项目 `.agents/skills/<name>`，同时生成 `.claude/skills/<name>`；输出标记为 `copy → Codex, Claude Code`。`--agent claude` 会失败并列出 `claude-code` 为有效名称，因此“Claude”在该 CLI 中的实际 agent 标识是 `claude-code`。

OpenSkills：`openskills@1.5.0`。默认项目安装命令为：

```sh
npx --yes openskills@1.5.0 install "$SNAPSHOT/corpus" --yes
```

结果明确报告 `Location: project (.claude/skills)`，发现并安装六个 Skill。每个目录额外写入 `.openskills.json`，其中保留本地 source、具体 `localPath` 和安装时间；这些 manager 元数据不属于 Skill 源文件比较范围。

## 选择性安装

Vercel 使用：

```sh
npx --yes skills@1.7.0 add "$SNAPSHOT/corpus" \
  --copy --agent codex --skill svc-methods --yes --json
```

结果只安装 `svc-methods`，输出 `Selected 1 skill: svc-methods`。

OpenSkills 没有同等的 `--skill` 参数；把本地 source 指向单个 Skill 目录：

```sh
npx --yes openskills@1.5.0 install \
  "$SNAPSHOT/corpus/svc-methods" --yes
```

结果只安装 `svc-methods`。这是通过 source 边界实现的选择性安装，不是声称 OpenSkills 支持 Vercel 的命名筛选参数。

## 内容与资源闭合

六个目录均与快照逐文件、逐字节比较，结果全部相等：

| Skill | 源文件数 | Vercel copy | OpenSkills copy |
| --- | ---: | --- | --- |
| `svc-methods` | 7 | exact | exact |
| `svc-specs` | 14 | exact | exact |
| `svc-sub-agents` | 3 | exact | exact |
| `svc-task-packet` | 14 | exact | exact |
| `svc-taste` | 2 | exact | exact |
| `svc-verification` | 1 | exact | exact |

对两个安装结果中的所有 Markdown 相对链接做了解析，未发现指向安装目录外或不存在文件的相对链接。外部 URL 和锚点没有被误判为本地资源。Vercel lock 输出为 local source 和每个 Skill 的 `computedHash`；OpenSkills 的 `.openskills.json` 记录其单 Skill `localPath`。

## 卸载边界

Vercel 在安装六个 Skill 后，向 `.agents/skills/unrelated/SKILL.md` 写入无关 sentinel，再移除 `svc-methods`。结果：`svc-methods` 从 Codex 与 Claude Code 目标移除，其余五个 Skill 保留，无关 sentinel 保留。

OpenSkills 在单 Skill 项目中加入 `.claude/skills/unrelated/SKILL.md`，执行：

```sh
npx --yes openskills@1.5.0 remove svc-methods
```

结果：`svc-methods` 被移除，无关 sentinel 保留。

这些是临时项目内的 manager-owned 安装边界观察，不证明真实用户目录或已有第三方安装会被安全接管；本实验没有使用 `--global`。

## Release tag 事实核对

从 `794966f:corpus/version.json` 读取版本 `16.0.0`，按当前发布 workflow 的固定拼接语法得到 `corpus-v16.0.0`。版本 SemVer 正则和 tag 前缀/形状检查通过；本地没有该 tag，`git ls-remote origin refs/tags/corpus-v16.0.0` 没有返回记录。因此本轮没有创建、推送或发布不存在的新 tag。

当前宿主可执行文件存在并报告 `codex-cli 0.159.3` 与 `Claude Code 2.1.236`。当时尚未启动任何宿主会话；后续的 Codex app-server 只读探针另有记录。该命令行版本事实本身不证明宿主采用，也不替代后续的实际发现证据。

实验结束后已清理临时项目、源码快照和 npm cache。

## Codex app-server 只读发现补充

随后检查了本机 `codex app-server --help` 和临时生成的实验协议 schema。当前 CLI 提供只读的 `skills/list` 方法；参数包含 `cwds` 和 `forceReload`，返回每个工作目录的 Skill metadata（名称、description、路径、scope、enabled 等）。

在临时项目中把当前 `corpus/svc-*` 复制到 `.agents/skills`，并使用临时 `HOME` 与 `CODEX_HOME` 启动：

```text
codex app-server --stdio
```

仅发送以下 JSON-RPC 消息：`initialize`、`initialized`、`skills/list`（`{"cwds":["<temporary-project>"],"forceReload":true}`）。没有发送 `thread/start`、`turn/start`、执行命令或任何 LLM 请求。`initialize` 返回 `Codex Desktop/0.159.3`；`skills/list` 返回六个 repo-scope、enabled 的 SVC Skill：

```text
svc-methods       .agents/skills/svc-methods/SKILL.md
svc-specs         .agents/skills/svc-specs/SKILL.md
svc-sub-agents    .agents/skills/svc-sub-agents/SKILL.md
svc-task-packet   .agents/skills/svc-task-packet/SKILL.md
svc-taste         .agents/skills/svc-taste/SKILL.md
svc-verification  .agents/skills/svc-verification/SKILL.md
```

返回的六条 description 与当前 source metadata 逐条相同；Codex 同时返回其临时 `CODEX_HOME` 下的 system skills，这些不属于项目安装结果。该实验实际证明了 Codex app-server 对临时项目的发现、描述和加载路径可见性，不证明会话在后续任务中一定选择某个 Skill。

Claude CLI 的帮助输出没有提供等价的无会话、只读 Skill inventory API。为避免启动会话或触发写作，本轮未执行 Claude runtime discovery；Claude 宿主发现与生效仍保持未验证。

## Git 根布局兼容补充

最后用当前稳定 source snapshot 构造了临时 repo root：根目录只放 `README.md` 与 MIT `LICENSE`，六个目录位于 `corpus/svc-*`；每个 Skill 目录携带当前 `metadata: {"version": "16.1.0"}` 和同一份 MIT `LICENSE`。两个安装命令均从 repo root 传入 source，CWD 为另一个临时项目：

```sh
npm_config_cache="$NPM_CACHE_DIR" npx --yes skills@1.7.0 add "$SNAPSHOT" \
  --copy --agent codex --yes --json

npm_config_cache="$NPM_CACHE_DIR" npx --yes openskills@1.5.0 install \
  "$SNAPSHOT" --yes
```

两者都递归发现并安装六个 Skill。Vercel 输出六个 project `.agents/skills/<name>`，OpenSkills 输出六个 project `.claude/skills/<name>`；manager 自己的 `skills-lock.json` 和 `.openskills.json` 未计入源文件比较。

对六个安装结果逐文件比较通过；每个 Skill 的 `SKILL.md` 保留 `16.1.0` metadata，每个 `LICENSE` 与 snapshot 根 `LICENSE` 的 SHA-256 均一致，六个目录的正文与资源也保持逐字节一致。该结果证明当前 Git 根布局可被两个 manager 递归发现，并携带 metadata 与许可证文件；没有改源码，也没有启动后续实验。临时 repo、项目和 npm cache 已清理。
