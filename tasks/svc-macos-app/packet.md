# SVC macOS 菜单栏 App

2026-10-26：首版实现和本机后台验收完成，当前正在完成开发签名安装、版本管理与 GitHub Release CD。用户已授权实现、直接验收和发布，无需阶段复核；验收不得打扰前台。用户随后明确同意提交并发布，并要求先补齐 durable docs，特别是 App 与 CLI 的关系。文档已补入 Product TDD，准备完成检查后提交和发布。尚未推送或创建公开 Release。

## 当前交付与边界

工作树为 `/Users/lanzhijiang/Development/.worktrees/svc-macos-release/svc`，分支 `feat/macos-release`，基线 `cb3ec472f685043ff76e4cf5ccea4d2214413f05`。本任务源码从原工作区分离，未带入其他任务的 Corpus、CLI 版本策略和 Skills 变化，未覆盖原工作区修改。

开发签名版已安装到 `/Applications/SVC.app` 并后台运行。签名来自本机钥匙串的 Apple Development 身份，私钥未导出。重装入口是 [script/build_and_run.sh](../../script/build_and_run.sh)；使用 `--verify` 构建、安装并后台启动，`--install` 仅安装。显式保存的 CLI 和项目设置保留。

[macos/README.md](../../macos/README.md) 拥有使用与运行合同，[CONTRIBUTING.md](../../CONTRIBUTING.md) 拥有发布流程，[开发能力产品合同](../../docs/prd/development.md) 拥有产品行为。原生源码与测试属于 `macos/`，Python 打包测试位于 `cli/tests/test_macos_packaging.py`。

App 使用 SwiftUI 内容与 AppKit 菜单栏宿主，支持用户添加的本机项目／工作树、状态刷新、启动、声明的停止、访问值和操作日志。CLI 继续拥有配置、探测、进程控制和共享协调。退出 App 不停止就绪服务器，进行中的控制操作完成后再退出；后台安装请求退出时不激活面板。远程控制、批量操作、自动启动和完整日志工作台不在首版范围。

## 版本与发布决定

App 唯一版本源为 `macos/VERSION`，当前 `0.1.0`；构建号取 Git 主线提交计数，包内保留 commit SHA。未提交构建带 `-dirty`，发布检查拒绝脏源码。macOS 独立维护 Towncrier changelog，以 `macos-v<version>` 发布，不复用 CLI 或 Corpus tag。

`dev status` 增加 `stop.kind`，dev-status schema 从 2 升到 3，ensure／stop 仍为 2。当前 main 的合同要求 schema 不兼容变化提升 package major，因此隔离工作树的配套 CLI 为 `17.0.0`。这没有采用原工作区另一个任务尚未提交的版本策略变更。CLI wheel 随预览发布，PyPI 仍由 CLI 自己的发布流程负责。

`tools/macos_app.py` 先构建并验证候选，再正常退出和替换旧 App。替换失败恢复旧包；恢复本身失败则保留备份路径，禁止自动清理唯一旧包。配套 CLI wheel 按摘要安装到用户 Library/Application Support 下的独立环境，同一 wheel 复用，重装不依赖工作树 `.venv`。

`.github/workflows/macos.yml` 在 arm64 runner 验证仓库和原生行为、构建 App 与同源 CLI、再以实际 wheel 验收真实服务。main 的发布记录变更或手动运行触发 GitHub prerelease。发布器核对 commit、tag、完整附件集合和 SHA-256，恢复同内容草稿，拒绝移动 tag 或覆盖不同附件。草稿查询使用分页 Release 列表，避免只返回已发布 Release 的 tag endpoint。

公开包使用 ad-hoc 签名，支持 macOS 14+ Apple Silicon，未公证；它不携带本机 CLI 路径、PATH、调试源码路径或开发证书。尚无 Developer ID 分发身份，不能承诺通过其他机器的 Gatekeeper。

## 验收证据与剩余边界

- 本机严格签名验证通过。重复安装前后 designated requirement、已有偏好导出和配套 CLI 路径一致；没有强杀开发服务器。开发安装在后台启动。
- 原生测试 13 项通过，使用实际安装的配套 CLI；包括 schema 拒绝、进程输出、共享操作、旧结果丢弃、退出等待与取消、真实 HTTP 服务启动／复用／停止，以及实际 NSButton 到 CLI 的完整控制链路。透明测试窗口不接收鼠标，测试禁止激活并断言前台应用保持不变。
- 原生离屏外观证据：[浅色](evidence/panel-light.png)、[深色](evidence/panel-dark.png)。此前观察过真实菜单栏首次展示；Finder reopen、系统菜单栏隐藏／定位、文件选择器和外部打开没有完成全部前台交互，不将离屏证据当作这些交互的验收。
- 隔离工作树最终 `SVC_BASE_REF=HEAD pdm run check` 通过，268 项 Python 测试通过，其中 12 项覆盖打包与发布；格式、类型、导入边界、schema 和 Corpus 检查均通过。两个新工具单独 mypy 通过，workflow YAML 与 shell 语法检查通过。
- 一项既有 telemetry 测试原先读取本机真实 Codex archive，遇到压缩文件失败。现在该测试显式传入临时 home，验收只读取 fixture；没有修改 telemetry 生产行为，该生产读取问题不属于本任务修复。
- 两次预览归档的 ZIP、wheel、安装说明、manifest 和 SHA256SUMS 字节一致；解压后签名验证通过，扫描确认无本机路径，配套 wheel 为 CLI 17.0.0。未提交归档被发布检查正确拒绝。
- 发布器测试覆盖首次创建、草稿重试、已发布附件不变、错误 revision、损坏附件、未声明附件、路径穿越和 tag 冲突；真实 GitHub 只读分页查询已通过。尚未实际运行 GitHub Actions 或公开 Release。

最终归档的摘要、解压后签名、路径隔离及最终安装身份／偏好保留再次通过。独立 advisor 已确认草稿查询和失败回滚两项修复闭合。

下一步：完成文档一致性检查，仅提交本任务变化，通过 PR 与必要 CI 合入 main，跟进 CD 到实际 Release 下载校验。提交与发布均已获授权，不再请求阶段许可。

新增的 [App 与 CLI 合同](../../docs/product-tdd/macos-client.md) 持久保存职责、公开 argv/JSON 边界、schema 兼容、停止权限、生命周期和配套发行关系；README、产品文档、部署导航、App README 和 CONTRIBUTING 已链接到同一所有者。

PR #37 的 Linux 通用 CI 通过。首次 macOS15 runner 有 7 项 HTTPServer 子进程就绪超时；官方 setup-python#1223 记录了同系统 loopback 反向解析延迟。独立进程堆栈确认 getfqdn 阻塞，hosts 映射实验无效且已移除；改用 PDM 安装的同版本独立 CPython 3.12.10，并以独立进程在 10 秒内创建 HTTPServer 验证该前提，然后照常执行全部检查，没有放宽业务超时或跳过测试。远端 macos-v* tag 已加入既有的更新／删除保护。
