# macOS App 与 CLI 合同

本文拥有原生 macOS 菜单栏 App 与 SVC CLI 之间的职责、调用、兼容性和生命周期合同。产品承诺见[开发能力](../prd/development.md)，安装与运行方式见 [App 使用说明](../../macos/README.md)，发行流程见 [CONTRIBUTING.md](../../CONTRIBUTING.md#macos-版本与发布)。

App 是 CLI 开发能力的图形客户端。App 拥有用户添加的本机项目目录、界面状态、刷新调度、当前会话的操作回执，以及用户选择的 CLI 路径和 PATH。CLI 拥有 `svc.json` 的解释、能力身份与共享范围、就绪探测、启动、声明式停止、跨进程协调和运行证据。App 不读取私有运行时记录，也不根据端口或历史 PID 推导停止权限；图形界面与终端调用使用同一套 CLI 规则。

## 公开调用与兼容性

App 通过绝对路径启动独立的 `svc` 可执行文件，传递 argv 和明确的项目目录，不经过 shell。当前调用面如下：

| 操作 | 公开命令 | 结果 schema |
| --- | --- | --- |
| 刷新项目 | `svc dev status --repo <path> --json` | 3 |
| 启动一个目标 | `svc dev ensure <target> --repo <path> --json` | 2 |
| 停止一个目标 | `svc dev stop <target> --repo <path> --json` | 2 |

字段的可执行权威源是 [CLI 输出 schema](../../cli/src/svc_cli/data/output-schemas/)；Swift 解码与兼容性检查位于 [DevModels.swift](../../macos/Sources/SVCMenuBar/Models/DevModels.swift)，真实命令边界由 [CLIClient.swift](../../macos/Sources/SVCMenuBar/Services/CLIClient.swift) 实现。App 先校验 `command` 和 `schema_version`，再读取所需字段。命令不匹配、schema 不匹配或必要字段缺失时拒绝结果；刷新失败会清除旧观察，控制请求失败则显示失败回执。不能把解码失败当作未就绪或成功。CLI 在部分非零退出码下仍会返回有效业务结果；是否有可用回执由退出码、JSON 和上述协议校验共同决定。

`dev-status` schema 3 为成功的目标观察增加 `stop.kind`：`exec` 表示有可执行停止声明，`manual` 表示需要手动操作，`absent` 表示未声明停止。错误目标只提供错误，不提供可操作的观察。这个公开字段可供任何 CLI 客户端使用，避免各个客户端重复解析配置；查询本身不执行停止操作，但 readiness probe 可能运行项目声明的命令，因此添加的项目属于用户信任边界。

App 根据最新观察决定按钮是否可用，CLI 在实际操作时重新依据当前配置、能力身份、锁和探测决定是否执行。界面快照不能授予额外权限。App 内以 `capability_id` 串行化同一能力的控制操作；其他 App 实例、终端和 Agent 之间的协调仍由 CLI 完成。

App 的 SemVer、CLI package 版本和每个命令的结果 schema 是三个独立身份。运行时兼容性由命令和结果 schema 决定，不通过 App 与 CLI 的版本号相等来判断。首版 App 0.1.0 随附 CLI 17.0.0：这次 `dev-status` 从 schema 2 升到 3，按当前仓库的版本检查政策要求 CLI package 主版本提升。该政策与 schema 生成检查由 [build_cli_output_schemas.py](../../tools/build_cli_output_schemas.py) 拥有；以后变更应按当时生效的政策评估，不能因为只修改 App 外观就提升 CLI 版本。

## 进程与安装关系

App 的一次刷新或控制请求对应一个 CLI 子进程。CLI 子进程退出后，已经通过就绪证明的开发服务器可以继续运行；退出 App、关闭面板或移除项目都不构成服务停止指令。退出期间尚未完成的启动／停止操作先返回结果，用户也可以取消退出。App 不给控制操作另加短超时，项目声明的执行与就绪超时由 CLI 负责。具体共享执行权威见[执行合同](execution.md)。

App 保存项目目录和用户设置，当前观察及最近操作回执只保存在会话中。CLI 拥有运行证据和日志的实际存储；App 只打开回执给出的日志路径，不扫描私有记录或承诺完整服务生命周期日志。CLI 的存储与恢复边界见[本地执行运行时](../deployment/execution.md)。

App 包不捆绑 Python 或 CLI。源码安装脚本会构建同源 CLI wheel，并放入用户 Library 下按 wheel 摘要隔离的 Python 环境，再把该可执行文件设为 App 的默认路径。用户显式保存的 CLI 路径优先于包内默认值，重装保留设置；若旧的自选 CLI 不兼容，需要在设置中选择配套 CLI。迁移或删除 CLI 环境时必须考虑仍引用它的 App 设置。

macOS 公开发布将 App ZIP 和同一 commit 的 CLI wheel 一起交付，manifest 记录两者的来源与兼容 schema。公开 App 不包含构建机的 CLI 路径，需要用户安装随附 wheel 并选择路径。配套发行保证有一组共同验收的产物，不把 CLI 变成 App 私有接口，也不等于向 PyPI 发布该 CLI；CLI 与 App 继续各自维护版本、changelog 和 release tag。

协议与进程边界由原生合同测试和真实服务生命周期测试覆盖；CD 还会用最终 wheel 重跑原生控制到真实服务的验收。安装、重装、签名和公开包的信任条件由 [macos/README.md](../../macos/README.md) 与 [INSTALL.md](../../macos/INSTALL.md) 拥有。
