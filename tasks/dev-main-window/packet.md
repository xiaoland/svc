# SVC Dev 主窗口

## 目标、约束与当前阶段

2026-10-28，用户要求在现有 MenuBar Popover 之外增加 Main Window，随后明确要求切换工作模式。已切换到 Iterative Collaboration（迭代协作），自主形成适量设计并交付可试用增量，不再逐阶段复核；产品目标仍是主窗口与快捷面板共存。必要源修改由这次功能请求授权，沿用本机安装与自由提交授权，不公开发布。

保留菜单栏快速查看与控制入口，主窗口用于持续浏览、管理多个项目和查看完整信息。沿用用户关于原生控件与不过度透明背景的反馈；不增加自动化测试，不制造高负载，不建立新的 GUI 观察宿主。项目和 Section 偏好、资源控制规则及 CLI 独立使用边界继续有效。

## 已核对事实

`SVCMenuBarApp.swift` 使用 AppKit 应用入口，AppDelegate 持有 NSStatusItem、NSPopover 和设置窗口；尚无主窗口。应用为 accessory，普通启动和 Finder reopen 打开 Popover，`--background` 不显示界面。

`MenuPanel.swift` 固定宽 420，提供全机用量、资源／执行分段页面和按 Section 组织的项目资源。`AppStore` 已拥有项目、组织偏好、资源观察、操作、回执及唯一 ActivityStore；视图保存页面和详情展开状态。当前两条轮询循环由 MenuPanel 的 task 与 `panelVisible` 控制，因此直接复制到主窗口会产生调度责任冲突。ActivityStore 能防止单次 monitor 重叠，但不能代替两个界面共享一次刷新节奏。

权威文档是 `docs/prd/development.md`、`docs/product-tdd/macos-client.md` 和 `macos/README.md`。当前只记录候选产品行为；正式决定后才更新这些文档，避免把提案写成已实现事实。

## 本轮实现方向

主窗口提供可调整大小、最小化和系统窗口操作的原生管理界面；Popover 保留快速查看与操作。只有一个主窗口，重复打开将已有窗口带到前台。

主窗口用原生侧栏列出资源入口、Section 与项目，并提供全局执行入口；内容区展示所选范围的资源、操作影响、观察和回执。选择 Section 可以聚合查看其项目，选择项目可以集中查看该项目；未分组来源仍可访问。主机用量保持全局可见，执行页始终包含跨项目及未归属项目的执行。两种界面共用模型和操作事实，导航与展开可各自保留，避免在一个界面操作导航时打断另一个。

在 Popover 提供“打开主窗口”入口；从 Finder 正常打开或重新打开 App 时展示主窗口。`--background`／后台启动保持安静，不抢焦点。打开主窗口后可通过 Dock 和 Cmd-Tab 切换；关闭最后一个管理窗口后回到菜单栏常驻。关闭窗口不退出 App，也不停止资源或执行；退出仍执行既有在途操作等待规则。主窗口记住大小与位置。

窗口采用系统标题栏、工具栏、侧栏、列表与标准控件，不将窄面板等比例放大，也不引入自绘高对比主题。设置仍是独立入口；本轮不增加新资源控制、工作流、终端或全机进程接管。

只要任一资源／执行界面可见，就保持必要观察；都隐藏时停止周期观察。两个界面同开不增加采样频次或并发项目探测；操作及其回执不依赖窗口持续打开。

## 后续与完成判据

实施顺序为：将周期观察移至 AppStore，按界面可见性与资源页需求统一启停；增加 SwiftUI 原生侧栏主界面和 AppKit 单窗口宿主；接入 Popover、系统菜单、正常／后台启动和窗口关闭策略；同步权威文档与 App 独立版本；单任务低优先级构建和既有检查，再复用 CLI runtime 开发签名安装。AppKit 继续拥有既有应用生命周期，不为新窗口另建 SwiftUI App 入口或第二个 Store。

以小规模独立脚本观察两处需求是否共用调度、隐藏后是否停止新请求；使用实际安装 App 的原生 UI 验证窗口、导航和同步，不新增 GUI 观察宿主或自动化测试。关闭界面允许已经启动的只读观察自然结束，不能强杀项目观察脚本，也不能因此启动重叠的新循环。

最终交付须有主窗口和 Popover 共存、重复打开不产生副本、项目／Section／回执一致、关闭界面不停止工作、后台启动不打扰、两界面同开不叠加观察的证据。沿用实际开发签名安装方式，并保留用户偏好；真实体验反馈仍由用户提供，不将工程观察写成人类验收。

## 实施与验证进展

已实现原生 NavigationSplitView 主界面、AppKit 单窗口宿主和工具栏、Popover／系统菜单入口、正常启动与 Finder reopen，以及 regular／accessory 切换。主窗口按当前 Section／项目筛选已有 ProjectView，执行页仍是全局入口。项目选择器复用同一个 ProjectPicker；主窗口使用 sheet，Popover 沿用原选择行为。没有增加新控制权限或改动 CLI。

周期观察已移至 AppStore，两个界面登记各自需求，主机和资源分别保留一个循环；已经取消但仍在等待 CLI 的循环继续占位，不能被第二个循环越过。MainWindowController 用真实窗口可见性、遮挡、最小化和应用隐藏状态更新需求。

App 版本为 0.5.0，CLI 保持 18.1.0。首轮单任务低优先级构建 5.21 秒，包含最终窗口关闭修正的既有原生检查构建 4.61 秒、13 项执行 2.681 秒全部通过。未新增或修改测试。知识引用检查、macOS 版本／changelog 检查与 diff 空白检查通过。

Foundation 独立脚本 `ObserveRefresh.swift` 使用临时假 CLI 和两项注入项目观察，不创建 UI、不调用真实项目脚本。其 [记录](evidence/refresh-observation.json)显示两界面同开只运行一组周期、主窗口单独保持刷新、全是执行页时项目请求计数不变、都隐藏后主机／项目计数不变；快速隐藏重开时主机和项目最大在途均为 1，最后无在途请求。此记录验证调度，不冒充真实窗口可见性和用户体验证据。

下一步复用当前 CLI runtime，开发签名安装并核对实际 App 的窗口、导航和关闭行为；真实检查前不得记为交付完成。

## 首轮真实界面反馈与修正

首个本机候选包为 0.5.0／589d527，开发签名及严格验证通过，CLI runtime 和原偏好、Section 原字节、项目配置均未变化。签名会改变 Mach-O 原始字节；复制两份可执行文件并移除签名后摘要相同，不能用签名前后的文件直接摘要差异误判重新编译。

实际主窗口 AX 支持项目筛选（impl-py 一项）、InKCre Section 聚合（两项）及全局执行页。界面同时暴露缺陷：手工 NSToolbar 的刷新／设置按钮被 NavigationSplitView 的自动工具栏替换，只剩位置不协调的侧栏按钮。用户明确指出界面缺陷，并反对反复通过 computer use 验收。首轮候选不能记为完成或验收通过；已正常退出该 App，未终止资源或受管执行。

停止重复 computer use。先只读判断主窗口、导航和工具栏的单一所有者；按仓库“工程判断因新证据受挑战时使用 advisor”的要求，请只读 advisor 评估继续 AppKit 宿主与迁移 SwiftUI scene 的维护后果，不委托实现、不启动构建或 UI。共享 Store 和已验证的观察调度仍有效，不随窗口呈现修正推翻。后续以原生结构检查和低开销脚本为主，避免边试点边猜测；没有新的证据之前，不声称按钮布局或关闭／后台行为已经验证。

只读 advisor 建议保留现有 AppKit 入口，不扩大为全应用迁移。已根据本机 SDK 核实：hosting 的 sceneBridgingOptions 自 macOS 14 起可用，系统 sidebar tracking separator 需要 fullSizeContentView；SwiftUI scene 的 suppressed launch 则需要 macOS 15，不能直接用于本项目的 macOS 14 基线。采用标准配置修复更符合现有证据：窗口使用 fullSizeContentView／unified，AppKit 保留标题和生命周期，hosting 只桥接 toolbars，导航与全部工具栏项归 SwiftUI。没有增加手工侧栏按钮、坐标补偿、负 padding 或另一套窗口框架。

`InspectWindowLayout.swift` 是一次性原生离屏脚本，构造真实 MainWindowController，禁止激活，不展示窗口，不进入 NSApplication.run，不发送 UI 输入、不运行项目观察。它在 1040 与 740 宽度下输出工具栏结构及完整窗口离屏图后结束。两次均获得系统 sidebar toggle、系统分隔项、刷新和设置四项，windowVisible 与 applicationActive 均为 false，unified／fullSizeContentView 均生效；[结构记录](evidence/window-layout.json)和两张布局图直接支持本次呈现修复。图中是空项目和未采样占位，不作为真实资源数据、系统激活／关闭旅程或完整可访问性验收。已有项目／Section／执行导航的先前观察及未受影响的 13 项检查继续有效。

本机修正版使用 0.5.1 区分首轮被拒绝的 0.5.0；CLI 仍为 18.1.0。已补齐标准隐藏菜单，显式恢复窗口 frame 后再开启 autosave，避免将 hosting 的临时尺寸覆盖用户窗口偏好。后续安装复用单任务构建产物和同一开发签名，不再通过 computer use 重跑整条旅程。
