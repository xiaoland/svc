# SVC 用户手册

## 阅读框架指导

框架权威源从[共同协作契约](corpus/index.md)进入，按当前工作选择六个 Skills：

| Skill | 工作职责 |
| --- | --- |
| [svc-task-packet](corpus/svc-task-packet/SKILL.md) | 所有非平凡任务的持续状态、规划、信息组织、增长与收尾 |
| [svc-methods](corpus/svc-methods/SKILL.md) | 按需选择并组合 Explore、Design 和 Implementation |
| [svc-verification](corpus/svc-verification/SKILL.md) | 判断声明的证据、适用范围、可信基础与残余 |
| [svc-sub-agents](corpus/svc-sub-agents/SKILL.md) | 判断委派价值，安排责任、权限和结果接收 |
| [svc-specs](corpus/svc-specs/SKILL.md) | 持久项目知识的准入、归属与维护 |
| [svc-taste](corpus/svc-taste/SKILL.md) | 有真实压力的设计与实施取舍 |

描述提供目标与触发条件，正文明确首动作和完成条件，条件引用连接深层内容。Methods 内的小选择表处理三种方法的选择困难；六个 Skills 不构成固定流水线。这些源结构不保证每个宿主或模型都能可靠发现、加载和执行指导。

完整采用需要常驻入口，使共同契约与所有非平凡任务使用 Task Packet 的规则在工作开始时可见。[消费者 AGENTS 模板](corpus/svc-specs/assets/AGENTS.root.template.md)提供带路径占位的起始形状，项目所有者须适配实际可访问位置并维护自己的内容。当前不承诺 Skills 安装边界、宿主插件或跨 Skill 依赖解析。

## 安装与初始化 CLI

CLI 独立提供开发执行和观测工具，不携带 Corpus，也不安装、管理或更新 Skills。

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

未标记内容、消费者框架指针和本地 Agent 指导归消费者所有。CLI 的受管导航只提供工具入口，不生成框架采用协议。只有可识别且未被修改的生成块可被精确计划维护；修改过的导航或忽略块停止修复。过期计划、并发修改检查与失败回滚保护仍然有效。

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

框架采用变化遵循[Corpus 版本迁移指导](corpus/migrations/index.md)，由 Agent/Human 更新消费者拥有的契约与引用；它不变换 CLI 配置，也不由 CLI 记录基线。

## Behavioral SemVer 与发布

- **MAJOR**：不兼容地改变必要义务、默认行为、权限边界、Task Packet 语义、消费者布局或稳定 CLI 合同。
- **MINOR**：增加可选、向后兼容的能力。
- **PATCH**：修正或澄清已有协议而不改变上述行为。

Towncrier 分别记录 `.changes/cli/` 和 `.changes/corpus/`。CLI 发布通过 Trusted Publishing 发布已验证 wheel；Corpus 发布有独立 tag 与 GitHub Release。CLI wheel 不含框架内容，因此新 Corpus 不再随 CLI 发布投递。框架内容与 `corpus/version.json` 在功能变更中一起推进，发布 PR 只准备对应 changelog。当前不新增 Skills 安装或分发承诺，详见[贡献指南](CONTRIBUTING.md)。
