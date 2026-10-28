# 主机压力与受管执行

本文拥有 CLI `activity` 单元的采样、一次性执行与跨进程控制合同。产品目的由[开发资源与执行管理](../prd/development.md)拥有，机械记录由[共享执行合同](execution.md)拥有，存储位置由[本地执行运行时](../deployment/execution.md)拥有。App 通过公开 CLI 读取这些事实，不直接采集进程或读取 runtime 文件。

`dev monitor` 不需要项目配置，不运行项目探测。它读取本用户的 execution 记录，返回全部已读到的活跃执行、仍可观察进程的 owner-lost 来源与最近执行记录，默认历史 20 条、可选 1 到 100 条。损坏或不支持的记录逐项报告，不清理或伪造为空。schema 2 机械状态仍由 ExecutionStore 拥有；查询通过生命周期锁证明 owner-lost，不根据 PID 是否存在接管或重启。记录可能由系统清理，因此清单不代表全机全部进程或永久历史。

psutil 提供约 250 毫秒共享采样窗口的整机 CPU、可用内存与磁盘计数差值。macOS 内存压力来自 `kern.memorystatus_vm_pressure_level`；等级未知时明确报告，不能从内存占比补出正常。系统内存 critical 对应 critical，warning 或 CPU 达 85% 对应 elevated，其余有内存等级时为 normal。等级及建议是产品启发，不是饱和、因果或未来容量证明。指标包含时间、窗口和不可用说明；负磁盘计数差值不转成速率。受管执行通过保存的创建时间验证主进程，再观察当前后代；每轮用量至多观察 64 个根和共 256 个进程，截断时报告不完整。CPU 用量以单核 100% 计，RSS 求和可能重复共享页，后代采样不保证包括已脱离或重新归属的进程。

`dev exec --cwd ... --label ... --source ... --json -- argv...` 是 macOS 上一次显式受管调用。它不合并同名命令、不读取 svc.json、不隐式调用 shell，stdin 为 null，stdout／stderr 分别写日志。前台 CLI 自己持有 ExecutionStore 的 run 生命周期锁，operation 为 managed，coordination key 每次独立。已有 `svc run` 的声明、收敛、终端输入和输出合同不变，也不通过原 follow／inspect 接管 managed 调用。必要元数据发布失败不得启动；进程发布失败时只清理本次仍拥有的组。

`management.json` schema 1 拥有标签、来源、主进程创建时间和组观察。机械 schema 2 仍拥有进程状态及起止事实。`termination.json` schema 1 以 execution ID 绑定请求，包含 terminate／kill 模式、时间与调用方声明的 human／agent／terminal 来源；同用户写入者可信，不把来源字段当身份认证。请求写入有独立短锁，force 不被后来的普通请求降级。终止命令只提交请求，真实 owner 在约一秒的循环中读取，并对本次隔离进程组发送 TERM 或明确请求的 KILL。普通终止不会隐式升级强杀。回执的 requested 不等于已退出；退出结果中 stopped_by 和 retry_allowed=false 表达已应用的终止意图。未发生终止时 retry_allowed 为 null，不授予自动重试权限。

owner 在控制期间不调用 Popen.poll／wait／send_signal，不提前回收直接子进程。保留的 leader PID 防止组标识复用；即使 leader 成为 zombie，也要继续管理仍存活的组员。macOS `proc_listpgrppids` 返回 PID 数、接收字节单位的缓冲区；查询扩容仍截断或失败时保持未知。结束判断先确认未回收 leader 已为 zombie，再取得完整组列表；列表仅含 leader 时才 wait 回收并结算 scope-complete。顺序不能交换，否则活着的 leader 可能在旧快照之后 fork 再退出。不能逐项过滤后用“本次看到的都消失了”代替完整组判据。该 API 内核仍遍历进程列表，因此查询保持低频。接口依据为 [Apple libproc](https://github.com/apple-oss-distributions/xnu/blob/main/libsyscall/wrappers/libproc/libproc.c) 与 [内核实现](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/proc_info.c)。

scope-complete 只证明本次受管进程组已收敛，不证明逃离组的进程、远端操作、文件一致性或业务结果。已释放的资源、submitted 操作和旧调用没有本通道；它们沿用声明控制者。owner 被强杀后显示 owner-lost，禁用终止，不从历史 PID 恢复控制。主进程先退出且组内仍有成员时，机械状态保持 running，组观察为 descendants-running。接口失败为 unknown，保留 owner 和显式强制请求入口。

macOS App 的 ActivityStore 拥有当前快照、请求代次和控制提示；切换 CLI 使旧快照失效。机器概览跨页面展示，超过 15 秒或更新失败的快照标为过期；执行列表独立于项目及 Section 折叠。AppStore 统一拥有菜单栏面板与主窗口的周期观察需求，不启动后台采集服务。至少一个界面可见时刷新机器与执行，至少一个可见界面停留在资源页时才周期刷新项目；都关闭、隐藏或主窗口最小化／被完全遮挡后不继续启动周期请求。主机与项目观察分别调度，避免慢探测阻塞压力刷新；主机请求至多一个在途，项目顺序观察。两个界面同开不创建第二组循环；隐藏后允许在途请求自然结束，快速重开也要等旧循环退出才能替换，不能通过强杀观察脚本中断潜在项目工作。来源、CPU 和内存数据不能被 UI 推导为额外控制权。


## 项目归属与用量观察

CLI 18.2.0 给 `dev exec` 增加可选 `--project`。显式目录规范化后必须存在；缺省时在启动 cwd 及其祖先中寻找最近的 svc.json，只判断文件存在，不解析或执行配置。找不到即未归属。具名 run 和资源动作采用已经解析出的 workspace.root。归属在启动时记录，不随之后项目配置变化重新推断，也不代表实际工作目标或经过认证的 Agent 身份。

activity 拥有 execution 目录内独立 observation.json schema 1，绑定 execution ID，保存 project_path、project_source，以及资源动作可选的 resource_entry_id／resource_key。非 managed 执行保存启动时取得的 process_created_at；managed 仍只由 management.json 拥有该身份。元数据仅在启动路径发布，monitor 不补录或修复；缺失、损坏或创建时间不符就不按历史 PID 采样。可选观察发布失败报告诊断，但不增加杀死 wait 动作或撤销 released 服务的理由。共享 ExecutionRecord schema 2、协调指针和控制协议没有增加字段，旧 CLI 可继续读取机械记录；观察归属从不授予终止权限。

monitor 先从全部记录建立可验证的观察集合，再限制最近结束执行的展示条数。根仍存活且身份匹配的 released 服务不会因超过 20 条历史而丢失用量，作为 resources 返回，执行行仍保留 released 语义且不能终止。owner-lost 根若仍可观察，也不受历史条数限制；它计入当前观察来源，状态仍为结果未知，不能变为可终止或已成功结束。根结束后不从历史进程组接管脱离的后代。受管 owner 仍持锁、根身份仍有效时，可以从其保留的进程组观察已重新归属父进程的 worker；查询组成员不构成新控制权限。查询本身会经过操作系统进程列表，不宣称完全没有系统扫描。

每个进程以 PID 和创建时间标识，采样前先建立唯一集合，再读取一次 CPU 基线与计数；重叠成员优先归最近的已登记执行根，不能同时计入外层项目和内层项目。无法消除的歧义明确报告并不重复计费。先按执行聚合，再按 project_path 聚合；共享服务归实际启动来源，不向所有引用项目复制用量。统计只覆盖可验证的本机进程，不包含容器内部、远端、绕过 SVC 启动的程序及已失去关联的后代。旧记录没有观察来源时保留未知，不根据进程名、端口或当前 cwd 补出历史归属。

进程内存优先采用 `proc_pid_rusage(RUSAGE_INFO_V2)` 的 phys_footprint，保留 RSS 原字段；footprint 包含系统计入的压缩内存，但进程之和不等于结束项目可释放的物理内存。进程磁盘读写及 pageins 由同一接口的累计量在相同进程身份下取差；采样失败或计数倒退返回 null，不能转成零。CPU 仍按单核 100% 表示。usage 的 complete／issues 说明本次选中集合是否完整读到，不承诺全项目或全部未来后代都已覆盖。

主机使用 host_statistics64 的 swapins／swapouts 计算真实 swap 页面速率，用 host_page_size 返回的页大小解释计数；压缩内存为 compressor_page_count 乘页面大小。pageins／pageouts、compressions／decompressions 分别返回，均以页/s 表达活动，不把压缩前页面量称为物理磁盘吞吐。psutil 7.2.2 的 macOS swap_memory.sin／sout 实际使用 pageins／pageouts，所以只复用其 swap used／total，不使用那两个字段计算真实 swap。主机 swap 不分摊给项目，项目 pageins 也不叫 swap；swap 已用量本身不决定当前压力，磁盘吞吐也不表示饱和度。压力等级仍是 CPU／系统内存的启发，没有新增未经验证的 I/O 阈值。

这些接口不需要 task port、地址空间遍历、root 或额外的隐私权限。实现依据为 [Apple rusage 接口](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/resource.h)、[VM 统计结构](https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/mach/vm_statistics.h)、[psutil 7.2.2 macOS 实现](https://github.com/giampaolo/psutil/blob/release-7.2.2/psutil/arch/osx/mem.c)及 [Apple 内存压力说明](https://support.apple.com/guide/activity-monitor/view-memory-usage-actmntr1004/mac)。

公开 dev-monitor 结果升级为 schema 2，扩展 pressure、execution usage、project_path／project_source，并新增 projects 和 resources；dev-exec／terminate schema 1 不变。结果形状变化必须推进自己的版本，不能因为旧 Swift 解码器忽略额外字段就沿用严格旧 schema。App 与 CLI 使用同一项目用量模型，App 只决定显示范围，不另行扫描进程或汇总一份来源不明的全机用量。
