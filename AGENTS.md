# AGENTS

本仓库是 Sustainable Vibe Coding（SVC）框架的权威源，不是消费者项目。保持框架精简、source-first，并让结构和引用可以机械验证。

## 知识所有者

- 框架目的、共同协作契约和六入口导航：`corpus/index.md`
- Skill 作者与布局规则：`corpus/AGENTS.md`，仅供维护者使用
- Working Methods：`corpus/svc-methods/`
- Task Packet 语义与增长：`corpus/svc-task-packet/`
- 子代理工作安排：`corpus/svc-sub-agents/`
- 声明资格与证据：`corpus/svc-verification/`
- 设计与实施判断：`corpus/svc-taste/`
- 产品、技术、单元、运行时与协调规范：`corpus/svc-specs/`
- Consumer Agent 指导起始形状：`corpus/svc-specs/assets/`
- SVC 自身持久的产品、技术与运行时事实：`docs/`
- Corpus 版本迁移选择与指导：`corpus/migrations/`
- CLI 发布配置、版本、Behavioral SemVer 证据与说明：`towncrier.cli.toml`、`.changes/cli/`、`cli/pyproject.toml`、生成的 `CLI_CHANGELOG.md`、GitHub Releases 和 `CONTRIBUTING.md`
- Corpus 发布配置、版本、Behavioral SemVer 证据与说明：`towncrier.corpus.toml`、`.changes/corpus/`、`corpus/version.json`、生成的 `CORPUS_CHANGELOG.md`、GitHub Releases 和 `CONTRIBUTING.md`
- 消费者 runtime、工具项目集成与 CLI 静态资源：`cli/src/svc_cli/`；测试位于 `cli/tests/`
- CLI 归档构建：`cli/pdm_build.py`；构建与运行不得依赖 Corpus
- 仓库检查与构建工具：`tools/`；自动化测试仅位于 `cli/tests/`
- 任务工作与留存证据：`tasks/`；保留方式由任务决定，任务材料不属于 Corpus

## 开发流程

- Runtime：Python 3.11+
- 环境与命令：PDM 2.28+
- 安装：`pdm install`
- 全量检查：`pdm run check`
- CLI 冒烟：`pdm run svc --help`
- 构建可安装发行物：`pdm build -p cli`
- 阅读框架源：从 `corpus/index.md` 和对应 `SKILL.md` 进入，按需读取 references/assets
- 使用 `rg` 搜索源；除非它们是目标，否则排除 `tasks/`、`.venv/` 和 `build/`
- 根据检查报告中的源文件和 Markdown 目标定位引用错误；缺失的本地路径或片段属于合同失败

## 执行规则

- 所有非平凡任务使用 `corpus/svc-task-packet/SKILL.md`；修改前读取 `corpus/index.md` 与对应知识所有者。
- 实质修改 Corpus 前读取最近的 `corpus/AGENTS.md` 作者合同。
- 只有改变涉及代码结构、边界、数据、权限、命名、抽象或复杂度时，才加载 `corpus/svc-taste/references/implementation.md`。
- 最近的本地 `AGENTS.md` 是附加约束。
- 先修改权威源；仅当消费者形状变化时更新模板。
- Corpus 不放 Python runtime 或构建工具代码；CLI 源与静态资源位于 `cli/`，仓库工具位于 `tools/`。
- 新增层、模板、工具或 Agent 入口必须有独立的所有者、触发条件、消费者和验证路径。
- 正文按语义段落换行，不按固定列宽硬换行；列表、表格和代码保留结构。
