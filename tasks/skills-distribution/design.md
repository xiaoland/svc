# SVC Skills Release、分发与采用方案

用户已确认 CLI 不携带 Corpus 正文，CLI 提供 SVC 专属采用与管理，分发内容支持 Vercel Skills、OpenSkills 等主流管理器。六个 Skills 共用当前仓库和一条 Corpus/Skills 发布线，可以选装；每个目录的必需内容自包含，不要求父级文件或其它 Skill。用户已同意明确目标发布、保护本地修改、按实际状态返回，并把文件更新和项目语义采用分开的升级流程。CLI 是否委托第三方工具没有要求；用户已批准以下默认与第一批实现范围，并授权落地。

## 源码与版本权威

将 version.json 的发布版本职责移到根 pyproject.toml，而非根 Python workspace 的 project.version：

```toml
[tool.svc.corpus]
version = "16.1.0"
```

cli/pyproject.toml 的 project.version 继续独立表示 CLI。删除 corpus/version.json 及无人执行的 previous/migration 历史链；已有迁移指南保留，按适用条件与 release notes 提供。发布版本不根据 commit 类型自动推导，沿用已有 Behavioral SemVer 判断。每次可见变化进入既有独立 Towncrier 队列。

六个 Skill 的 metadata.version 表示所属统一发布，不是独立版本源。发布准备时从根配置同步并提交；正式发布检查只核对，不改源码。Git tag 中的目录与 ZIP 对应目录逐字一致；准确源码 commit 在打包时记录到发行清单，避免源文件自指 commit。根 index 是仓库介绍与导航，不属于 Skill 执行依赖。

## Release 与渠道

继续使用 main 集成、release PR 和 corpus-v<version> tag，与 cli-v<version> 分开。正式 tag 与发行附件不重写，修正另发版本。保留 changelog 合并触发发布的现有流程，不为移动版本字段另建发布系统。

每次 GitHub Release 提供精简 ZIP、SHA-256 校验文件、发布说明与必要迁移指导。ZIP 保留六个 corpus/svc-* 目录和发行清单，包含统一版本、源仓库、准确 revision 和 Skill 名称；保留必要许可材料，排除 CLI、tasks、维护者 AGENTS 和开发工具。不生成管理器专用正文。

第三方管理器可以从 Git 源安装一个或多个 Skill；可复现采用使用明确 tag/commit。它们的更新仍遵守各自来源/ref 机制，不能宣称统一的 SemVer 升级合同。CLI、手动和离线采用使用同版本发行附件。CLI 稳定更新选择只查询 corpus-v 发布流，不能把同仓库的 latest CLI Release 当作 Skills 发布。ZIP 不进入 CLI wheel。

发布 workflow 核对配置、metadata、说明、引用与目录闭合，从已提交源码生成附件，检查归档与源码一致，绑定 tag/说明/附件到同一 revision，附件齐全后公开 release。失败重跑补齐同一发布，不能用变更后的内容覆盖现有发行物。检查由仓库工具完成，不恢复根 tests/。

## CLI 安装管理

CLI 直接消费官方发行 ZIP，首轮不依赖 Node、Vercel 或 OpenSkills 命令，也不建立可切换后端框架。成熟管理器是并行采用渠道，而非必需运行依赖。CLI 只管理 SVC Skills，不做任意第三方 Skill marketplace。

默认项目范围、复制安装和当前六个 Skills；支持显式选择 Skill、目标发布、目标宿主，以及显式全局范围。首轮支持 Codex 与 Claude Code；写操作显式选择宿主，可以重复选择，不默认同时修改两处。安装位置遵循目标宿主发现目录，不把绝对路径写进通用 Skill 正文。

安装记录保存实际版本、来源/revision、所选 Skill、scope、位置及安装基线；记录不成为另一套发布版本索引。安装检查发行身份、资源与下载完整性，写后查验结果。已存在的未知来源或另一管理器安装可以观察并用于项目采用，但不静默接管、覆盖或删除。不要修改第三方锁文件来伪造它的安装所有权。命令具体语法在接口设计中定稿。

## 升级与移除

状态、远端升级检查和实际更新是不同动作。更新明确当前来源、目标正式发布、范围与所选 Skill；不隐式追踪 main，不把原生管理器 update 当作跨 release 选择。下载并检查目标后，比较已安装内容与安装基线，未修改才走正常替换；定制或来源冲突先报告，不默认覆盖，不新增通用三方合并。

按实际成功、失败或部分完成报告结果并保持准确安装记录，不能凭底层退出码宣称目标版本已经采用。具体原子范围与恢复机制在 CLI 实现设计中按真实失败边界确定，不提前承诺跨所有宿主/global 事务。

移除仅作用于明确归 CLI 管理且未发生冲突的目标。内容被修改、来源未知或安装归另一管理器时停止该操作并报告。项目取消采用不顺带删除全局 Skills，卸载文件不冒充消费者项目指导已经迁移。

## 项目采用

安装、宿主发现和采用生效分别验证。项目采用建立明确 Agent 可见的 SVC 指导，包括所有非平凡任务的 Task Packet 规则；消费者内容与本地约定归消费者。使用单独采用操作，复用 CLI 现有精确 plan/apply、标记块、过期拒绝和并发变更保护，不改变 init 的工具集成职责。

更新文件后展示适用发布说明与迁移指导；没有具体已授权转换合同就不自动改 AGENTS 或项目资料。采用和取消采用只处理自己的未修改标记块，冲突须保留消费者内容。长期定制放在项目指令或自有 fork；通用管理器的覆盖行为在采用文档中说明。

## 验收与实施顺序

先迁移版本权威、完善发布准备与发行物，再验证 Vercel/OpenSkills 的真实安装，然后实现 CLI 安装/状态/更新检查/更新/移除，最后接入项目采用与取消采用。每一步都保持 CLI 无 Corpus 构建输入与运行时源码回退。

机械检查覆盖版本一致、Skill 内资源闭合、源码与 ZIP 一致、归档身份与完整性。隔离安装验收覆盖选装、固定版本、项目/全局目标以及正式发布选择；CLI 回归仅放在 cli/tests，覆盖内容冲突、其它安装所有权、部分失败的真实状态与消费者内容保护。宿主会话观察独立验证发现与非平凡 Task 触发，不从文件存在推导生效。

## 许可与实施决定

用户已批准全景并选择 MIT。根 LICENSE 是许可正文权威，六个 Skill 与独立 CLI member 保留相同声明副本，保证单目录复制和独立发行仍携带许可。发布准备同步这些副本，发布检查只读核对。

install/update/remove/adopt/unadopt 默认计划，--apply DIGEST 精确执行；status/check 只读。独立安装记录位于实际 skills root/.svc/<name>.json，一个 Skill 与其记录是本地事务单元，运行期失败停止后续项且保留前序成功；掉电或 SIGKILL 后只观察并拒绝覆盖冲突，不承诺自动恢复。宿主路径与正文版本分别观察，真实发现/触发证据保留在任务验证记录。
