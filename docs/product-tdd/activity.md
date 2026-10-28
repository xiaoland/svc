# 主机压力与受管执行

本文拥有 CLI `activity` 单元的采样、一次性执行与跨进程控制合同。产品目的由[开发资源与执行管理](../prd/development.md)拥有，机械记录由[共享执行合同](execution.md)拥有，存储位置由[本地执行运行时](../deployment/execution.md)拥有。App 通过公开 CLI 读取这些事实，不直接采集进程或读取 runtime 文件。

`dev monitor` 不需要项目配置，不运行项目探测。它读取本用户的 execution 记录，返回全部已读到的活跃执行与最近结束的执行，默认历史 20 条、可选 1 到 100 条。损坏或不支持的记录逐项报告，不清理或伪造为空。schema 2 机械状态仍由 ExecutionStore 拥有；查询通过生命周期锁证明 owner-lost，不根据 PID 是否存在接管或重启。记录可能由系统清理，因此清单不代表全机全部进程或永久历史。

psutil 提供约 250 毫秒共享采样窗口的整机 CPU、可用内存与磁盘计数差值。macOS 内存压力来自 `kern.memorystatus_vm_pressure_level`；等级未知时明确报告，不能从内存占比补出正常。系统内存 critical 对应 critical，warning 或 CPU 达 85% 对应 elevated，其余有内存等级时为 normal。等级及建议是产品启发，不是饱和、因果或未来容量证明。指标包含时间、窗口和不可用说明；负磁盘计数差值不转成速率。受管执行通过保存的创建时间验证主进程，再观察当前后代；单次用量至多采样 256 个进程，截断时报告不完整。CPU 用量以单核 100% 计，RSS 求和可能重复共享页，后代采样不保证包括已脱离或重新归属的进程。

`dev exec --cwd ... --label ... --source ... --json -- argv...` 是 macOS 上一次显式受管调用。它不合并同名命令、不读取 svc.json、不隐式调用 shell，stdin 为 null，stdout／stderr 分别写日志。前台 CLI 自己持有 ExecutionStore 的 run 生命周期锁，operation 为 managed，coordination key 每次独立。已有 `svc run` 的声明、收敛、终端输入和输出合同不变，也不通过原 follow／inspect 接管 managed 调用。必要元数据发布失败不得启动；进程发布失败时只清理本次仍拥有的组。

`management.json` schema 1 拥有标签、来源、主进程创建时间和组观察。机械 schema 2 仍拥有进程状态及起止事实。`termination.json` schema 1 以 execution ID 绑定请求，包含 terminate／kill 模式、时间与调用方声明的 human／agent／terminal 来源；同用户写入者可信，不把来源字段当身份认证。请求写入有独立短锁，force 不被后来的普通请求降级。终止命令只提交请求，真实 owner 在约一秒的循环中读取，并对本次隔离进程组发送 TERM 或明确请求的 KILL。普通终止不会隐式升级强杀。回执的 requested 不等于已退出；退出结果中 stopped_by 和 retry_allowed=false 表达已应用的终止意图。未发生终止时 retry_allowed 为 null，不授予自动重试权限。

owner 在控制期间不调用 Popen.poll／wait／send_signal，不提前回收直接子进程。保留的 leader PID 防止组标识复用；即使 leader 成为 zombie，也要继续管理仍存活的组员。macOS `proc_listpgrppids` 返回 PID 数、接收字节单位的缓冲区；查询扩容仍截断或失败时保持未知。结束判断先确认未回收 leader 已为 zombie，再取得完整组列表；列表仅含 leader 时才 wait 回收并结算 scope-complete。顺序不能交换，否则活着的 leader 可能在旧快照之后 fork 再退出。不能逐项过滤后用“本次看到的都消失了”代替完整组判据。该 API 内核仍遍历进程列表，因此查询保持低频。接口依据为 [Apple libproc](https://github.com/apple-oss-distributions/xnu/blob/main/libsyscall/wrappers/libproc/libproc.c) 与 [内核实现](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/proc_info.c)。

scope-complete 只证明本次受管进程组已收敛，不证明逃离组的进程、远端操作、文件一致性或业务结果。已释放的资源、submitted 操作和旧调用没有本通道；它们沿用声明控制者。owner 被强杀后显示 owner-lost，禁用终止，不从历史 PID 恢复控制。主进程先退出且组内仍有成员时，机械状态保持 running，组观察为 descendants-running。接口失败为 unknown，保留 owner 和显式强制请求入口。

macOS App 的 ActivityStore 拥有当前快照、请求代次和控制提示；切换 CLI 使旧快照失效。机器概览跨页面展示，超过 15 秒或更新失败的快照标为过期；执行列表独立于项目及 Section 折叠。AppStore 统一拥有菜单栏面板与主窗口的周期观察需求，不启动后台采集服务。至少一个界面可见时刷新机器与执行，至少一个可见界面停留在资源页时才周期刷新项目；都关闭、隐藏或主窗口最小化／被完全遮挡后不继续启动周期请求。主机与项目观察分别调度，避免慢探测阻塞压力刷新；主机请求至多一个在途，项目顺序观察。两个界面同开不创建第二组循环；隐藏后允许在途请求自然结束，快速重开也要等旧循环退出才能替换，不能通过强杀观察脚本中断潜在项目工作。来源、CPU 和内存数据不能被 UI 推导为额外控制权。
