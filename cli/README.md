# Sustainable Vibe Coding distribution

This member builds the `sustainable-vibe-coding` Python distribution: the `svc` command and its local development-collaboration runtime. Framework guidance is released separately as six self-contained Agent Skills. `svc skills` installs an explicit official release or offline archive, protects local modifications, and manages project adoption separately from installation. The CLI package contains no Corpus content and builds independently of the parent repository.

The canonical framework source and repository development instructions remain in the workspace root. This file owns only package-index metadata for the independently rebuildable member distribution. The distribution is licensed under MIT and carries its own license notice.

SVC Dev 通过 `dev list`、`dev status`、`dev act` 和 `dev reconcile` 提供独立的开发资源接口。macOS App 是使用同一公开合同的图形入口，不拥有资源配置或执行权限。CLI 18 要求项目配置 schema 5；迁移和生命周期边界见仓库用户手册。
