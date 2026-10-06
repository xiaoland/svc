# SVC Skills 分发

目标：让同一份六个自包含 SVC Agent Skills 通过官方发行物、SVC CLI 和通用 Skills 管理器采用，明确发布、安装、升级、移除与项目采用的职责。CLI 不携带 Corpus 正文，所有非平凡任务使用实际 Task Packet 的语义保留。

用户已批准[方案](design.md)并授权实现，另明确选择 MIT；本任务未获提交或发布授权。前序目录闭合修正已提交为 `794966f`，本次工作基于该状态，不恢复根 `tests/` 或 Corpus 测试。

实现采用根 `pyproject.toml` 的统一 Corpus 版本、六个 Skill 的同步 metadata、绑定准确源码 commit 的 ZIP/manifest/checksum，以及独立 CLI 版本。CLI 直接消费官方或离线 ZIP，提供 install/status/check/update/remove/adopt/unadopt，写操作以精确计划执行。安装记录保护本地修改和其它管理器的所有权；采用块与安装文件分别管理。

所有者：skills_release 负责版本与发布工具/workflow；skills_cli 负责安装生命周期服务与必要的 LocalPlan 修复；Primary 负责命令、输出、项目采用、文档和总体验收。一个 Skill 与其记录构成独立事务，跨单元失败保留并准确报告前序成功，不承诺掉电恢复。

完成状态：实现、文档和本地验收已完成，239 个 CLI 测试、独立 wheel/sdist 构建与隔离安装实验通过。真实 GitHub 发布、Claude 宿主发现和模型自动触发未执行，不能由资源闭合或文件安装推导这些结果。

证据入口：[升级与分发调查](inquiry.md)、[第三方管理器与 Codex 发现](manager-verification.md)、[发布工具边界](release-verification.md)、[总体验收](verification.md)。运行和采用合同以 `USER_MANUAL.md`、`docs/deployment/skills.md` 和 `CONTRIBUTING.md` 为权威，本 Packet 保留任务决策与观察。

2026-10-06 版本纠正：用户明确全部尚未发布的改进仍属 v15。当前 CLI 与 Corpus 预备版本统一为 15.0.0；此前任务材料中 16.0.0/16.1.0 的本地快照与构建数字保留为历史观察，不构成已发布版本或后续版本决策。当前版本以权威配置为准，同一未发布开发线不逐次升版。
