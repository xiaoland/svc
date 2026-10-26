# SVC 菜单栏 App

这个原生 macOS App 管理用户添加的本机 SVC 项目与工作树。从 Finder 打开时展示面板；开发安装默认只在后台启动。面板显示服务就绪状态，提供逐项启动、停止、访问地址与操作日志入口。项目配置和服务器生命周期仍由 `svc` CLI 负责。跨单元职责与兼容规则见 [App 与 CLI 合同](../docs/product-tdd/macos-client.md)。

需要 macOS 14+、Swift 6 工具链，以及支持 dev-status schema 3 和 dev-ensure／dev-stop schema 2 的 SVC CLI。从仓库根目录执行：

```sh
pdm install
./script/build_and_run.sh --verify
```

应用稳定安装到 `/Applications/SVC.app`，Codex Run 使用同一入口。`--install` 安装后不启动；`--build-only` 只在 `dist/SVC-build/SVC.app` 构建，不退出当前 App。安装先完成构建、签名和校验，再请求旧 App 正常退出，等待最多 30 秒；不强杀服务操作。替换后的签名校验失败时恢复旧包。新 App 通过后台模式启动，不主动展示面板或夺取焦点。

本机安装从钥匙串选择唯一的 Apple Development 身份；存在多个身份时，通过 `SVC_SIGNING_IDENTITY` 指定证书 SHA-1 或完整名称。证书私钥始终留在本机。签名使用固定 Bundle ID `dev.svc.menubar`，重装保留当前用户设置。

首次使用时选择包含 `svc.json` 的项目目录。添加的目录会执行项目声明的 readiness probe（包括 exec probe），因此只添加自己信任的项目。添加项目不执行启动或停止动作。项目列表保存在当前用户的 `dev.svc.menubar` 偏好中；配置无效或路径失效时直接显示错误。

安装脚本同时构建配套 CLI wheel，并安装到 `~/Library/Application Support/SVC/runtimes/<wheel 摘要>/` 下的独立 Python 环境。同一个 wheel 复用已有环境；CLI 源码变化产生新环境，旧环境保留以便现有设置继续使用。App 默认引用本次配套环境，不再依赖工作树的 `.venv`。需要本机 Python 3.11+、PDM 和可用的依赖下载源；App 不捆绑 Python。

设置中的 CLI 必须是可执行文件的绝对路径。显式保存的 CLI 路径优先于包内默认值，重装不会覆盖它；自定义 CLI 需要满足相同 schema 合同。命令搜索路径 PATH 默认来自本机构建环境，可在设置中调整。App 不读取登录 shell 配置，项目需要的环境变量由 SVC 配置声明。

App 的唯一版本源是 `VERSION`，构建号来自当前 Git 的主线提交计数，包内记录完整源码 revision；未提交构建标记为 `-dirty`。设置窗口显示版本与构建号。发布流程和版本准备见根目录 `CONTRIBUTING.md`，公开预览安装条件见 `INSTALL.md`。GitHub 附件是 arm64 的 ad-hoc 签名预览，未公证，与本机开发签名安装分开构建；公开包不带本机 CLI 路径、PATH 或调试源码路径。

服务状态表示探测到的可用性，未就绪不等于进程不存在。启动会复用已健康的服务；停止只执行项目声明的 cleanup。手动停止或未声明停止的目标没有自动停止按钮。仓库或主机共享的服务明确显示范围，并在本 App 内按 capability_id 互斥控制；跨进程协调继续由 CLI 负责。

关闭面板或退出 App 不停止已经就绪的服务。正常退出时若启动／停止尚在进行，App 会等待结果，并允许取消退出。最近的操作回执仅保留在当前会话；日志入口仅代表对应操作的已有文件，不保证服务全生命周期的输出，也不扫描私有 runtime 存储。

运行原生测试及真实服务生命周期检查：

```sh
SVC_TEST_CLI="$PWD/.venv/bin/svc" swift test --package-path macos
SVC_RENDER_DIR="$PWD/dist/ui-evidence" swift test --package-path macos --filter offscreen
pdm run check
```

`SVC_TEST_CLI` 指向本次待验证 CLI。生命周期测试使用临时目录和临时 loopback HTTP 服务，通过声明的停止请求清理。未设置该变量时只执行不依赖真实 CLI 的测试。原生按钮验收在透明、不接收鼠标的测试窗口内调用实际 NSButton，测试程序禁止激活，并断言前台应用未改变。离屏渲染不创建可见窗口，输出浅色／深色 PNG；它是渲染证据，不代表系统菜单栏锚定或人工体验。原生代码与测试位于 `Sources/SVCMenuBar`、`Tests/SVCMenuBarTests`；Python 测试仍由仓库 `cli/tests` 管理。

Swift 的 `CLIClient` 只通过 argv 调用公开命令，不经 shell，不解析 `svc.json` 或私有运行时记录。`AppStore` 持有项目、操作和请求代次；修改配置、控制操作与项目移除会使旧刷新失效。界面只呈现这些状态。AppDelegate 独占 NSStatusItem、NSPopover 和设置窗口；菜单栏宿主采用 AppKit，以公开 API 控制首次展示、Finder reopen 和显隐轮询，内容使用 SwiftUI。标准编辑菜单为设置输入框提供复制、粘贴与全选快捷键。子进程 stdout／stderr 使用临时文件，避免大量输出或已释放服务器继承描述符导致的管道等待。控制操作使用 CLI 自身的超时，不被 App 的短超时打断。
