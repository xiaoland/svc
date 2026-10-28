# App 使用用户安装的 CLI

用户在侧会话明确要求 App 依赖用户安装的 CLI，找不到时引导 GitHub latest release 或 PyPI，不再自动创建 App 私有 Python 环境。此前“最多 17”的说明是对不兼容变更至少进入 17 的判断，并非 17 的硬上限；公开 macos-v0.1.0 的 CLI 17.0.0 保持发布事实。

本次只修改 CLI 发现、安装工具和相关说明，不改 CLI 版本或主线程正在实施的 harness 能力。用户随后明确授权提交本次改动，提交不包含主线程的其他工作。主线程正在修改部分相同文件，本次以窄修改保留其内容；安装验收使用隔离副本，避免把未完成的主线程实现部署到本机。

验收包括自动 PATH 查找、明确路径优先、旧私有路径迁移、缺失时可访问的安装链接，以及 App 安装不再安装 CLI。使用有限脚本、原生构建和既有检查，不启动 UI 自动化观察或真实 harness 任务。

当前：本次调整完成，已安装 App 0.2.0 build 82，并在后台启动；本次提交只保存此次改动，不发布。主线程的 harness 源修改保留，当前工作区也已通过原生构建。本机交付通过隔离副本只采用本次变更，源码变更由本次 Git 提交保存。

App 不再读取安装器提供的默认 CLI／构建机 PATH，默认使用用户 PATH，包含 mise shim。设置允许留空自动发现，显示实际路径并提供重新检测；主窗口、面板和设置含 GitHub latest release 与 PyPI 入口。CLIClient 每次解析所选安装，显式无效路径不会回退到另一版本。旧私有路径恢复为自动查找，其余路径保留。macos_app.install 不再构建 wheel、创建 venv 或安装包；公开归档仍可以提供供用户手动安装的独立 wheel。

本机系统 CLI 使用用户管理的 ~/.local/share/svc/local-cli/18.2.0，mise 18.2.0 链接已从 App Library/runtimes 改到该目录，版本名与实际版本一致。17.0.0 已随 macos-v0.1.0 公开，schema 5 的不兼容变化按现有兼容基线进入 18；本次未改主线程已在编辑的 CLI 版本字段。用户的“最多 17”已澄清为至少需要进入 17，并非硬上限。

验证结果：路径边界脚本覆盖查找顺序、明确路径优先、缺失、目录、相对 PATH 和旧私有路径识别；原生 Store／Client 脚本验证偏好迁移、明确路径保留、缺失指引，并经 mise shim 完成真实 dev monitor 解码。既有打包检查 13 项、既有 Store 检查 4 项通过；未添加自动化测试，删除已失去对象的私有环境复用用例。ruff lint／format、文档链接检查和 git diff --check 通过。安装包无 SVCDefaultCLIPath／SVCDefaultSearchPath，codesign --verify --strict 通过，TeamIdentifier 为 7J9DJNJ782，进程正常运行。没有使用 computer use 或持续 UI 观察；安装链接的实际点击体验未作人工确认。

持久说明同步于 docs/prd/development.md、docs/product-tdd/macos-client.md、macos/README.md、macos/INSTALL.md、README.md、CONTRIBUTING.md 和 MACOS_CHANGELOG.md。旧私有环境保留在磁盘以免破坏已有调用，但 App 已不再依赖它。
