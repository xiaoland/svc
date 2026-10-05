# 设计：六个 Skills 与 CLI 内容解耦

用户已确认拆成六个 Skills，并保留 Task Packet 对所有非平凡任务的现有触发范围。当前方案先完成职责与内容拆分，再分别改善发现、加载和执行。方案不决定安装边界、宿主插件、分发包格式或独立安装承诺。

## 已确认的边界

六个入口为 `svc-task-packet`、`svc-methods`、`svc-verification`、`svc-sub-agents`、`svc-specs`、`svc-taste`。Explore、Design、Implementation 在 Methods 内按需选择并递归组合；合并入口不合并语义职责，也不形成阶段流水线。Task Packet 不缩小为恢复、交接或并行协调工具。

借鉴 matt-skills 的三种机制：描述承担目标与触发条件，正文明确首动作和可判断的完成条件，选择困难时使用薄路由。正文按语义段落换行，列表、表格和代码保留结构；不按固定列宽硬换行。

## 权威源与布局

继续以 `corpus/` 为唯一框架权威源，六个目录直接使用对应 Skill 名称，入口为 `SKILL.md`。只为实际内容建立 `references/` 和 `assets/`；不保留同义的旧 `index.md` 副本，不新增生成式技能层或运行时路由器。

```text
corpus/
  index.md
  AGENTS.md
  version.json
  migrations/
  svc-task-packet/
    SKILL.md
    references/
    assets/
  svc-methods/
    SKILL.md
    references/
  svc-verification/
    SKILL.md
  svc-sub-agents/
    SKILL.md
    references/
  svc-specs/
    SKILL.md
    references/
    assets/
  svc-taste/
    SKILL.md
    references/
```

根 `index.md` 保留短共同协作契约，拥有 Human 权限、可质疑的事实与方案、自主调查、持久修改前的条件及重新请求 Human 决策的规则；目录表只导航，不要求继续加载其他入口。六个 Skill 在当前上下文尚未包含共同契约时读取它，不复制全文，也不增加已加载状态文件。

Consumer AGENTS 模板提供常驻的共同契约指针，以及所有非平凡任务使用 Task Packet 的提示。完整采用需要可见的常驻入口，不能声称条件性 Skill 元数据保证全局约束在任何调用前生效。模板只提供起始形状，项目内容及授权始终由消费者拥有。

各 Skill 保留自身职责边界，例如 Verification 不授予接受权限，Implementation 需要已授权的改变，Child 只获得 Assignment 的权限。这些边界不能全部删成共同契约链接。框架授权规则不转交 Task Packet。

跨 Skill 的工作切换写明确切名称与触发情形；对某条参考规范的读取直接指向唯一所有者并写明条件。源码中使用可校验的相对链接，不要求返回根索引选路。这确定源码关系，不承诺任意安装布局均保留这些路径；当前不增加依赖解析器或共享内容投影。

## 内容迁移表

| 当前所有者 | 目标所有者 | 处理 |
| --- | --- | --- |
| `corpus/index.md` | 根 `index.md` | 保留共同契约，改为六入口的短导航 |
| `task-packet/index.md` | `svc-task-packet/SKILL.md` | 保留完整任务职责与非平凡任务触发 |
| `task-packet/planning.md`、`information.md`、`growth.md` | Task Packet 的同名 references | 保留独立问题和语义边界 |
| `task-packet/templates/index.md` 与模板 | Task Packet 的模板选择 reference 与 assets | 选择规则仍按已准入的需要，模板存在不代表必须创建文件 |
| `methods/index.md` | `svc-methods/SKILL.md` | 选择当前所需方法，不承载全任务编排 |
| Explore、Design、Implementation 及三个 Design 投影 | Methods 的 `explore.md`、`design.md`、`implementation.md`、`product-design.md`、`technical-design.md`、`test-design.md` references | 保留全部语义，按当前工作分支读取 |
| `verification/index.md` | `svc-verification/SKILL.md` | 保留声明、观察、可信基础、残余及证明复用 |
| `sub-agents/index.md`、`explorer.md`、`executor.md` | `svc-sub-agents/SKILL.md` 与角色 references | 角色不拆为额外 Skills，不复制方法 |
| `specs/index.md` 与规范种类、协调扩展 | `svc-specs/SKILL.md` 与对应 references | 保留准入、持久知识所有权和协调扩展边界 |
| Specs 各类模板与 `templates/AGENTS.*.template.md` | Specs 的 assets | 保留适用条件和消费者所有权 |
| `taste/index.md` 与 `taste/implementation/index.md` | `svc-taste/SKILL.md` 与 `references/implementation.md` | 可主要提供参考；不改成固定流程或每次必读准则集 |
| `migrations/`、`version.json` | 原发布所有者 | 保留独立框架发布和版本相关参考 |
| `corpus/AGENTS.md` | 原维护者指导 | 更新 Skill 作者合同；不成为消费者 Skill |

每份旧规范的主张必须能够在新所有者中找到，允许消除重复陈述和调整导航，不顺手收窄职责、改变权限或规定新流程。Consumer 实例中的 inquiry、design、verification 状态归 Task Packet；方法如何产生或判断结果仍归相应 Skill。

## 六个入口的使用合同

这些是实现时的正文与描述要求，不是要求每个任务展示的方法术语或固定文件清单。

| Skill | 发现条件 | 首动作 | 可用结果与结束条件 |
| --- | --- | --- | --- |
| Task Packet | 开始或推进任一非平凡任务，包括恢复、任务形状变化和收尾 | 找到现有 Packet；不存在时建立最小入口，明确目标、授权、当前状态和验证边界 | Packet 足以恢复和控制当前任务；随任务变化维护，完成后按保留规则收尾 |
| Methods | 存在非显然的信息缺口、未决方案，或要实现已明确的有界改变 | 按当前缺少的返回选择 Explore、Design 或 Implementation，仅加载对应分支 | 返回关键信息、当前可实施方案或真实改变及局部反馈；适当时转换方法或返回控制 |
| Verification | 需要判断关键行为、已有系统或完成声明是否成立 | 确认声明及其所有者，选择能区分重要替代解释的观察 | 给出证据、适用范围、可信基础和残余；不替人授权效果或验收 |
| Sub-agents | 正在判断是否委派，或安排、接收、调整一项有边界的委派 | 比较直接工作、渐进加载、确定性机制和委派的成本收益 | 给出不委派的判断，或有明确责任、权限和结果合同的 Assignment 及整合返回 |
| Specs | 持久项目知识需要建立、更新、迁移所有者，或要判断是否值得形成规范 | 查找现有权威，先判断源码、配置、schema 或测试能否直接拥有该事实 | 更新合适的持久所有者，或说明无需新增文档；不把临时证据提升为项目事实 |
| Taste | 设计或实施面临影响权限、数据、边界、命名、依赖或改变成本的真实取舍 | 确认当前压力、已有项目事实和人的合法偏好，选择相关判断指导 | 给出有因果理由和反压力的判断；不以通用准则覆盖项目事实或人的权限 |

描述同时覆盖用户明确请求与任务中途出现的状态。触发指导不授予写入、委派或外部效果权限。不存在信息缺口的直接查询、机械修改等简单工作继续直接完成；验证也不强制制造新的测试或文档。

Skill frontmatter 首轮只需要规范要求的 `name` 和 `description`，不声明新工具权限、宿主专属能力、依赖图或固定运行时。元数据与正文使用现有 Agent 指导语言，Task Packet 的协作文件使用中文。不新增第七个总路由 Skill；Methods 内部的小选择表只路由其三种方法。

## CLI 最终边界：hard-cutoff

用户已确认移除公开命令并继续采用 hard-cutoff。下列变化按大版本处理，不提供兼容入口、静默接受旧配置或自动迁移路径。

移除 `lookup`、`upgrade` 和 `task init/grow`。lookup 与 Corpus 基线升级不再属于 CLI；Task Packet Skill 使用自己的 assets 和现有文件工具完成任务文件操作与增长判断，不将模板复制入 CLI，也不为了保留命令形状增加通用模板接口。Skill 操作必须保护已存在的 Packet 和授权路径，但不能声称文件工具天然等同于旧命令的原子创建及全部路径检查。

保留 `init`、`status`、`dev`、`run`、`double`、`telemetry`、`analysis`。init/status 只管理 CLI 配置、workspace、受管集成块及 dev/run 声明，不安装 Skills、管理框架版本或生成框架采用协议。CLI 帮助继续作为命令合同。

配置采用 schema 4，删除 `corpus_version`，保留 dev/run 及 overlay 的现有约束。旧 schema 明确拒绝并给出迁移指引，不忽略版本、不自动删除字段，也不通过 init 清空或重建旧配置。人工迁移需同时更新主配置及存在的 overlay 的 schema，删除主配置的 Corpus 基线字段，并保留其余内容。保留 current-only 配置合同，不新增自动迁移协议。

CLI 的受管 AGENTS/docs 导航改为工具入口，消费者自己的框架指针不由 CLI 改写。继续只修改可识别且未被修改的生成块；未标记内容、改过的受管块和本地 Agent 指导不得覆盖。保留原有精确 plan/apply、并发修改检查和回滚保护。

删除 `cli/pdm_build.py` 的 Corpus 输入与投影、Corpus reader、catalog/release/migration 领域模型及源码回退。保留 CLI 输出 schema 资源；sdist 不含 `_build_inputs/corpus`，wheel 不含 Corpus 正文、模板或 catalog，CLI 构建与执行不需要仓库旁的 Corpus。

catalog 中被文件事务继续使用的 JSON 编码和散列小函数移入既有 `plans.py`，更新 project/integration 的调用，不新增通用工具层。框架版本索引的解析与检查归仓库 `tools/`，CLI runtime 不导入它。只删除确认已无剩余消费者的依赖。

删除 lookup/upgrade 的输出模型、注册与生成 schema；init 结果 schema 从 3 升为 4，status 从 2 升为 3，去除 Corpus 字段和延续动作，保留配置与集成状态。更新 schema 生成器、测试支持数据、引用及 import-linter 合同，避免全域绕过或无关重构。

## 发布、文档与检查

这次消费者地址与 CLI 契约变化建议分别推进 Corpus 与 CLI 至 16.0.0；配置 schema 4、各命令结果 schema 和两产品版本仍是独立概念。保留当前 Towncrier、changelog、tag 及发布 workflow 的职责，不决定 Skills 安装包或发布新宿主插件。

添加各产品的中文发布片段，以及框架采用指南和 CLI 手工配置迁移说明。Corpus migration 不负责 CLI 配置变换。更新 root/corpus AGENTS、README、USER_MANUAL、CONTRIBUTING、CLI README 和已有产品事实所有者；不建立第二套持久项目说明。保持框架内容与版本一起推进的检查。

旧 catalog 投影检查由源 Skills 的名字、描述、资源和本地链接检查替代。检查使用既有仓库工具和测试入口；不为了六个固定入口实现通用 Skill 安装器、YAML 解析框架或性能遥测系统。机械验证不宣称已经证明模型会可靠发现或执行指导。

## 验证场景与实现准入

| 场景 | 关键观察 |
| --- | --- |
| 从 Consumer AGENTS 开始非平凡任务 | 能到达共同契约和 Task Packet，建立足够的任务状态而不加载整套正文 |
| 没有采用模板，直接调用 Verification | 获得共同契约和本职责的授权边界，不要求读取其他方法 |
| 已知位置的文字小修改 | 直接完成，不误触发完整方法或建立额外任务文件 |
| 原因不明的偶发故障 | Methods 进入 Explore，选择能区分解释的观察 |
| 实施中出现恢复语义或数据所有权取舍 | 在出现压力时进入 Design/Taste，形成可用选择后返回实施 |
| 接手暂停任务 | Task Packet 恢复目标、授权、当前状态与下一步；保持完整职责 |
| 明确的委派机会 | Sub-agents 判断价值，形成受限 Assignment；不默认派出团队 |
| 修改持久产品承诺 | Specs 找到既有所有者，使用对应参考；不默认创建规范全家桶 |
| 干净环境安装 CLI wheel | 没有 Corpus 仍能 init/status 并完成一个真实 dev/run 入口；旧配置明确失败且内容不变 |

源检查验证六个入口及全部本地引用，内容核对保证现有职责和主张没有丢失。代表性 Agent 走查记录可见入口、模型与上下文、触发选择、首次有效行动前的无关读取、深层加载原因、结果质量；不以单次观察或 token 数宣称统计性能保证。

六 Skill 拆分已确认，共同契约、内容归属与验证路径已收敛，公开命令删除和旧配置 hard-cutoff 已获用户确认。当前没有阻止进入实现的设计未决项，用户已明确授权实施，源码修改与集成验收已完成。实现仅覆盖本方案，不扩展至安装边界、宿主插件或额外兼容机制。
