# nearby-audio：宿主级安装、系统服务与设备资源

2026-10-27 读取本地工作树，HEAD `6c5d04b28e1e4910229b3c3ceef6ff9430367676`，没有已跟踪变更。未启动 App、访问麦克风、查询设备或修改系统服务。

## 已观察事实

| 编号 | 资源与现有控制 | 证据与边界 |
| --- | --- | --- |
| N1 | Mac 构建脚本只允许主仓打包唯一 `/Applications/Shenglin.app`；替换前要求 GUI 已退出，并停止旧麦克风后台；运行脚本校验签名和重复路径后以 `open -g` 打开。 | [构建安装](/Users/lanzhijiang/Development/nearby-audio/scripts/build-mac-app.sh:4)、[启动](/Users/lanzhijiang/Development/nearby-audio/scripts/run-mac-app.sh)。源码工作树不是安装或运行实例的天然边界。 |
| N2 | 麦克风后台由 SMAppService／launchd 管理，GUI 注册它；后台持有实例锁并写入状态，读取时拒绝超过 2 秒的状态。 | [后台定义](/Users/lanzhijiang/Development/nearby-audio/Mac/MicrophoneAgent.swift:5)、[GUI 注册](/Users/lanzhijiang/Development/nearby-audio/MacGUI/AppModel.swift:284)。控制主体是原生应用和系统服务管理器，不是发现 PID 的调用者。 |
| N3 | HAL 驱动构建与安装分开。安装脚本要求 root，校验签名后放入系统 HAL 目录并重启 `coreaudiod`。 | [驱动安装](/Users/lanzhijiang/Development/nearby-audio/scripts/install-mac-driver.sh:4)、[开发说明](/Users/lanzhijiang/Development/nearby-audio/manuals/开发与诊断.md:36)。这是影响主机音频的操作，不是普通开发进程重启。 |
| N4 | iPad 安装器验证设备、签名团队、profile 和安装回执；Windows 安装器以管理员配置 NSSM 服务、持久数据目录、日志、停止宽限和重启策略。 | [iPad 安装](/Users/lanzhijiang/Development/nearby-audio/MacGUI/IPadInstaller.swift:108)、[Windows 服务](/Users/lanzhijiang/Development/nearby-audio/scripts/install-windows-service.ps1)。设备上的安装状态与进程运行状态不同，系统管理器仍拥有生命周期。 |
| N5 | 浏览器扩展有 WXT 开发与构建入口，但禁用自动启动新浏览器，开发说明要求在既有 Helium 加载对应产物以保留 Native Messaging 环境。 | [WXT 配置](/Users/lanzhijiang/Development/nearby-audio/BrowserExtension/wxt.config.ts:6)、[脚本](/Users/lanzhijiang/Development/nearby-audio/BrowserExtension/package.json)、[开发说明](/Users/lanzhijiang/Development/nearby-audio/manuals/开发与诊断.md:32)。启动 watcher 不等于扩展已经加载并可用。 |
| N6 | 本机控制 CLI 经 GUI 的 Unix socket 查询／操作，部分状态包含设备标识与音频业务信息；真实跨设备回归会临时改变服务、授权和麦克风状态。 | [诊断说明](/Users/lanzhijiang/Development/nearby-audio/manuals/开发与诊断.md:41)。本调查未调用它们，不能把诊断或测试命令当作无副作用状态探测。 |

## 对产品判断的影响

N1 支持明确区分源码位置、构建产物、已安装资源与运行实例，不能默认每个工作树可独立启动一份。固定安装路径、bundle 身份和签名会影响开发资源是否可继续使用。

N2 与 N3 支持按控制主体及动作影响区分能力：系统服务和驱动应沿用已有管理入口，普通停止、注销服务、安装驱动、重启系统音频不是同一操作。

N4 与 N5 支持可观察、安装、运行、连接与人工步骤独立存在。界面应能表达“产物已构建，仍需加载／授权”，而不是强行用 ready／stopped 两个状态概括。

音频配对、静音、录音和设备授权是声邻产品行为。将 App 或设备登记为开发资源不等于授权 SVC Dev 执行这些业务动作；资源管理只需承接被明确提供的准备、观察和生命周期能力。

## 残余

没有核验当前安装版本、驱动状态、设备连接或系统授权。本轮源码观察足以证明控制差异，不能证明哪一项应优先做成 SVC 内建支持，也未评估平台适配成本。
