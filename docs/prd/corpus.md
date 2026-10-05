# CLI 工具项目集成

本[产品事实](index.md)投影拥有 CLI 初始化、配置与受管集成的可观察承诺。CLI 语法、配置解析和文件事务由可执行源负责；框架指导与版本迁移由 `corpus/` 拥有。

CLI 提供 `init`、`status`、`skills`、`dev`、`run`、`double`、`telemetry` 和 `analysis`。它不携带 Corpus 正文；`skills` 消费独立发行物并管理明确属于 CLI 的文件，项目采用与文件安装独立。CLI 版本、配置 schema 与 Corpus 版本是独立概念。

普通命令文本根据实际语义支持 Agent/Human 决策。紧凑 JSON 是脚本与 CI 的独立投影；预期的领域非成功结果保持自足，语法、非法请求和基础设施失败仍是错误。不为无关命令增加通用结果 schema。

## 消费者项目合同

初始化默认 dry-run，不静默覆盖消费者内容。

```bash
svc init /path/to/project --json
svc init /path/to/project --apply <plan-digest>
svc status /path/to/project --json
```

精确计划 apply 可以创建 `svc.json`、`.gitignore` 中的局部配置忽略块、`AGENTS.md` 与 `docs/index.md` 中的 CLI 工具导航块，以及被忽略且归消费者所有的 `AGENTS.local.md`。工具导航只指向 CLI 帮助和工具操作，不生成框架采用协议；框架常驻规则与实际 Skill 指针可由独立 `skills adopt` 的精确计划建立，消费者自己的规则保持原样。

`svc.json` 是完整、提交到版本控制的项目配置。schema 4 可声明 `dev` 与 `run`，最小形状为：

```json
{
  "schema_version": 4
}
```

`svc.local.json` 是可选、被忽略的稀疏 overlay，也必须声明 schema 4。它只覆盖 `dev` 和已在主配置声明的 `run`，不能创建本地专有 run 名称或形成无效的有效配置。`init` 只维护其标记的忽略块，不写本地配置；缺失时创建 `AGENTS.local.md`，之后不重写它。

CLI 16 采用 hard-cutoff，拒绝旧配置而不改写文件。人工迁移须把主配置和存在的 overlay 都改为 schema 4，从主配置删除 `corpus_version`，保留其余声明。没有自动迁移、字段别名或旧命令转发。

`status` 是只读的紧凑 JSON preflight，独立报告 CLI、配置、集成和 workspace 事实及一个主要延续动作。它汇总 dev target 和提交的 run entry 名称而不执行它们；观察 runtime 使用 `svc dev status`。每个当前 `--json` 响应都是一个紧凑 JSON 值。

未标记内容、消费者框架指针和本地 Agent 指导始终归消费者所有。只有可识别且未被修改的生成块可由精确计划维护；修改过的导航块或忽略块停止修复，等待审查。计划过期或文件并发改变时拒绝 apply；写入失败按原文件事务合同回滚。CLI 帮助独立拥有工具语法，不要求加载框架 Skill。

## Skills 分发与项目采用

六个 Skill 共用一个发布版本，每个目录可单独安装并包含必需资源。CLI 直接读取正式发行 ZIP 或离线 ZIP，不依赖第三方管理器，也不把 Corpus 重新纳入 wheel。Vercel Skills 和 OpenSkills 可以安装相同 Git 源目录；CLI 能使用其实际入口建立项目采用，但不接管文件或锁记录。

`skills install/update/remove` 以明确宿主、项目或全局范围和 Skill 选择产生精确计划；只对原样、明确归 CLI 的目录执行更新与移除。`status` 观察本地基线，`check` 比较明确目标或最新稳定 Corpus 发布；CLI 与 Corpus 发布版本独立，latest CLI Release 不能充当 Skills 更新。未知来源、修改或新增内容保留。多项执行中的成功、失败与未执行项保持可区分。

`skills adopt/unadopt` 独立维护项目入口中的干净 SVC 采用块，不安装或移除 Skill。完整采用建立所有非平凡任务恢复或创建实际 Task Packet 的常驻规则，并指向实际可用入口。文件存在不能证明宿主发现；宿主发现不能证明 Agent 自动触发。文件更新结果提供发布与迁移指导，不自动变更消费者任务或持久文档。
