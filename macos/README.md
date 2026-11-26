# SVC 菜单栏 App

SVC Dev 提供菜单栏面板和主窗口，用于查看机器压力、访问项目声明的资源，以及跟踪和控制本机执行。资源操作通过用户选择的 SVC CLI 完成。[产品定位](../docs/prd/development.md) · [App 与 CLI 合同](../docs/product-tdd/macos-client.md)

## 安装和运行

公开预览的安装条件、签名和附件校验见[发行包安装说明](INSTALL.md)。从源码开发需要 macOS 14+、Swift 6、PDM 和钥匙串中的 Apple Development 签名身份。在仓库根目录运行：

```sh
pdm install
./script/build_and_run.sh --verify
```

脚本构建、签名并校验 App，正常退出旧实例后替换 `/Applications/SVC.app`，随后在后台启动。正在进行的控制操作最多等待 30 秒；替换后的签名校验失败会恢复旧包。Codex Run 使用同一入口。`--install` 只安装，`--build-only` 只在 `dist/SVC-build/SVC.app` 中构建。Swift 默认使用两个并发任务，可通过 `SVC_BUILD_JOBS` 设置为 1 到 8。

存在多个开发身份时，以 `SVC_SIGNING_IDENTITY` 指定已有证书的 SHA-1 或完整名称。开发安装使用固定 Bundle ID `dev.svc.menubar`，保留用户偏好。从旧 ad-hoc 包迁移后，系统可能重新询问目录访问权限。[Apple 关于代码签名身份的说明](https://developer.apple.com/documentation/technotes/tn3127-inside-code-signing-requirements)

需要核对安装时，检查实际运行进程的路径以及应用签名。旧工作树的 `dist` 中可能还有同名包。

```sh
ps -A -o pid=,comm= | awk '/\/SVCMenuBar$/'
codesign --verify --strict /Applications/SVC.app
codesign -dvvv /Applications/SVC.app
```

## 选择 CLI

App 1.0.0 配套 `sustainable-vibe-coding` 发行版 `1!1.0.0`。CLI 由用户安装和升级。公开预览附带 `SVC-CLI.zip`，解压得到可独立安装的 wheel。安装步骤见[发行包安装说明](INSTALL.md)。

本机自用可运行 `./script/install_local_cli.sh`，由脚本通过 `uv` 从当前已提交的源码安装 CLI。首次使用时，在 App 设置中选择脚本输出的 `svc` 绝对路径，默认是 `~/.local/share/svc/dogfood/bin/svc`。后续重复运行脚本即可更新这份 CLI，App 重装会继续使用已保存的路径。开发和调试未提交的改动时，也可选择本工作树的 `.venv/bin/svc`。

CLI 路径留空时，App 从所选执行环境的 PATH 查找。项目终端模式读取项目的 zsh 或 bash 登录环境，自定义 PATH 模式使用填写的目录。

开发资源配置使用 schema 5。已有 0.1.0 targets 配置须排空旧操作并迁移。App 会校验实际使用的命令结果版本；各项兼容条件详见[公开调用与兼容性](../docs/product-tdd/macos-client.md#公开调用与兼容性)，迁移步骤见[用户手册](../USER_MANUAL.md#人工迁移-cli-配置)。

## 使用两个界面

- **菜单栏面板**用于速览状态、打开资源地址和执行声明动作。点面板左上角的应用标识或按 ⌘0 可打开主窗口。
- **主窗口**支持按全部项目、Section 或单个项目查看资源与执行，也能浏览全局执行历史。侧栏底部的“＋”用于添加项目或新建 Section。只添加可信目录，刷新可能运行项目声明的自动观察命令。删除分组后，项目回到未分组，资源继续运行。
- **执行与用量**只统计已观测到且身份可验证的进程。点机器压力状态查看 CPU、内存、磁盘和 swap，点项目旁的信息按钮查看已观测项目用量。使用“执行来源”设置可接入 Pi、Codex 和 Claude Code。可用的日志与停止范围由各来源决定。[执行与项目用量](../USER_MANUAL.md#按项目查看执行与用量) · [原生执行接入](../USER_MANUAL.md#接入-agent-原生执行)
- **指令结果通知**显示 App 发起的资源动作与恢复确认回执。“请求已接受”表示控制者已接手，仍需核对结果。点通知可定位原项目和当次回执摘要。在“设置”里的“通知”可查看权限、打开系统设置或发送测试通知。

从 Finder 打开或重新打开会显示主窗口；关闭窗口后 App 继续在菜单栏运行。隐藏所有界面会停止新的周期观察。退出时 App 等待在途资源操作，允许取消退出。关闭窗口或退出 App 后，已就绪服务继续运行。[刷新、资源与执行的职责](../docs/product-tdd/macos-client.md)

## 验证

从仓库根目录执行。使用临时的测试项目，真实生命周期测试会通过配套 CLI 启动并停止专用的 loopback HTTP 服务。

```sh
SVC_TEST_CLI="$PWD/.venv/bin/svc" swift test --package-path macos
SVC_RENDER_DIR="$PWD/dist/ui-evidence" swift test --package-path macos --filter offscreen
pdm run check
```

设置 `SVC_TEST_CLI` 才会运行真实 CLI 生命周期测试。离屏测试用于核对布局，系统菜单栏锚点、窗口激活和通知展示要在运行中的 App 上验证。版本准备与发布见[贡献指南](../CONTRIBUTING.md#macos-版本与发布)。

默认执行环境接入用户的 zsh／bash 项目终端配置，包括已配置的目录及 prompt hooks；周期观察复用准备结果，点击刷新或保存设置后重载。已有自定义 PATH 保留为显式模式，可在设置切换。准备失败／超时会说明项目命令尚未执行，不静默回退；项目动作 env 仍优先，CLI 继承语义不变。启动配置可能执行代码，完整环境不会写入诊断；不自动批准工具的项目信任请求。详见[项目执行环境合同](../docs/product-tdd/macos-execution-environment.md)。
