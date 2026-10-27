# 实施准备实验

2026-10-27，在 macOS 15.4.1／arm64、Python 3.12、Swift 6.2.3 上核对会改变实施路线的三个前提。仓库 HEAD 为 `13694c0122294fc86cefd6ef83ec5e374dd1311d`，实验读取现有运行代码，本阶段只写任务材料与临时目录。它们不等于 A01–A18 的资源功能验收。

## 等待动作的机械能力

[wait_policy.py](wait_policy.py) 在临时 runtime 中使用现有 ExecutionStore、start_isolated 和 wait_owned。独立 owner 进程安装不转发的信号处理，子进程独立记录收到的信号，第三个进程尝试同一锁。控制者启动后连续发送 SIGINT、SIGTERM、SIGINT，跨过旧 terminate 的三秒升级窗口，最后由测试闸门允许控制者正常结束。

[实际结果](wait-policy-result.json)：owner 收到三次信号，子进程未收到；等待期间锁仍被持有，正常结束后释放，机械记录 exited／0。首次脚本误用了不存在的 point_coordination，尚未启动控制者；更正为现有 write_coordination 后得到上述结果。结论是机械设施足够支持领域 wait 策略，不证明尚未实现的 CLI 已正确处理启动交接、重复信号或崩溃。

```sh
.venv/bin/python tasks/dev-resource-manager/experiments/wait_policy.py > tasks/dev-resource-manager/experiments/wait-policy-result.json
```

## 原生语义控件与不激活前台

[native_controls.py](native_controls.py) 编译 [Swift 实验](native_controls.swift)，在临时目录构建并 ad-hoc 签名独立 `.app`。命令行观察进程先订阅 NSWorkspace 激活事件，再以 `open -g -n -W` 启动该 bundle；GUI 使用产品的 `.accessory` 策略，不调用 activate／makeKey。宿主透明、忽略鼠标，完全不注入全局鼠标键盘。

初始纯 SwiftUI Button 的 NSButton 标识／标题为空。继续读取 accessibilityChildren 与 accessibilityChildrenInNavigationOrder、保留窄协议元素，以及在已有 AX 权限下通过外部进程查询，均未取到目标标识；把窗口移出所有屏幕且保持不透明也没有解决。保留了 [进程内结果](native-controls-in-process-failure.txt)、[透明窗口外部 AX 结果](native-controls-transparent-ax-failure.txt) 和 [屏幕外结果](native-controls-offscreen-ax-failure.txt)。这些结果只排除本机已尝试的隐藏宿主路径，不能声称 SwiftUI 在所有环境不支持语义自动化。

选定一个窄 NSViewRepresentable：NSButton 直接保存入口＋动作键标识，Coordinator 只拥有最新回调。实验先点击 entry-a/install，再由 SwiftUI 将同一视图绑定为 entry-b/install 并点击，独立 effects 数组必须仅为这两个值。初版桥的 perform 命名与 NSObject selector 发生冲突，改为明确的 invokeAction 后通过；实现不得沿用歧义 selector。

[最终结果](native-controls-result.json)：唯一匹配控件为 1，两次效果与入口一致；内外激活事件、键窗口事件均为 0，进程退出码 0。成功路径使用进程内原生按钮，不依赖外部 AX 权限；external_ax_matching_controls=0 表示此路径未调用外部 AX 点击，不是另一项成功证据。window_intersects_screen=true 与透明 alpha=0 同时成立，宿主没有显示在用户屏幕上。实验 App 在结束时自行退出，临时 bundle 随 runner 清理。

```sh
.venv/bin/python tasks/dev-resource-manager/experiments/native_controls.py
```

该证据支持按钮桥和后台验收方法，不覆盖真实资源面板、最终 wheel、视觉布局、安装版本、菜单栏锚定或完整退出流程。A14／A15／A18 仍待候选实现。新界面保持既有菜单栏 shell；若实现改变系统入口，仍触发对应重新验证。

## 异步提交的结果传输

[submitted_result.py](submitted_result.py) 复用 start_isolated，在合并日志保留普通 stdout 与 stderr，同时通过环境变量 SVC_DEV_RESULT_FILE 写独立结果文件。[结果](submitted-result.json) 区分了有效 operation ID 与“命令退出 0 但 JSON 损坏”。这证明无需改变机械日志策略就能传递引用；正式的字段、大小、文件和 URL 验证仍由后续 dev 实现完成。

```sh
.venv/bin/python tasks/dev-resource-manager/experiments/submitted_result.py > tasks/dev-resource-manager/experiments/submitted-result.json
```

没有安装新依赖，没有替换／重启 `/Applications/SVC.app`，没有读取或运行四个真实项目的资源配置，也没有提交或发布。所有通过结论只针对上述隔离前提；失败修复记录与结果一起保留。
