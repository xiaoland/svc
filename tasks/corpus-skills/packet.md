# Corpus Skills 改进

目标：将 Corpus 重组为六个 Agent Skills，让 Agent 从当前任务识别适用指导、按需加载并有效执行；CLI 不再携带 Corpus。

已确认拆分为 Task Packet、Methods、Verification、Sub-agents、Specs、Taste；Methods 合并 Explore、Design、Implementation。Task Packet 仍对所有非平凡任务触发。先拆分，再逐入口改善发现、加载与执行；正文按语义段落换行。安装边界暂不讨论。

本阶段的调查与设计收敛已完成，用户已明确授权实施，源码修改与集成验收已完成。本次提交已获用户明确授权；推送和发布仍需明确授权。

完成条件：六个 Skills 的规范、参考与模板归属完整，共同协作契约可到达；代表性场景证明指导能适时加载并支持具体行动；获实施授权后，完成 CLI 解耦、契约与文档同步，验证 CLI 在没有 Corpus 的构建和安装环境中可用。

当前事实：前一批修复已分别提交为 `d43f6f4`、`e8701ec`，260 项测试与 sdist→wheel 构建通过。这是迁移前的基线证据，不是新方案的验证。根共同契约、六入口内容归属与分段实施路线已收敛。

兼容范围已确认：下一大版本移除 lookup、upgrade、task init/grow；采用 schema 4，旧配置按 hard-cutoff 明确拒绝，不保留兼容入口或自动迁移。人工迁移说明要求保留其余内容，并同时处理主配置与存在的 overlay。

当前交付：六入口与内容归属、发现与条件加载指针、CLI 解耦、schema 4 hard-cutoff、迁移说明、独立版本 16.0.0 和 CI 验收已完成。详细证据见 [实施路线](plan.md)。源码与验收已完成，本次提交已获授权，安装和分发保持在当前范围之外。

- [已确认决策](decisions.md)：保留用户确认的范围，避免把推荐方案误作已接受决定。
- [实现设计](design.md)：权威源、六入口合同、内容归属、CLI 边界与验证场景。
- [实施路线](plan.md)：有边界的改变与验证要求。
- [调查证据](inquiry.md)：导航抽查、matt-skills 参考和当前 CLI 依赖。
