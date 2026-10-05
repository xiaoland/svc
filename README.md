# Sustainable Vibe Coding

Sustainable Vibe Coding（SVC）是 source-first 的 Agent 协作框架。框架指导以六个 Agent Skills 组织，开发协作 CLI 独立提供执行与观测工具；CLI 不携带 Corpus，也不安装或管理 Skills。

## 开发 SVC

要求 Python 3.11+ 和 PDM 2.28+。

```bash
pdm install
pdm run check
pdm run svc --help
pdm build -p cli
```

框架权威源位于 `corpus/`，从[共同协作契约与导航](corpus/index.md)进入。`corpus/AGENTS.md` 只指导框架维护者；SVC 自身的持久项目事实位于 `docs/`。可安装 CLI 及其测试位于 `cli/` workspace member，仓库专用的检查与发布工具位于 `tools/`。

## 使用 SVC

阅读[用户手册](USER_MANUAL.md)。六个 Skills 分别负责 Task Packet、Methods、Verification、Sub-agents、Specs 和 Taste。Task Packet 适用于所有非平凡任务；Methods 按需组合 Explore、Design 和 Implementation，不构成固定阶段流程。Skill 描述帮助发现入口，正文提供首动作与完成条件，条件引用连接深层指导；这些结构不保证宿主或模型在任何上下文中可靠触发。

## 仓库布局

```text
corpus/                     框架共同契约、六个 Skills 和版本迁移指导
cli/
  pyproject.toml            可安装 CLI workspace member
  src/svc_cli/              Python runtime 和 CLI 静态资源
  tests/                    CLI runtime 测试
  pdm_build.py              CLI 构建 hook，不读取 Corpus
towncrier.{cli,corpus}.toml 独立发布说明配置
.changes/{cli,corpus}/      独立待发布片段
CHANGELOG.md                发布流拆分前的共同历史
tools/                      源检查、发布与验收工具
tests/                      框架源与仓库工具测试
tasks/                      任务工作与留存证据
```
