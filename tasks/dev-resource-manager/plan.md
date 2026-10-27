# SVC Dev 实施计划

2026-10-27：本计划在第 4 阶段获批，第 5 阶段已按计划完成源码与局部行为验证。用户禁止增加自动化测试，后续允许迁移或删除既有用例；新增验证材料只使用独立脚本。实际结果见 [验收记录](verification.md#第-5-阶段实现反馈)，用户已授权第 6 阶段验收、自由提交及本机安装；公开发布未获本轮授权。

工作基于 `13694c0122294fc86cefd6ef83ec5e374dd1311d` 所在 worktree。既有文档修改保留；`tasks/svc-macos-app/packet.md` 是上一任务的修改，不纳入本任务提交。配置与协议尚未集成时不安装中间状态，不修改四个真实项目或用户偏好；第 6 阶段按授权替换已安装 App。

## 实施前已经确定的接缝

### 版本与协议传播

CLI 17.0.0 已随公开 `macos-v0.1.0` 制品分发，不能因最新独立 CLI tag 仍是 16.0.0 而复用 17。计划使用 CLI **18.0.0**、App **0.2.0**；版本相同不是兼容条件，App 仍按公开 command/schema 校验。版本准备和发布操作分开，本次不触发 GitHub Release。

| 合同 | 当前 → 本次 | 传播到的消费者 |
| --- | --- | --- |
| 项目配置 | 4 → 5，`dev.targets` → `dev.resources` | `config.py`、`project.py` 初始化、sparse overlay、项目／run／dev fixtures、CLI 使用与迁移说明。 |
| 根 `status` 输出 | 3 → 4 | `cli_output/project.py`、根文本输出、静态 schema、项目合同测试；只报告声明，不进行资源观察。 |
| `dev identity` | 2 → 3 | 入口、协调与观察实例区分后的投影、文本及 schema 测试；直接协调键算法保持不变。 |
| `dev status` | 3 → 4 | 具名观察、部分失败与现存执行事实；Swift、安装器和制品验收一起更新。 |
| `dev ensure`／`dev stop` | 2 → 3 | 显式动作的统一回执，保留各自 command，不能猜测第一个动作。 |
| `dev list`／`dev act`／`dev reconcile` | 新增，各为 1 | 参数分派、投影、静态 schema、Swift 调用与兼容检查。 |
| `init` 输出、机械执行记录、run／double 输出 | 分别保持 4、2、现有结果版本 | `InitPlan.signature()` 中的 4 是 init 合同，不是配置版本；run／double 不承接 dev 新规则。 |

公开模型与 `output_schema.py` 是结果 schema 权威，`tools/build_cli_output_schemas.py` 生成静态文件。App 本次主要消费 list/status/act/reconcile；Swift 与安装器的消费要求必须同最终 wheel 对照，不能从任意 CLI 的当前 schema 动态推断 App 已兼容。manifest 用逐命令的 `cli_result_schemas` 代替单个 `dev_status_schema`，明确记录实际配套版本。

`tools/build_cli_output_schemas.py` 的已发布基线选择也要覆盖带配套 wheel 的 macOS 发布 tag：从相应 tag 的 CLI package 源读取版本，而不是拿 App 版本当 CLI 版本。以 CLI 17 已通过 App 发布的历史构造回归；同步 CONTRIBUTING 的版本政策。根 Corpus 版本和 Skill 内容不变。

### 执行与恢复存储

`dev/resources.py` 拥有有效资源解析、一跳 owner、入口身份、摘要和锁内快照；`identity.py` 继续拥有直接协调键。将现有 readiness 适配演进为 `dev/observations.py`，保留 HTTP／TCP 边界，在统一具名观察上判断新鲜度和正向完成条件，不留下两套 target/resource 引擎。

`dev/runtime.py` 拥有动作、join、中断和完成语义。新增的 `dev/records.py` 只拥有 dev 的执行补充事实与恢复确认，供 list/status/act/reconcile 使用并由 A10–A13 覆盖；不是资源数据库。机械 `ExecutionRecord` 保持 schema 2：新增动作使用 `operation="act"`，沿用 subject、workspace_instance、intent_digest 和 coordination_key。dev 元数据按 execution ID 保存在原 execution 目录，含 schema 1、入口身份、动作键、有效声明摘要、完成／中断合同、领域阶段（pending／settled／owner-lost）及必需回执事实，不复制完整环境或配置。恢复确认在同一 dev 记录中绑定该 execution ID 与协调键，原机械 owner-lost 不改为成功。

所有写入走以下次序：

1. 按首次解析的协调键尝试取得锁，不排队执行有限动作；只对已发布且完全等价的 ensure 请求走独立 join 路径。
2. 锁内重新读取选定入口、owner、动作、解析环境与声明摘要。协调键或调用方所见摘要变化即拒绝，使用这份已核对快照执行，不切到另一把锁重试。
3. 读取当前指针、机械记录与 dev 阶段。取得无人持有的锁后，发现 abandoned active 或 dev pending 即记录 dev owner-lost，未确认者持续阻断；机械仍 active 才调用 mark_owner_lost，已 exited／released 的真实机械事实保留。旧 ensure／stop 记录可以缺少新 dev 元数据，但仍受阻断；`act` 记录缺少／损坏元数据是错误，不能降级为旧记录或允许新动作。
4. 写机械 starting 记录 → 写 pending 的 dev 元数据 → 发布 coordination 指针 → 启动子进程。任一必要写入失败都不启动。指针前留下的孤立记录没有已启动副作用；指针后崩溃则按未知处理，包括尚未拿到 PID 的窗口。
5. 完成合同判断结束后，把完整回执和 settled 在同一次原子写入中保存，再返回；可判定失败也属于 settled。机械 exited 不等于领域已结算，join 必须等待 dev settled／owner-lost，并继续校验声明，不能直接借 follow_execution 的机械 terminal 报成功。读者没有取得锁时，不把尚在发布、缺少结果或未结算瞬间当作成功；不匹配时 busy，发布损坏保留错误。
6. reconcile 在同一锁内检查指针、ID、协调键和未知确认；先原子写确认，才允许后续独立请求覆盖指针。重复同 ID 确认可返回已有确认，旧指针已被替换时拒绝过期 ID。恢复确认与原结果分开保存，不把 dev owner-lost 改成 settled；恢复本身不执行动作或接管旧 PID。

保存中断请求与最终观察的职责留在 dev，信号 handler 只记录请求供主流程消费。`wait` 在启动后不调用 terminate，也不安装杀进程的期限；轮询／等待仍持续持锁直到真实结束。共享执行层的锁、start_isolated、wait_owned 和 release_owned 足够支撑这条路线，只有发现无法在领域层实现的机械缺口才改 `_execution.py` 并重验 run／double。处理信号从发布前开始，启动交接间收到信号也不得丢失或意外释放锁。

### submitted 的结果通道

保持合并日志供人诊断，不从混合 stdout/stderr 猜 JSON。submitted 默认按声明的退出码完成提交，0 只报告接受、不提供操作引用；需要动态引用时，动作明确选择 `operation-json`，CLI 向控制者传入 `SVC_DEV_RESULT_FILE`，指向本次 execution 下独立的 dev 结果文件。

结构限定为 `{"schema_version":1,"operation":{"id":"控制者操作ID","url":"可选访问地址"}}`，id 必填。进程结束后读取，限制大小（64 KiB）、严格字段和类型、普通非链接文件，URL 沿用访问入口的许可规则；无需新日志协议或后台作业系统。选择结构化结果后，即便命令退出 0，文件缺失／损坏也返回结果无效与实际退出事实，不报告资源完成，不自动重试；实际请求可能已经发生，控制者仍拥有异步冲突处理。未选择该通道时不推断输出内容。

### 旧客户端迁移

旧基线固定为 [已下载的公开 wheel](../../dist/release-acceptance/macos-v0.1.0/sustainable_vibe_coding-17.0.0-py3-none-any.whl)，SHA-256 为 `b22480be9dbce8f978df7aab788487f0613eee6b9d500ff1864ea3e478ad72d6`。A16 用此 wheel 的独立环境启动旧调用，不能用改过的源码冒充旧客户端。

先禁止发起新的旧版控制，保留旧 owner 和 follower 正常结束的机会。实验只在旧 owner 仍持锁时迁移同名、同 scope／host_key 的配置，并验证新调用 busy、无副作用；之后排空所有旧 CLI 调用才开放新控制。旧 follower 可能按旧快照执行，不能认为更换配置或共用锁能让旧客户端遵守新 owner-lost 规则。进程强杀产生未知时按真实控制者核对并在新 CLI 恢复；不得强制“排空”成假成功。随后才允许引入 owner、改资源键或 scope。人工迁移不会自动改写用户配置。

### 原生控件与前台隔离

保持 `SVCMenuBarApp.swift` 的 NSStatusItem／popover 锚定和用户主动打开时的行为。资源行、详情、状态和选择继续由 SwiftUI／AppStore 拥有；只为自动动作提供一个窄的 `ResourceActionButton`（NSViewRepresentable），包含原生 NSButton、稳定入口＋动作键标识、名称、enabled 与回调。Coordinator 的回调和标识随 SwiftUI 更新，不保存另一份资源状态。

直接对透明 SwiftUI Button 的底层 NSButton、两种公共 AX children 及已有权限下的外部 AX 查询均未获得标识，屏幕外宿主对照也未解决。窄桥实验成功按唯一标识点击，重新绑定另一入口后只执行新动作；没有按坐标、视图序号或“第一个按钮”寻址。实际 `.accessory` 策略、透明忽略鼠标宿主，以及外部 NSWorkspace 激活观察全程为零激活、零键窗口。详见 [实验材料](experiments/README.md)。这选定实施路线，不代表候选面板或视觉已验收。

## 线性实施顺序

下列是同一次已约定产品变更的执行顺序，不是缩小为 ensure／stop 的首个增量。主 Agent 负责集成；没有预设并行写代码轨道。

| 步骤 | 具体工作与依赖 | 完成反馈 |
| --- | --- | --- |
| 1. 配置与公共模型 | 修改 config.py、project.py、cli_output/{project,dev}.py、output_schema.py，定义资源、观察、动作、owner 及 overlay；按上表同步初始化、声明摘要和严格投影。 | 配置与 schema 局部检查覆盖 A01／A05。无旧字段双读；其它领域 fixture 只迁移项目配置版本。 |
| 2. 解析与观察 | 实现 resources.py 和 observations.py，复用 identity.py 的协调算法及既有 HTTP/TCP/exec 设施。时间保留 provider 数据时间，过期不因新查询而洗新；解析 owner 不执行其观察。 | A02–A05：不同入口、同边界、局部未知、自动观察、provenance；list 无 provider 调用，status 无控制。 |
| 3. 动作与恢复 | 按上述顺序实现 runtime.py／records.py，串联三种完成、两种中断、有限 busy、ensure join、声明重载及 explicit reconcile。 | A06–A13 的真实独立 CLI 进程、效果文件、信号、故障点；覆盖指针前后崩溃、机械退出后仍 pending、settled 回执落盘后崩溃、旧记录和结果文件失效，不能只做线程测试。 |
| 4. CLI 与迁移贯通 | 完成 cli.py 参数／分派／文本／退出码，更新生成 schema、test_cli.py、项目／run helpers、CLI README 与 USER_MANUAL。ensure/stop 调同一 act 引擎。 | A16／A17 的新旧 wheel 边界、错误结果与退出码；`--json-schema` 可独立发现全部公开命令。 |
| 5. 原生资源面板 | 修改 DevModels.swift、CLIClient.swift、AppStore.swift、MenuPanel／TargetRow／ReceiptView（按最终职责改名），加入窄动作按钮和资源详情。观察按入口＋方面，操作按协调身份，回执保留原入口。 | A14／A15：语义点击、真实 CLI 链、绑定更新、状态竞争、错误可找、等待退出／取消退出；离屏浅深色画面要实际审查。 |
| 6. 同源制品与版本 | CLI 18.0.0／App 0.2.0、Towncrier 片段；修改 macos_app.py、publish_macos_release.py、build_cli_output_schemas.py、对应测试与 macOS workflow。保留原开发签名与后台启动合同。 | A17／A18 制品部分：安装器全部 schema 检查、manifest、最终 wheel 的原生连通；明确所选必需测试已执行，不让环境条件静默跳过。 |
| 7. 集成反馈与持久知识 | 必需局部检查通过后执行仓库全量检查、原生测试及候选包验证；纠正失败并只重验受影响结论。更新 PRD、App／CLI 合同、执行／部署、安装及版本说明的实际状态。 | 提供第 5 阶段实现及局部行为证据，A01–A18 逐项记录实际支持范围；阶段 6 再完成正式验收、开发签名安装／重装和交付判断。 |

## 验证命令与交付边界

实施使用既有 PDM 与 SwiftPM。以下是已采用的检查入口。既有用例已迁移，新增观察使用任务 scripts 目录；源码和最终 wheel 的结果分别保留，不新增自动化测试。

```sh
pdm run pytest cli/tests/test_config.py cli/tests/test_project.py cli/tests/test_dev_identity.py
pdm run pytest cli/tests/test_dev_runtime.py cli/tests/test_execution.py cli/tests/test_cli.py
pdm run build-cli-output-schemas
pdm run check-cli-output-schemas
pdm run pytest cli/tests/test_cli_output_schema_release.py cli/tests/test_macos_packaging.py
pdm run check
SVC_TEST_CLI="$PWD/.venv/bin/svc" SVC_RENDER_DIR="$PWD/dist/dev-resource-manager/render" swift test --package-path macos
pdm run python -m tools.macos_app archive --output dist/dev-resource-manager/candidate
```

候选归档后在新的临时 venv 安装该目录的唯一 wheel，以该 venv 的绝对 svc 路径重新运行必需原生连通分组。迁移保留名称的生命周期用例，并补齐 workflow 的渲染与 runtime 环境；缺 SVC_TEST_CLI、渲染输出或桌面条件时报告缺口，不能发布为全通过。源码 CLI 与最终 wheel 的证据分别记录，保留版本、摘要、dirty 状态和前提。

本地未提交候选只能标记 dirty；`--require-clean` 的正式发布检查要在另有提交授权且所有本任务改动落到对应 commit 后执行，不能为检查通过顺手提交其它修改。开发签名安装／再次安装在第 6 阶段用既有 `script/build_and_run.sh --verify` 路径执行，保护用户偏好、CLI 选择和在途操作。公开发布、真实项目配置迁移及真实设备／远端操作仍需各自授权，不从本计划推导。

实现遇到影响身份互斥、副作用、观察有效性或产品范围的反例，回到对应方案与判据纠正；普通编译、类型和测试失败就地修复。不得删除困难判据、改用外部登记／daemon 或缩减产品范围来宣称完成。

实施结论：步骤 1–7 的源码传播、制品与局部反馈已完成。阶段 6 尚未开始；正式安装、重装和完整交付结论仍待对应授权与证据。
