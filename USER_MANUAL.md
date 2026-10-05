# SVC 用户手册

## 阅读框架指导

框架权威源从[框架介绍与导航](corpus/index.md)进入，按当前工作选择六个 Skills：

| Skill | 工作职责 |
| --- | --- |
| [svc-task-packet](corpus/svc-task-packet/SKILL.md) | 所有非平凡任务的持续状态、规划、信息组织、增长与收尾 |
| [svc-methods](corpus/svc-methods/SKILL.md) | 按需选择并组合 Explore、Design 和 Implementation |
| [svc-verification](corpus/svc-verification/SKILL.md) | 判断声明的证据、适用范围、可信基础与残余 |
| [svc-sub-agents](corpus/svc-sub-agents/SKILL.md) | 判断委派价值，安排责任、权限和结果接收 |
| [svc-specs](corpus/svc-specs/SKILL.md) | 持久项目知识的准入、归属与维护 |
| [svc-taste](corpus/svc-taste/SKILL.md) | 有真实压力的设计与实施取舍 |

描述提供目标与触发条件，正文明确首动作和完成条件，条件引用连接深层内容。Methods 内的小选择表处理三种方法的选择困难；六个 Skills 不构成固定流水线。这些源结构不保证每个宿主或模型都能可靠发现、加载和执行指导。

每个 Skill 的必需指导与资源都位于自身目录内，不要求加载仓库根文件或其它 Skill。完整采用需要常驻入口，使授权边界与所有非平凡任务使用 Task Packet 的规则在工作开始时可见。[消费者 AGENTS 模板](corpus/svc-specs/assets/AGENTS.root.template.md)提供带路径占位的起始形状，项目所有者须适配实际可访问位置并维护自己的内容。下面的安装与采用步骤建立可访问入口；仍需在目标宿主中观察发现与执行，不能只凭文件存在宣称生效。

## 安装与初始化 CLI

CLI 提供开发执行和观测工具，并从独立发行物安装、管理 SVC Skills；CLI 包不携带 Corpus 正文。

```bash
python -m pip install sustainable-vibe-coding
svc --help
```

源码工作区使用 `pdm install`，随后通过 `pdm run svc` 调用 CLI。初始化默认 dry-run，不静默覆盖消费者内容：

```bash
svc init /path/to/project --json
svc init /path/to/project --apply <plan-digest>
svc status /path/to/project --json
```

精确计划 apply 可以创建：

```text
svc.json
.gitignore                 局部配置的有界忽略块
AGENTS.md                  有界 CLI 工具导航块
AGENTS.local.md            被忽略、归消费者所有的本地 Agent 指导
docs/index.md              缺失时创建，带有界 CLI 工具导航块
```

`svc.json` 是完整、提交到版本控制的项目配置。schema 4 可声明开发能力与有界运行，最小配置为：

```json
{
  "schema_version": 4
}
```

可选的 `svc.local.json` 是被忽略的稀疏 overlay，也须声明 schema 4。它可覆盖 `dev` 和主配置已有的 `run`，不能创建本地专有 run 名称或形成无效的有效配置。`init` 只维护标记的忽略块，不写本地配置；缺失时创建 `AGENTS.local.md`，之后不重写它。

在任何仓库先用 `svc status --json` 获取只读 preflight。它分别报告 CLI、配置、集成和 workspace 事实及一个主要延续动作，只汇总 dev target 和 run entry 名称而不执行它们；需要 runtime 观察时用 `svc dev status`。每个当前 `--json` 响应都是一个紧凑 JSON 值。

未标记内容、消费者框架指针和本地 Agent 指导归消费者所有。`init` 的受管导航只提供工具入口；框架采用使用独立的 `skills adopt` 标记块。只有可识别且未被修改的生成块可被精确计划维护；修改过的导航或忽略块停止修复。过期计划、并发修改检查与失败回滚保护仍然有效。

## 安装、升级与采用 Skills

六个 Skills 共用一个 Corpus 发布版本，可以选装。CLI 安装默认复制到项目目录，写操作必须显式选择宿主；Codex 使用 `.agents/skills`，Claude Code 使用 `.claude/skills`。`--global` 显式选择对应的用户目录。`--skill NAME` 可重复，省略时选择六个。安装、更新、移除和采用默认返回只读计划；重复相同命令并添加 `--apply <plan-digest>` 才写入。计划绑定当前文件状态，过期后必须重新审阅。

```bash
svc skills install --repo /path/to/project --agent codex --version 16.1.0 --json
svc skills install --repo /path/to/project --agent codex --version 16.1.0 --apply <plan-digest>
svc skills status --repo /path/to/project --agent codex --json
svc skills check --repo /path/to/project --agent codex --json
svc skills update --repo /path/to/project --agent codex --version <target-version> --json
svc skills adopt --repo /path/to/project --agent codex --json
svc skills adopt --repo /path/to/project --agent codex --apply <plan-digest>
svc skills unadopt --repo /path/to/project --agent codex --json
svc skills remove --repo /path/to/project --agent codex --json
```

`--version` 指向正式 `corpus-v<version>` 发布。`check` 未指定版本时只选择最新稳定 Corpus 发布，不使用同仓库的 CLI latest Release；`status` 不访问网络。离线安装与更新用 `--archive /path/svc-corpus-<version>.zip`，默认读取相邻 `.zip.sha256`，也可用 `--checksum` 指定校验文件。发布附件必须先实际发布才能通过在线路径下载；本地源码开发不把尚未发布的版本当作可下载发行物。

更新先校验目标发行物，再比较实际目录与安装基线。本地改动、新增文件、未知目录、另一管理器安装或符号链接均阻止覆盖；CLI 不提供强制覆盖或三方合并。安装记录位于目标 Skills 根下的 `.svc/<name>.json`。`recorded_version` 是记录版本，`actual_version` 仅在文件与目标发行物匹配时确认。多目标先做整体冲突预检，再逐 Skill 执行；失败停止后续项，已成功项保留并报告真实状态。受控错误与中断按文件事务回滚当前项；掉电或强制终止后的混合状态由下次检查识别并拒绝覆盖，没有自动恢复承诺。

`adopt` 不安装文件，不接管第三方安装。它要求实际可读的 `svc-task-packet`，在 Codex 的 `AGENTS.md` 或 Claude 的 `CLAUDE.md` 添加独立标记块，让 Human 权限边界和所有非平凡任务使用实际 Task Packet 的规则常驻可见。可用 `--skills-dir /actual/skills/root` 指向其它管理器的目录；原文件、锁文件和更新仍归原管理器。采用和取消采用保护块外内容，拒绝改写修改过的块。`unadopt` 不删除安装，`remove` 不修改项目采用指令；更新文件不自动迁移消费者资料，结果提供 release notes 与迁移指导链接。

也可以使用通用管理器直接安装源目录。例如 Vercel Skills 的宿主名为 `claude-code`，与 SVC CLI 的 `claude` 不同：

```bash
npx skills@1.7.0 add xiaoland/svc --skill svc-task-packet --agent codex --copy
npx skills@1.7.0 add xiaoland/svc --skill svc-methods --agent claude-code --copy
npx openskills@1.5.0 install xiaoland/svc
```

需要可复现内容时，按管理器支持的语法固定 `corpus-v<version>` tag 或完整 commit；不能把它们跟踪原来源的 update 当作 SVC 的明确换版。通用管理器可能覆盖本地定制；长期项目规则放在项目入口，修改 Skill 正文时使用自有 fork 并自行同步。OpenSkills 的 `sync` 管理自己的发现块，与 SVC `adopt` 的常驻规则不同。目录安装成功、宿主列出入口和 Agent 实际执行分别观察；当前已隔离验证两个管理器的目录安装和 Codex 的只读发现，未据此承诺 Claude 或模型自动触发。

## Task Packet

所有非平凡任务使用 Task Packet。先找到现有 Packet，不存在时建立足以表达目标、授权、当前状态与验证边界的最小入口，随后按任务压力增长。[Task Packet Skill](corpus/svc-task-packet/SKILL.md)拥有选择和维护规则，并提供 references/assets；Agent 使用已有文件工具完成操作，保护现有 Packet 和授权路径。模板存在不意味着必须创建所有文件，文件工具也不自动具备旧 CLI 创建命令的全部事务与路径保护。

## 声明与确保开发能力

可选的 `dev.targets` 直接声明命名能力。每个 target 有 scope（`worktree`、`repository` 或 `host`）、一个 readiness probe（`http`、`tcp` 或 `exec`）、可执行或手动 provisioner，以及可选的 target-local 可执行或手动 `stop` 动作。默认文本服务 Agent/Human，紧凑 JSON 服务脚本与 CI：

```bash
svc dev identity --repo /path/to/project --json
svc dev status --repo /path/to/project --json
svc dev status frontend --repo /path/to/project --json
svc dev ensure frontend --repo /path/to/project --json
svc dev stop frontend --repo /path/to/project --json
```

根 `status` 只汇总声明；`dev status` 观察 target，不启动或接管进程。`ensure` 处理一个 target，复用健康 endpoint，拒绝被占用但不健康的 endpoint，不执行 `manual` provisioner。`stop` 只执行消费者声明的清理动作，不从记录的 PID 推断权限。可执行工作按声明的 scope 协调，readiness 成功后释放进程权限。默认 worktree scope 的 probe endpoint 必须证明解析出的实例；host scope 要求 `host_key`。

Dev 值只支持 `${dev.instance}`、`${dev.worktree.id}` 和 `${dev.target}` 插值。命令是参数数组，配置的工作目录必须位于 workspace 内。

## 运行共同声明的命令

独立的 `run` map 声明有界、归项目所有的命令，让 Human、Agent、编辑器或 CI 使用相同名称：

```json
{
  "schema_version": 4,
  "run": {
    "check": {
      "argv": ["pdm", "run", "test"],
      "env_files": [".env.shared"],
      "env": {"PYTHONUTF8": "1"}
    }
  }
}
```

```bash
svc run check --repo /path/to/project
svc run --follow <execution-id> --repo /path/to/project
svc run --inspect <execution-id> --repo /path/to/project --json
```

一个 caller 拥有前台进程；同一有效 worktree entry 的并发本地 caller 跟随该次执行，不重复启动。execution ID 寻址捕获的 stdout/stderr 和有界 receipt。之后显式调用 entry 会重新执行，已结束的 receipt 不声明新鲜度或验收通过。文本模式保留原生 stdout/stderr，把 SVC 生命周期事实写入 stderr；`--json` 不显示原生输出，只返回紧凑 receipt。

Overlay 可替换已有 entry 的 argv、cwd、env-file 数组并合并 inline env。相对路径从 workspace 根解析；严格环境文件按顺序加载，再应用 inline env，receipt 不保存原始环境值。`run` 不提供 shell 字符串、依赖图、任意参数、后台模式、readiness、缓存、artifact 模型或项目结果判定。

## 分析 Agent 任务证据

Telemetry 获取一个显式选择的本地 provider 源，analysis 读取一个不可变证据 bundle。两者不上传数据、访问网络服务、调用模型或宣称审计完整性。调用 Agent 拥有语义解释和结论；SVC 拥有有界捕获、原生保真、快照身份和确定性结构导航。

```bash
svc telemetry agent-thread list [selection options] [--json]
svc telemetry agent-thread export (--thread-id <id> | --source <path>) --output <absent.zip> [--json]

svc analysis query --schema
svc analysis query --input /path/to/evidence-v3.zip --request <file|->
svc analysis read --schema
svc analysis read --input /path/to/evidence-v3.zip --request <file|->
```

`list` 提供有界 inventory，展示 provider 生命周期、识别结果和本地来源，不预测 export 时源是否仍可读。`export` 要求确切 thread ID 或源路径与不存在的目标，保持源只读，拒绝覆盖及源/目标别名。成功 export 是已验证 bundle；进程中断可能留下无效的部分目标，重试前须删除。caller 决定存储与访问权限；没有 `--include-sensitive` 确认、`--repo` 边界、TTY gate 或 private member-mode 承诺。

schema-v3 ZIP 的权威是 `manifest.json`、`native.bin` 和 `native-index.jsonl`。Provider 原生字节保留源顺序；framing 只记录稳定 ID、连续字节范围、源坐标和 `complete|incomplete` 状态。一个 `evidence_id` 绑定原生与 framing 字节。可选 `trajectory.jsonl` 是可丢弃重建的派生结构缓存，其计数、能力和损失摘要也不是证据权威。schema-v1/v2 bundle 属于历史 cutoff，query/read 在有界识别后拒绝，须从 provider 本地源重新获取。

这是同用户本地流程，不是安全沙箱；SVC 不防御 root、同账号恶意进程或对抗性路径替换。原生证据可包含所有选中内容，结构投影与省略不提供保密或脱敏。caller 拥有存储、访问、保留和披露决策。

`query` 是封闭的 machine-first 协议，提供 `overview` 和确定性 `match`。它使用或重建结构缓存，返回证据身份、源/捕获事实、派生能力与损失、稳定 native/trajectory 引用、结构范围及有界匹配。匹配条件覆盖 record type、role、tool、relationship、native range 或 literal text；不支持任意字段选择、SQL/JSONPath、正则程序、join、grouping、scoring 或自然语言提示。

`read` 按原生顺序向前读取，从开头或确切 native 引用开始，可包含有界前置 records，并以绑定请求 scope 的 cursor 延续。结果提供捕获的字节/值、确切 frame/fragment offsets、digest、来源与延续。cursor 是带类型请求 scope 的未签名本地状态，不是认证能力；frame/fragment digest 在读取时从原生字节计算。确切 UTF-8 fragment 可直接读为文本，任意字节以无损 base64 返回。Read 不过滤、重排、总结或静默标准化文本。

响应区分 `complete`、`partial` 和 `unavailable`；分页不是证据损失。不完整的 acquisition frame 可读，但不能产生 projection record。缺失或无效缓存从原生证据重建；重建失败使结构 query 不可用，不阻止 native read。Query/read 是 JSON-first，`--schema` 拥有机器合同；任务分析方法和权限边界由 `svc analysis --help` 提供。

旧 `telemetry agent-thread analyze` 与 Textual navigator 已移除；调用 Agent 通过显式 `query` 与原生 `read` 解释证据。

## 人工迁移 CLI 配置

包管理器拥有 CLI 安装和更新。CLI 16 不提供 `lookup`、`upgrade` 或 `task init/grow`，不保留别名或转发。旧配置采用 hard-cutoff，失败时保持文件不变；`init` 不清空、重建或自动迁移旧配置。

先备份并审查项目配置，把 `svc.json` 与存在的 `svc.local.json` 的 `schema_version` 改为 `4`，从主配置删除 `corpus_version`，保留其余 dev/run 声明与 overlay 内容。之后用 `svc status --json` 检查，再审查新的 init 计划及其受管工具导航变化。未知字段和无效有效配置继续被拒绝。

框架采用变化遵循[Corpus 版本迁移指导](corpus/migrations/index.md)，由 Agent/Human 更新消费者拥有的契约与引用；它不变换 CLI 配置，不自动迁移消费者语义；CLI 只记录自己安装文件的基线。

## Behavioral SemVer 与发布

- **MAJOR**：不兼容地改变必要义务、默认行为、权限边界、Task Packet 语义、消费者布局或稳定 CLI 合同。
- **MINOR**：增加可选、向后兼容的能力。
- **PATCH**：修正或澄清已有协议而不改变上述行为。

Towncrier 分别记录 `.changes/cli/` 和 `.changes/corpus/`。CLI 发布通过 Trusted Publishing 发布已验证 wheel；Corpus 发布有独立 `corpus-v<version>` tag 与 GitHub Release。CLI wheel 不含框架内容，因此新 Corpus 不随 CLI 发布投递。框架版本权威是根 `pyproject.toml` 的 `[tool.svc.corpus].version`，六个 Skill 的 `metadata.version` 由发布准备命令同步；发布物提供精简 Skills ZIP、manifest 与外部 SHA-256 校验文件。MIT 声明随每个独立 Skill 与 CLI 发行物携带，详见[贡献指南](CONTRIBUTING.md)。
