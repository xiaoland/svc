# 实施路线

本路线把已收敛方案转为有边界的改变。六个 Skills 的拆分及 CLI 的公开命令删除、旧配置 hard-cutoff 均已确认，设计不存在阻止进入实现的未决项。用户已明确授权实施，源码修改与集成验收已完成；本次提交已获用户明确授权；推送和发布仍需明确授权。

## 1. 拆分框架内容，保留语义

在 `corpus/` 建立六个 Skill 入口，将深层指导和模板迁入对应 references/assets，保留根共同契约与版本相关迁移资料。更新作者合同、消费者模板和所有本地引用。按语义段落消除固定列宽硬换行，不改变代码块、列表或表格结构。

验证每份旧文档均有明确新所有者，全部职责、权限边界和现有触发范围得到保留。确认 Methods 只选择其三个内部方法，Task Packet 仍对非平凡任务触发，Taste 和角色契约没有重复权威。

## 2. 逐入口改善发现、加载与执行

逐个收敛 name/description、首动作、反馈循环、可用结果、停止与转向条件。对深层参考写明到达条件，公共必需内容留在入口。用设计中的正常启动、直接调用和任务中途变化场景走查，不把固定步骤强加给纯参考型 Taste。

验证指导能产生具体动作，简单工作不被误路由，Methods 能在信息缺口、方案分歧与实现反馈之间转换，加载共同契约不要求顺带读其他正文。记录观察限制，不建立常驻模型评测平台。

## 3. CLI 与 Corpus 解耦

移除 lookup/upgrade/task 的解析、执行、输出和专有资源，删除 Corpus 投影与源码回退，不保留旧命令别名或转发器。把保留的小型事务编码与散列函数移到既有 owner，把框架版本检查移到仓库 tools。将配置切换为 schema 4，移除 Corpus 基线，更新 init/status 与受管工具导航；旧 schema 明确拒绝，不加入自动迁移。

在 config/project/integration 的既有行为边界更新回归检查：新配置与 overlay 正常解析，旧配置拒绝且不改文件，未知字段继续拒绝；修改过的受管块和消费者内容受到保护；精确计划过期、并发变更和回滚仍按现有合同处理。删除不再提供的能力测试，保留真实事务与运行时保护测试。

同步 output schema 注册与生成文件、测试配置 builders、import-linter、CLI 依赖与构建元数据。CLI 必须从 sdist 在没有 Corpus 的环境中构建 wheel，独立安装后 init/status 与真实 dev/run 能正常执行。

## 4. 集成验证与收尾

更新 README、USER_MANUAL、CONTRIBUTING、AGENTS、CLI README 与持久产品事实；记录独立的 Corpus/CLI 行为变化、版本、发布片段和迁移说明。保持现有发布职责，不引入尚未讨论的安装流程。

运行适用的源引用与 Skill 合同检查、框架版本检查、输出 schema 检查、配置与集成回归、全量 `pdm run check`、sdist→wheel 构建及隔离环境黑盒验收。检查两种归档都没有 Corpus/catalog/框架模板输入，CI 去除旧 lookup 冒烟但保留既有工具能力验收。

将实际证据与残余更新到 Packet，清理仅用于本次验证的临时产物。本次提交已获明确授权；未经明确授权不推送、不发布。

## 实施责任与已完成反馈

| Owner | 责任 | 当前结果 |
| --- | --- | --- |
| corpus_skills | 六入口、references/assets、共同契约与 Corpus 发布片段 | 完成内容迁移、逐入口指针与语义走查 |
| corpus_boundary | CLI 命令与配置 hard-cutoff、构建解耦、CLI 回归 | 完成，210 项 CLI 测试通过 |
| delivery_docs | 用户文档、持久产品事实、CLI 发布片段 | 完成，18 份文档的 38 个本地目标与片段有效 |
| 主 Agent | 源合同检查、仓库工具、锁文件、CI、集成验收与 Packet | 全量 220 项测试、静态检查与隔离安装验收通过 |

## 最终验证证据

- `pdm lock --check` 通过；锁文件仅同步 CLI 版本、描述及移除 semantic-version。
- `SVC_BASE_REF=HEAD pdm run check` 通过：源 Skill 与链接、Corpus 发布、输出 schema、格式、lint、mypy、七条 import-linter 合同与 220 项测试。相较迁移前 260 项，删除了不再提供的 Corpus CLI 能力测试，并增加源 Skill 与版本合同验证。
- `pdm build -p cli` 生成 16.0.0 sdist 与 wheel；逐项检查归档不含 Corpus、catalog、框架模板或 `_build_inputs`。
- Python 3.12.10 临时目录中从 sdist 独立重建 wheel；无源码路径注入的独立 venv 离线安装 wheel，完成 init plan/apply、healthy status、真实 run 写入可观测文件并退出 0。
- 独立安装中 lookup、upgrade、task init/grow 返回解析拒绝；schema 3 主配置与 overlay 的 status 返回 malformed，字节内容保持不变。
- 既有 `tools/accept_agent_thread.py --slice all` 对同一 wheel 的 inventory、evidence、query、read 全部通过。
- 源路径导航只读实验支持场景选择与按需读取；未验证宿主自动发现和加载、安装布局或统计性能。没有测量迁移前后导航性能提升。

本次临时构建、venv 与项目验证目录已清理。构建归档保留在既有忽略目录 `cli/dist/`。本次迁移已获提交授权，未推送、未发布；无需为当前已约定范围继续添加安装器或宿主适配层。

## 收尾调整

用户要求删除根 `tests/`，已删除其中工具与 Corpus/Skills 测试，同步 pytest、格式与 lint 范围及 AGENTS 说明。自动化测试仅保留 `cli/tests/`；源码元数据、链接、版本与输出 schema 检查仍作为仓库检查工具运行。上述 220 项结果是删除根测试前的记录，最终验证以本节追加的结果为准。用户已授权提交本次修改。

最终 `SVC_BASE_REF=HEAD pdm run check` 通过：仅收集 `cli/tests/` 的 210 项测试，全部通过；格式、lint、类型、依赖边界与仓库检查通过。
