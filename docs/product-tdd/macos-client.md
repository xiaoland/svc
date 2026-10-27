# macOS App 与 CLI 合同

本文拥有 SVC Dev 图形入口与程序化入口之间的职责、公开协议和生命周期合同。产品定位见 [开发资源管理](../prd/development.md)，使用与迁移见[用户手册](../../USER_MANUAL.md)，发行流程见[贡献指南](../../CONTRIBUTING.md#macos-版本与发布)。本文描述 CLI 18.0.0／App 0.3.0 的源码合同；旧版 App 0.1.0／CLI 17.0.0 使用 targets 合同，不能混用。安装和公开发布是独立的交付步骤，不能由源码版本推断。

App 与 CLI 是同一产品能力的两个入口。App 拥有项目来源偏好、呈现、刷新调度、当前会话回执及 CLI 路径和 PATH；CLI 拥有配置解释、资源身份、观察、声明动作执行和跨进程协调。项目脚本或实际控制者拥有资源内部的初始化、数据清理、权限和异步操作生命周期。App 不直接读取配置和私有 runtime，也不根据端口或历史 PID 推导权限。

## 本机项目分组

App 0.3.0 增加单层 Section，属于 App 的来源组织能力，CLI package 仍为 18.0.0。原 `projects` 路径数组继续拥有项目来源与项目顺序；UserDefaults 的 `projectSections` Data 保存 JSON schema 1，包含有序的 `sections`（id、name、collapsed）及 `assignments`（项目路径到 Section UUID）。一个项目只保存一个归属，组内沿用项目顺序，不生成资源副本。

缺少该偏好时按全部未分组读取，保留原配置。读取时验证版本、名称、唯一 Section ID 和归属目标；不在现有项目列表中的路径归属会被剔除。无法解码或合同无效时保留原始值、显示错误并禁用分组编辑，项目仍可从原来源使用，不能用空分组覆盖损坏数据。写分组由 AppStore 统一负责，不保存观察快照或执行状态。

Section 的创建、重命名、排序、移动和折叠不使项目请求代次失效。删除 Section 只解除归属，控制仍按协调 ID 互斥，回执仍按 entry ID 保存并绑定项目路径。运行提示根据在途操作的项目路径和资源协调 ID 派生，项目暂时无法刷新时也不丢失在途提示。重新添加已有项目会展开并定位原入口，不重复添加或自动改组。

## 公开调用与兼容性

App 通过绝对路径启动独立 CLI，以 argv 传入项目目录，不经过 shell。命令结果的权威是[公开输出 schema](../../cli/src/svc_cli/data/output-schemas/)，客户端边界是 [CLIClient.swift](../../macos/Sources/SVCMenuBar/Services/CLIClient.swift) 与 [DevModels.swift](../../macos/Sources/SVCMenuBar/Models/DevModels.swift)。

| 操作 | 命令 | 结果 schema |
| --- | --- | --- |
| 声明及已有执行事实 | `dev list [resource]` | 1 |
| 默认观察或指定方面 | `dev status [resource] [--observation key]` | 4 |
| 明确动作 | `dev act <resource> <action> [--expected-digest digest]` | 1 |
| 恢复确认 | `dev reconcile <resource> --execution id --acknowledge-unknown` | 1 |
| 同名动作便捷入口 | `dev ensure/stop <resource>` | 3 |
| 工作区身份 | `dev identity` | 3 |

以上调用都支持 `--repo`、`--json` 和 `--json-schema`。根 status 结果 schema 为 4，init 结果仍为 4；配置 schema 5 与这些结果版本相互独立。App 校验 command、schema 和必要字段，拒绝不兼容或损坏结果，不能造出成功或未就绪。非零 CLI 退出也可能携带有效回执。

App SemVer、CLI package 版本及逐命令结果版本独立管理。App 0.3.0 沿用 0.2.0 的 CLI 18.0.0 合同；18.0.0 的 CLI major 对应配置、公开结果和控制行为的不兼容变化。CLI 17.0.0 已作为 macOS 0.1.0 的公开附件交付，即使未发布 PyPI，也属于兼容性基线。基线选择由 [build_cli_output_schemas.py](../../tools/build_cli_output_schemas.py) 拥有。

## 进程与安装关系

一次请求对应一个 CLI 子进程。App 不额外给控制请求加短超时；退出等待在途操作，用户可取消退出，取消退出不取消动作。就绪释放后的服务不随 CLI 或 App 退出；移除来源和关闭面板也不是停止指令。观察和会话回执不作为下次启动的新鲜事实；运行证据由 CLI 保存，App 只使用公开回执中的日志路径。

App 不捆绑 Python 或 CLI。源码安装构建同源 wheel，在用户 Library 下按 wheel 摘要建立隔离环境，将其路径设为默认值；显式保存的 CLI 路径优先，重装保留偏好。公开发布交付同 commit 的 App ZIP 和 CLI wheel，manifest 记录版本、来源和四个 App 调用协议。公开包不含构建机路径；安装者选用配套 wheel。配套发行不使 CLI 成为 App 私有接口，也不自动发布到 PyPI。安装和信任条件见 [macOS README](../../macos/README.md) 与 [INSTALL](../../macos/INSTALL.md)。

## 资源合同

### 声明与身份

配置 schema 5 使用项目内的 `dev.resources` 替换固定 `dev.targets`。`svc.json` 与同版本 `svc.local.json` 共同形成一份有效声明；不新增项目外登记库或后台服务。资源至少提供观察、访问或人工／自动操作之一，包含具名观察、具名动作和明确关系。五类控制特性可以组合，不对应五种执行器。App 保存项目来源偏好，CLI 独立按 `--repo` 解析项目；资源作用位置可以是远端或设备。

入口身份由所选项目／工作树与资源键确定。控制协调身份沿用当前 namespace、scope、scope ID 与资源键生成规则，直接迁移同名同范围资源时保留原锁边界。实际观察到的实例身份由控制者或探测提供，未知时不推断。URL、PID 或显示名相同都不构成自动合并依据。

共享 owner 只能显式引用另一项目中的直接资源声明，不允许引用链或环。引用提供共享协调身份，不继承 owner 的动作或权限，也不自动执行其观察和依赖。请求保留所选入口及其声明，控制者仍可拒绝。owner 无法解析时拒绝共享控制，不退回本地锁；独立观察和访问可以继续返回并说明关联错误。普通关系不产生控制顺序。本机协调不承诺跨用户、跨主机或项目脚本直接调用的互斥。

### 观察与动作

观察按具名方面分别返回结果、来源、检查时间、错误及可选值和实例。控制者的数据时间与 SVC 检查时间分开，过期观察不能满足动作完成条件，单项失败不抹去其它项。HTTP／TCP／exec 是观察手段；不可达不独立证明停止。exec 明确选择退出码格式或版本化 JSON，退出码格式约定 0 满足、1 不满足、其它为观察失败，JSON 格式表达 `satisfied / unsatisfied / unknown` 及可选显示值、说明、数据时间和实例身份。默认刷新只调用声明为自动观察的入口；任意项目脚本不因此获得无副作用保证。

动作具有稳定键、意图、作用对象、控制特性、数据影响与完成合同。效果缺失保持未知，人工入口返回明确步骤，不能被客户端补成自动操作。自动完成方式为：`exit` 等有限命令结束并检查可选正向完成条件；`ready` 取得就绪和所需实例证明后释放本次拥有的长驻进程；`submitted` 只确认实际控制者已接受请求。最后一种方式要求控制者拥有后续身份、冲突处理和生命周期，本机锁仅保护提交过程。回执分别表达请求、执行、完成条件和各项最终观察，不能以命令退出或 readiness 为 false 推导数据已保留或资源已停止。

submitted 默认使用声明的退出码合同，0 仅表示接受请求。需要返回动态操作引用时，动作显式选择 `operation-json`；控制者通过 `SVC_DEV_RESULT_FILE` 写入本次执行的独立结果文件，结构为 `{"schema_version":1,"operation":{"id":"控制者操作ID","url":"可选访问地址"}}`。不从合并日志提取 JSON。该通道要求严格字段和类型、至多 64 KiB 的普通非链接文件，以及沿用访问入口许可规则的 URL。命令退出 0 但约定结果缺失或损坏时保留真实退出事实并报结果无效；实际提交可能已发生，不能自动重试或声称资源操作完成。

有限命令的 `wait` 策略在启动后不因 SIGINT／SIGTERM 或客户端等待期限终止动作，保持协调所有权直到真实结束；启动前取消不再启动动作。`terminate` 只适用于声明可中断的动作，仅能终止本次仍拥有的进程。`ready` 也只用于未就绪时可安全终止本次启动的情况。App 不另加短控制超时，无取消能力时不提供虚假的取消成功；沿用等待操作后退出或取消退出。没有独立后台托管承诺。

### 协调与恢复

同一协调身份上的控制请求互斥。有限动作不缓存历史成功，遇到竞争返回 busy，不隐式排队。ensure 式动作通过正向条件收敛，只能加入同入口、同动作、同解析意图的在途执行；跨入口或相同 argv 本身不证明等价。查看后执行的请求绑定有效声明摘要；CLI 在锁内重新解析入口、owner 和动作，协调键或摘要变化时拒绝替换执行。join 另行核对请求与在途快照。摘要覆盖解析到的声明和执行输入，不冻结外部脚本字节。

机械进程退出与 dev 动作结算是两个事实。动作保持 ExecutionRecord schema 2，以 `operation="act"` 区分；dev 补充记录按 execution ID 保存入口、动作、摘要、pending／settled／owner-lost 阶段和回执。持锁重载、检查旧未决事实后，先写机械记录及 pending 元数据，再发布协调指针，最后启动；必要记录发布失败不得启动。完整回执与 settled 必须原子保存，join 等领域结算而不是仅等机械退出。失去生命周期锁时仍 pending 即构成 dev owner-lost，即使机械已经 exited／released 也持续阻断，并保留机械真实结果。旧 ensure／stop 记录可以没有新元数据，新 act 记录缺失或损坏元数据不能假定为旧格式。

未解决的 owner-lost 持续阻止同一边界上的后续变更，查询和观察仍可用。恢复必须引用当前未决 execution ID 并明确承认原结果未知、重试可能重复；恢复只解除阻断，不执行动作、不改变原未知结果，也不证明原进程结束。确认在锁内检查并先原子记录，再允许另一明确请求覆盖协调指针；确认不把 dev owner-lost 改成 settled，不能根据历史 PID 接管。runtime 留存条件见[本地执行运行时](../deployment/execution.md)。

### 接口、呈现与迁移

共同公开入口是 `dev list`、`dev status`、`dev act <resource> <action>` 和 `dev reconcile <resource> --execution <id> --acknowledge-unknown`。list 解析声明及已有执行事实，不运行 provider probe；status 获取观察，不执行控制动作。ensure／stop 仅在对应明确动作存在时可用，不任取第一个动作。reconcile 无确认参数时只返回未决事实。最终字段由同步更新的公开 schema 与客户端模型强制，App 不解析配置或私有执行记录。

list／status 的 0 表示请求取得可判定结果，不要求所有条件满足；未知或部分观察失败返回 3 并保留有效项。act 的 0 表示声明的完成合同成立，submitted 仍只表示接受；busy、人工操作、声明过期、条件未满足和未解决 owner-lost 返回 3，配置或执行错误返回 4，真正取消／终止返回 130。wait 收到信号后正常完成时保留实际完成结果，退出码不能代替结果对象。

App 按来源展示资源及具名状态，详情承载实例依据、关系、动作影响和回执，较强后果在执行前可见。观察按入口与方面保存，操作按协调身份互斥，回执保留所选入口和 execution ID；共享身份不合并权限和反馈对象。旧刷新不能覆盖操作后状态，切换 CLI 或移除来源使对应观察失效。混合资源不使用统一就绪计数，也不把所有实现细节堆在列表中。

原生资源行与详情继续使用 SwiftUI，Store 保持唯一的界面状态所有者。资源动作按钮使用窄 NSViewRepresentable 承载 NSButton 的稳定入口／动作标识、名称、启用状态和回调；更新视图时同步标识与回调，不另建动作注册表。它允许隐藏宿主直接按语义触发同一个产品控件，菜单栏锚定和用户主动打开行为保持原结构。此实现选择只解决本机隐藏宿主未暴露 SwiftUI 动作标识的验收接缝，不表示整个界面改用 AppKit。

配置遵循 current-only 人工迁移，不新增双读或旧字段别名；现有 `${dev.target}`／`SVC_DEV_TARGET` 脚本接口继续表示所选资源键。先保持资源键、scope 和 host_key 迁移声明形状；引入 owner、改名或改变 scope 属于协调身份变更，必须先完成旧边界的活跃或未解决执行。没有持久身份映射时，不承诺任意热改身份下的跨键互斥。旧客户端的 follower 可能取得锁后继续旧快照，因此停止发起旧控制并排空全部旧 owner／follower 后才开放新版控制。保持相同协调键只保证旧 owner 持锁时新请求不并行，不能把新版 owner-lost 规则强加给旧等待者；不能通过强杀旧调用伪造已排空。公开结果和 App 一起迁移，CLI、App 和结果 schema 仍分别管理版本，不兼容组合明确拒绝。
