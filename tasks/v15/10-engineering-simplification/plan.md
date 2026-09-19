# 实施计划

1. 盘点 v15 历史兼容面：配置、Corpus、analysis、integration、机器输出与运行中进程合同；区分应删除的成功路径和必须保留的拒绝/安全边界。
2. 分离发布说明、Corpus 发布索引和 CLI 合同，重做当前草稿中混入 Corpus 指南的 CLI 迁移内容。
3. 用 Towncrier 替换 Changie，保留 release PR 合并触发发布，并让 CI/CD 复用同一构建与验收入口。
4. 收敛静态检查与测试入口；补齐 mypy 实际源码覆盖，改善子进程超时、stderr 和失败现场的可诊断性。
5. 验证当前合同、旧输入拒绝、Python 3.11/3.14、wheel 安装、init/status、analysis、double 与 Agent-thread 黑盒行为，再演练 release PR 准备流程但不发布。

当前状态：设计已形成于 [design.md](design.md)，等待 Human 审阅。讨论前草稿仅作为候选差异，不作为既定实现；设计确认前不继续产品源码和工作流修改。
