# 项目执行与用量

## 目标与权限

2026-10-28，用户认可显式受管执行，并要求执行归入项目、按项目查看资源占用，重点补充磁盘 I/O、内存换页和 swap；要求联网研究，同时建立独立验收项目，或复制 Velune／Shenglin（不能用 worktree）接入 SVC Dev。继续迭代协作，授权范围内自主研究、收敛、实现及本机交付；沿用自由提交和开发签名安装授权，不公开发布。

禁止新增自动化测试，允许脚本；允许按新合同迁移或删除既有用例。避免高负载、并行构建、常驻观察宿主与反复 computer use。使用既有原生窗口和工具栏，不重新引入已修复的双重窗口／工具栏管理。保留真实项目与用户偏好，验收数据放在独立项目。

## 实施起点

App 0.5.1／CLI 18.1.0 已支持全局执行与主机压力。`dev exec` 记录 cwd、来源与标签，尚无明确项目身份；monitor 只对仍受管的根进程和当前后代取得 CPU／RSS，尚不提供项目汇总、进程 I/O、swap 或压缩指标。资源 ready 动作可能释放长驻进程，不能把已结束的准备动作当成长驻资源用量，也不能从历史 PID 获得控制权。

权威所有者为 `docs/prd/development.md`、`docs/product-tdd/activity.md`、`docs/product-tdd/macos-client.md`、公开输出模型／schema、`macos/README.md` 及用户手册。研究材料和本轮证据归本 Packet。现存旧 `tasks/svc-macos-app/packet.md` 及 InKCre 迁移材料与本任务无关，不纳入提交。

研究先解决三项会改变实现的事实：macOS 的页面读入、真实 swap 读写和压缩计数含义；低开销进程 I/O／内存指标与身份验证；资源释放后可观察身份与项目汇总的覆盖边界。再确定最小合同、独立项目和线性实现路线。

## 研究起点

Apple Activity Monitor 文档明确将内存压力、压缩内存、swap 已用量分开。psutil 7.2.2 在 macOS 没有 Process.io_counters；memory_full_info 的 USS 需要更昂贵的地址空间检查，swap 字段不适用于 macOS。Apple 的 proc_pid_rusage V2 则提供 diskio_bytesread／written、phys_footprint、pageins 等字段，本机只读自采样已成功。系统 vm_statistics64 明确区分 pageins／pageouts、compressions／decompressions 和 swapins／swapouts，不能混用字段。

下一步核对库实现及原生接口，明确归属和不可用值，再完成独立验收项目与实现。最终证据需连接真实 CLI、Swift 模型与项目 UI；单纯 JSON 或静态布局不能代表全部产品行为。

## 技术选择与实现路线

只读 advisor 核对后建议独立 observation.json sidecar，已采用：旧机械记录严格拒绝新增字段，给它追加项目／创建时间会影响混用 CLI 的控制与加入；仅汇总 managed 又会遗漏 released 服务。启动者负责一次写入归属，monitor 只读；元数据缺失不从当前 PID 补录身份，不授予控制，写观察失败也不杀死实际动作。managed 的进程创建时间仍由原 management.json 拥有，避免复制权威。

run 和 dev 保存已解析 workspace.root；dev exec 支持 --project，缺省仅在启动时查最近 svc.json 祖先，找不到即未归属。执行、Section 和项目选择都是界面范围，不推断工作目标。项目总量由唯一采样集合聚合：按 PID／创建时间去重，重叠归最近已登记执行根；released 根仍活着时继续观察，先建立观察集合再截取历史。当前受管组保留的 zombie leader 允许通过已验证进程组找到被重新收养的 worker；released 根结束后不再承诺后代覆盖。

使用原生 proc_pid_rusage V2（160 字节结构）获取内存 footprint、磁盘读写累计量和 pageins，用相同进程身份在采样前后取差。系统 host_statistics64 提供压缩及真实 swap 计数，host_page_size 获取实际内核页大小。本机已读到 16 KiB 页面。当前 psutil 7.2.2 的 swap_memory.sin/sout 实际来自 pageins/pageouts（上游源码已核实），因此只用其 used/total，不用其 sin/sout；页面速率统一按页/s 展示，不伪装为压缩后磁盘字节。新接口不需要 task port、地址空间遍历、root 或新的隐私授权。

每轮至多 64 个观察根、共 256 个进程，单个共享约 250 ms 窗口；截断和不可用明确报告。保留已有可见性调度，不运行项目 probe 来监控执行，不使用高负载实验。项目数字仅涵盖由 SVC 启动且身份可验证的本机进程，远端、容器内部、已脱离关联和外部程序不计入，也不把共享资源向每个引用方重复分摊。

已实现以上采集及公开字段、项目页资源／执行切换、项目用量、全局执行分组和主机 swap／磁盘信息。首次 Swift 单任务低优先级构建 5.86 秒通过；Python lint 和相关类型检查通过。真实 CLI 已证明验收服务 ready 释放后仍以一个不可终止的资源运行计入项目，其身份、内存和 I/O 字段可读取。还需完成边界观察、全部适用检查、原生模型／布局和本机交付，不能据此提前宣称完成。

## 独立验收项目

已新建 `/Volumes/WorkSSD/Development/svc-dev-lab` 与 `svc-dev-lab-peer`，对应用户的 ~/Development 路径；两个目录各自 git init，不使用 worktree，不复制真实项目或凭据。每个都有 schema 5 配置、具名有限任务、可就绪释放的 loopback Web 服务及按实例身份停止的入口。服务两分钟自动结束；工作负载持有 8 MiB 缓冲，每 250 ms 写入至多 64 KiB、总计至多 8 MiB，只写各自 .runtime。初选端口遇到已有监听时未停止对方，已改为本机检查空闲的 60671／60672，配置与访问入口同步。

后续使用这些项目观察项目归属、released 超过历史窗口仍可统计、嵌套去重、身份不符拒绝采样与 root 退出后 worker 的用量边界；不制造真正 swap 压力。最后将它们通过实际 AppStore 加入“验收” Section，保留原项目及 CLI 偏好。

## 已取得的证据与修复

结果版本已按仓库规则推进：CLI 18.2.0 的 dev-monitor 为 schema 2，exec／terminate 仍为 1；App 0.6.0 和安装工具 manifest 同步要求 monitor 2。与 HEAD 的公开 schema 比较通过；package major 相对最近已发布基线已经推进，不能因为本机 18.1 尚未发布而继续沿用 monitor 1 的旧形状。资源配置 schema 5、机械记录 schema 2、现有控制文件均未改变。

原有全量仓库检查的 260 项测试通过，13 项原生检查通过，未新增或修改测试。脚本实际发现可选观察元数据中的 null 与机械读取器不相容，导致普通执行丢失项目；修正为省略可选空字段，保留机械记录读取的严格默认值。仅将本轮未发布 observation 文件的 null 键做等价省略，没有补录 PID 身份或改变非空归属事实。另发现 management.json 原合同允许启动前的空创建时间，其读取现在显式允许该合同的 null；机械记录仍禁止 null。之后 9 项既有 execution 检查和相关类型／静态检查通过，启动失败的专门观察确认保留项目、来源、不可终止且无伪造损坏诊断。

`observe.py` 对独立 runtime 和两个实际项目分别观察。released 根已经被 21 条后续历史挤出执行清单，资源用量仍存在，终止请求被拒绝；真实前台 run 嵌套另一项目的 managed 执行时，根／后代集合实际重叠，3 个进程分别归为外层 2、内层 1，没有重复；zombie leader 的 worker 重新归属父进程后仍观测到一个工作进程；错误创建时间不采样也不获得控制权。[观察记录](evidence/observations.json)保存数值与问题。观察路径的组枚举只读取预算加一项，不为了用量扩大到完整控制证明；控制完成判断仍使用原先不可截断的完整成员查询。

实际 CLI 对两个项目各取得一个 ready 服务和一个临时执行，分别返回约 45 MiB 的进程计入内存及约 250 KiB/s 的受限写入；两次有限调用自然退出 0，服务通过声明停止入口结束。具名 run 的独立观察也取得 declared 项目归属及用量，执行页不授予它终止权限。观察登记被故意注入 OSError 时，真实 sleep 仍自然退出 0；可选记录失败没有杀死工作。未通过制造换页或 swap 压力验证系统告警。

原生脚本使用实际 Swift 模型和控件重放真实 CLI 的脱敏项目快照，1040／740 两种宽度及单项目执行列表已检查。两种宽度都保留系统侧栏按钮、刷新和设置，窗口未显示，应用未激活；单项目列表只显示该项目的一项活跃执行。图中的数值是记录重放，不证明拍图时实际工作仍在运行，也不当作物理键盘或 VoiceOver 验收。没有使用 computer use 重跑点击旅程。

上述待办已完成，安装和客户端证据见下节。

## 本机交付

产品源码及权威文档已提交为 `25e835f8e3f039482f2d30533269e22a76b139cd`。本轮交付 App 0.6.0／CLI 18.2.0；生成的 wheel 含 99 个 svc_cli 文件，逐字节匹配已提交源码。隔离 runtime 位于 `~/Library/Application Support/SVC/runtimes/c25ccbdb08478f55cb94/bin/svc`，实际版本与 monitor schema 2 均已核对。[Runtime 证据](evidence/runtime.json)记录 wheel 摘要和路径，没有覆盖登录 shell 的旧 CLI。

最终 Swift 编译用单任务、低优先级完成，耗时 4.59 秒。应用已替换到 `/Applications/SVC.app`，采用 `Apple Development: lanzhijiang@foxmail.com (Z5PX453UV3)` 签名，Team ID 为 `7J9DJNJ782`，严格签名验证通过。用临时副本移除签名后比较，安装代码与预备包相同；实际运行进程来自该安装目录并带 --background。源码版本元数据为上述提交加 dirty，原因是构建时仍有本任务证据及其他任务的未提交材料；99 个 CLI 文件已单独校验，不能把此标记当作干净发布证据。未制作标签、推送或公开 Release。

[Foundation 客户端观察](evidence/client.json)使用实际产品模型、ActivityStore 和新 runtime。它解码实际 monitor 数据，并通过产品终止路径结束本项目 30 秒上限的有限任务。结果为 interrupted／scope-complete，项目归属保留，canTerminate 变为 false；[owner 结果](evidence/client-owner.json)返回进程状态 130、stopped_by human、retry_allowed false。此观察无需 AppKit 窗口或前台输入，不能替代物理键盘、VoiceOver 或人类体验验收。

两个项目已通过实际 AppStore 加入“验收” Section。原有 2 个项目、Section 的 UUID／名称／折叠状态、原项目分配以及 CLI 路径与搜索路径均保留；原项目 svc.json／svc.local.json 摘要未改变。[登记](evidence/registration.json)和[安装](evidence/installation.json)保存结果。当前实例 PID 为 57917，仅是交付时快照，不作后续控制依据。单次实际 monitor 墙钟 0.541 秒、子进程 CPU 0.249 秒，无诊断问题；它包含 Python 启动和共享采样窗口，不代表纯采样成本或全场景性能保证。

验收项目各自为普通 Git 仓库，提交分别为 svc-dev-lab 的 `a7f47c1` 和 svc-dev-lab-peer 的 `8576c77`。README 给出从当前安装包读取配套 CLI 的命令，便于以后迭代直接复用。交付时两个仓库干净，验收任务和服务已结束；[项目交付观察](evidence/lab-delivery.json)记录普通 Git 目录、提交及剩余用量来源。用户可在 App 的项目页启动验收服务，或按 README 运行有限任务。

本轮未新增或修改自动化测试，只使用脚本及既有检查。完整既有检查与原生检查的结果已保留；随后修复采用有关静态检查、既有 execution 检查及实际脚本复核，最终包再次编译。未制造内存／swap 压力，也未声称已覆盖外部程序、远端、容器内部、旧记录或无法证明身份的进程。产品文档已说明项目用量边界，以及页面读入、真实 swap 活动与系统压力的区别。

实现、本机交付和约定脚本验收已完成；产品体验仍由用户判断。目前无须用户补充决策。任务材料保留为本轮交付证据，原有 svc-macos-app 与 InKCre 迁移任务材料不属于本轮提交。
