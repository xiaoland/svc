# 改进 Agent 间协作 Skill

## 当前审查：精简、职责与触发加载（2026-10-17）

最新阶段：用户已明确授权按上述方案实施，精简主文并按实际分支拆分 references，版本保持 16.0.2。collaboration_default 继续负责 Skill 主文及本目录 references；主 Agent 负责外部引用、既有变更片段、语义采用与检查。保留正常路径完整责任、独立完成与单次最终交付、必要中途例外、采用依据、独立安装授权边界及在途责任；不增加协议或模板。完成判据为主文可独立执行正常协作、四分支按真实困难触发、无悬空引用、发布版本仍 16.0.2，以及适用检查通过。以下审查阶段授权记录属于历史。

实施已完成：主文按安排完整成果、独立执行返回、采用继续分为三块，description 覆盖被委派方；正常复用和自动最终交付留在入口。旧两份参考删除，改为 delegation、adoption、coordination、handoff 四分支；删除通用验证分类和 SQL 长例，保留开放设计短例及按实际判据/观察困难可选发现 Verification 的路由。总体任务完成条款明确以 overall Task owner 为主语，避免 child 等待采用才返回。主 Agent 已读回全部五份文件并核对必要边界，更新 index 导航和原 16.0.2 变更片段。按同一 wc -w 口径，入口 755→473 词，五份总计 2984→1465 词；这不是实测 token 或触发率收益。

本轮验证：`SVC_BASE_REF=HEAD pdm run check` 的发布/Skill 引用、schema、格式、lint、类型及 7 项依赖合同通过；pytest 252 通过、1 失败（23.49 秒）。仍是 `test_cli_export_query_and_read_contract` 扫描本机同一压缩归档，在 `_session_meta:64` 对整数调用 `.get`，与此前已隔离复现的既有失败一致，本轮不重复实验或扩大 runtime 修复。另行确认六份 metadata 及根版本仍为 16.0.2、四分支集合准确、Skill 目录内及 Task Packet 链接有效、无 Corpus/CLI/tools 旧引用；`git diff --check` 通过。未提交、发布或执行模型行为对照；全量检查仍有上述残余，不声称全绿。

用户要求重新审视 svc-agent-collaboration，按 matt-skills 的定义判断可精简内容、职责错位及触发/加载问题。本轮授权为调查和建议，不修改 Corpus；上一轮 16.0.2 的未提交实施保留。主 Agent 负责外部定义、跨 Skill 所有权和最终建议；原 collaboration_default 负责现有三份文件的局部发现；原 multi_turn_judgment 仅判断独立安装下采用指导与 Verification 的职责边界，不作为 reviewer。

对照原文为 curated matt-skills 固定 revision 05cfa8b 的 writing-for-agents 与 SKILL-MECHANICS：指针描述到达条件，常驻指针消耗 context load，人记入口消耗 cognitive load；共同必要规则内联，分支深度按需展开。此次做静态路径和语义审查，不把单词数当作 token、运行时延或触发率。完成判据为可定位的发现、因果影响、最小修正和应保留边界；不运行与文档审查无关的全量测试。

审查完成，依据与定位见 [调查记录](inquiry.md#2026-10-17触发加载与内容所有权审查)。主要建议：补被委派方触发；将自动 final 单次交付与主文默认共置；收窄 substantial/reused 等宽泛加载条件；压缩通用验证方法和跨文件重述。保留独立安装边界、开放判断及真正协调例外。advisor 对采用/验证边界的建议已与 Verification 主文及 evidence reference 核对；本轮只更新任务材料，新的源精简尚未授权。

用户进一步指出 reference 太少会影响按需展开，主文过长复杂。撤回优先维持两份 reference 的建议：以正常协作可独立完成为主文边界，候选拆为安排责任、采用返回、执行中协调、责任交接与恢复四个独立分支，各以实际困难或例外触发。复用本身、收到返回本身不触发深入加载；不同分支不构成顺序必读流程。不为凑四份保留重复内容，若安排责任去重后没有独立深度则不单建。原 advisor 已就这一结构取舍返回理由；仍属设计讨论，未实施。

## 当前讨论：复用 sub-agent 的多轮交互（2026-10-17）

当前阶段：实施完成，验证残余已明确。用户明确要求“按此模型，改进 svc-agent-collaboration (bump patch)”，已授权修改技能及必要发布元数据；未授权提交或发布。采用前述强默认和两个例外，不增加消息协议或计数规则。根 Corpus 版本按用户要求从 16.0.1 递增为 16.0.2；六个 Skill 共同版本已由准备工具同步，CLI 版本不变，生成 changelog 按功能变更约定未手改。以下调查和提案记录描述此前状态，不再代表当前授权。

collaboration_default 负责 Skill 及现有 references 的语义整合与局部验证；主 Agent 负责版本、中文 Towncrier 片段、跨入口一致性、全量检查及结果采用。完成判据：普通探索与修复默认独立执行；不能等待的前提变化/阻塞和提前解除依赖仍可沟通；最终返回不重复主动发送、不要求无意义确认、不解除未完成责任；引用与版本一致，`pdm run check` 通过。真实消息和 token 收益未做对照实验，不作为本轮通过结论。

交付：主文新增独立完成默认及两个例外，coordination-and-handoff 替换宽泛中途消息规则并覆盖复用 sub-agent、自动最终交付和回应边界；delegation-and-adoption 与现有边界一致，无需改动。主 Agent 已采用负责人的局部引用检查和语义结论，读回最终 diff；新增中文 `.changes/corpus/agent-independent-completion.fixed.md`，六入口元数据均为 16.0.2。未新增模板、测试或 runtime 修改。

验证：`pdm run prepare-corpus-release`、版本一致性断言、`git diff --check` 通过。`SVC_BASE_REF=HEAD pdm run check` 的 Corpus/引用、schema、格式、lint、类型和 7 项依赖合同全部通过；pytest 为 252 通过、1 失败。失败项 `test_cli_export_query_and_read_contract` 默认扫描本机 Codex，读取 state DB 指向的压缩归档时，`_session_meta` 对 JSON 整数调用 `.get` 抛错。已逐字核对测试和读取器与 HEAD 相同，并以临时标量输入复现同一错误；在临时测试调用中仅补显式隔离 `--home` 后，原有导出/查询/读取断言全部通过，实验文件已清理。全量检查仍未全绿，不能用隔离结果替代原始失败；残余属于未修改的 telemetry，不扩大此次技能改动范围。未提交、发布或构建要求已提交源码的正式发行物。

最新设计讨论：用户认可聚焦上行消息，但要求检验更简单的默认，询问中途上报与介入是否本身低效。主 Agent 与原 advisor 收敛为：委派完整、可采用的成果后，child 在权限内独立探索、修复和验证，完成后最终返回；parent 默认等待成果，不逐步介入。正常不确定性与可恢复失败不触发沟通。只保留不能等到返回再处理的变化/阻塞，以及能提前解锁真实依赖的可采用阶段成果。中途交互视为例外，不能根据数量一律判定错误。最终返回结束一次执行回合，不自动结束 Agent 或整体责任；原 owner 可继续修复同一成果，不要求另造任务。该默认比逐消息成本权衡更简单，属于待用户讨论的提案，仍未授权改 Corpus。

最新用户反馈：主要问题在 sub-agent 向主会话发送消息，明确授权观察本机 Codex 父子会话轨迹。主 Agent 使用只读 SQLite 连接查询 threads/thread_spawn_edges，读取对应 rollout；upstream_trace_sample 独立负责 arc-bench 与 homelab 两个对照样本。未读取认证文件、未解密消息、未向被观察任务发消息。前一轮对 parent 续接的侧重需要收窄到 child 主动上报的时机、交付通道和接收方负担。

已核实 Velune 样本：根会话 `01a144c4-c8ac-7a13-bd40-604533dcd0f3`，统计截止 `2026-10-16T16:36:00Z`（北京时间 10 月 17 日 00:36），四个直接子会话向根发送并被记录为 MESSAGE 的数量分别为 subscription_path 8、codex_source 30、subscription_transport 38、subscription_manual 50，共 126 条；另有 30 条自动 FINAL_ANSWER。子会话只统计首个由 /root 发起的自身 task_started 之后的事件，排除 fork 继承的父会话完成记录；发送数与根接收数逐个一致。30 个自身已完成回合中，21 个在最后一次向 /root 主动发送后 30 秒内完成；这是时序观察，不证明正文重复。根轨迹第 1002、1020、1032、1037、1044、1054 行在北京时间 10 月 16 日 22:11:56—22:12:54 收到 6 条主动消息。

主要证据入口：`/Users/lanzhijiang/.codex/sessions/2026/10/16/rollout-2026-10-16T20-51-49-01a144c4-c8ac-7a13-bd40-604533dcd0f3.jsonl`；manual 子会话 `/Users/lanzhijiang/.codex/sessions/2026/10/16/rollout-2026-10-16T22-04-04-01a14506-ef4d-7633-b3c0-bc5b69c1b32f.jsonl` 第 1401 行主动发送、1410 行结束，相隔 4.2 秒。以上路径需以 state DB 返回值为准；消息正文为密文，最终答复可读。

对照样本由 upstream_trace_sample 返回：arc-bench 根 `01a144f3-b09c-7a20-bc07-a696cf50a419` 的 minimax_volo_execution 在三个自身回合中有 75 次 send_message 调用，根接收 71 条 MESSAGE 和 2 条 FINAL_ANSWER；homelab 根 `01a14354-034e-74e1-a21b-e9145a5aea6e` 的 qbit_diagnosis 有 6 次 send_message 调用。样本仍在运行，子会话发送数与根接收数不能直接当作丢失消息证明；不合并计算总体比例。对照仅支持上报密度差异，不支持无效消息率或 token 收益估计。

调查与提案已完成，advisor 已结合观察返回判断。当前建议：中途主动上报应以接收方在最终交付之前能采取的行动及延迟后果为依据；重要但不影响当前行动的材料合并到最终返回。运行平台已自动交付最终答复时，避免用主动消息再交付相同完成内容；确有提前解阻价值的中间交付仍保留。信息上报不应自动要求确认，也不应让子 Agent 无故暂停已授权工作；必须回应的问题、责任转移和依赖明确接收的操作仍应闭合。最终交付保留可采用结论、证据和残余，不复制全部消息历史。最小修改落点是现有 Send Information That Changes Execution 与交付说明，不新增轮次配额或确认协议。本轮未修改 Corpus；后续若授权实施，需保留真正提前解锁依赖和避免错误行动的反例。

用户观察到 sub-agent 经常被复用，提出 parent-agent 与 sub-agent 的多轮交互指导可能不足，频繁交互会侵蚀协作收益。本轮仅调查现有覆盖并形成修改建议；未授权修改 Corpus、提交或发布。此前阶段记录保留为历史，不代表当前版本或授权。

主 Agent 已完成条款对照；multi_turn_judgment advisor 已返回独立判断，未修改文件。现有条款覆盖延续负责人、合并更新及避免逐步指挥；具体缺口是深入参考的入口偏向 independent session、下一轮往返的增量价值，以及同一成果的延续与成果完成后的 Agent 再次使用未充分区分。建议扩展现有 reference 的适用范围，补充下一轮应解决的实质问题及重复往返时的调整条件，并说明复用上下文不自动延续旧权限或永久领域所有权；入口只增加必要导航。不新增协议、模板或固定轮数上限。

本轮提案已完成，待用户决定是否实施。依据为当前 Skill 和两份 references 的逐条对照及 advisor 的因果论据；没有运行轨迹，不能确定主要损耗类型或声称已验证收益。高频往返若来自工具轮询、用户持续变更目标或必要的递进设计，需分别判断，不能仅凭轮次判定低效。只更新本 Packet；`git diff --check` 通过，未修改 Corpus、提交或发布。

## 前序实施记录

当前阶段：实施完成，待用户复核。用户于 2026-10-06 对目标架构回复“同意，开始”，授权按认可方案修改 Skill 及相关消费者和迁移说明；未授权提交或发布。前序 verification 的未提交修改保留，用户纠正后，共同 Corpus 与 CLI 预备版本均为 15.0.0；此前逐次升版是误判。

目标：让 Agent 将协作组织成可采用的结果，选择适合的执行形式，保持完整执行责任，并在依赖协调、结果采用和责任转移时避免不必要的重复工作与失控的共享影响。

输入：当前 corpus/svc-sub-agents 入口和 Explorer/Executor references；/Users/lanzhijiang/.codex/AGENTS.md 及 guides/delegation.md；../factory26/docs/agent-guides/delegation.md；../factory26/sources/svc/skills/svc-sub-agents/SKILL.md；../factory26/tasks/development-delegation/packet.md 中的实际消息诊断。外部仓库材料作为依据，不将其项目专属许可、角色配置或运行规则引入本仓库。

主 Agent 负责材料对照、相邻职责、版本准备、迁移说明与整体采用；a2a_advisor 已完成统一问题、命名与迁移决策，不作为 reviewer，不修改源码。collaboration_content 拥有 Skill 目录改名与三份内容实施；collaboration_cli 拥有 CLI 名单、版本及安装/移除/采用的相关回归验证。局部修复留在各负责人处。

已观察到的缺口：当前 Authority Star 容易把所有协调压到 Primary；Executor 要求调用方先提供完整执行、验证与重试细节且强制独立 validator，增加委派准备成本并限制开放判断；Child/Primary 术语难以描述持续独立会话及其更新的人类决定；缺少消息触发、依赖直接协调与在途效果交接。参考源同时明确结果采用不能依赖另一个 Agent 的赞同，也不能一律重做全部调查。

advisor 已完成判断，建议 svc-agent-collaboration，入口加 delegation-and-adoption、coordination-and-handoff 两份按需 reference；移除固定星形拓扑、角色文件组织骨架及普遍独立 validator 前置要求，保留总体整合、共享目标责任、真实权限和采用依据。主 Agent 采用该方向作为待用户核对的具体提案；不以 advisor 赞同替代内容证据。

用户认可的理解：协作是拥有各自上下文、能力与行动边界的 Agent 共同推进目标；收益来自有效分担认知与执行负担，并行只是其中一种机制。上下文分开可能造成理解分叉，执行分开可能切断责任，外部产生的结果仍需要采用依据，独立执行空间也不保证效果隔离。入口必须从这些因果关系推出行动，而非先罗列角色、字段或流程。

目标方案见 [Design](design.md)。迁移决策已收敛：所有尚未发布的开发调整共同归入 Corpus 与 CLI 15.0.0；严格当前六名归档，无别名或自动跨名事务；复用显式旧名检查/移除、新名安装、其余实际安装项更新和独立 adoption 刷新。先确认目标发行物可读及新入口可安装再移除旧项，保留文件及消费者资料所有权。

实施结果：旧 Skill 目录及 Explorer/Executor 文件已移除，新目录含入口、LICENSE 和两份按需 reference。主 Agent 读回全部内容，核对 what/why/how、第一步、权限、有界返回、真实共享目标与在途操作责任；相邻 Methods、导航、维护者知识归属及迁移指导已同步。CLI 只替换两个当前六名名单，复用既有记录和操作机制；pdm.lock 仅同步两个本地包版本，没有升级外部依赖。

验证结果：`pdm run prepare-corpus-release` 同步六个 metadata 与许可；`SVC_BASE_REF=HEAD pdm run check` 通过，包含源码版本/引用检查、输出 schema、格式、lint、类型、7 项依赖合同和 245 项 CLI 测试。CLI 负责人相关 34 项回归覆盖旧名查询/移除及修改保护、旧及混合归档拒绝、当前新入口安装和采用块刷新保留块外内容。`pdm build -p cli` 成功生成 17.0.0 wheel 与 sdist，wheel metadata 正确且没有 Corpus 或 SKILL.md 内容；CLI help 冒烟通过。

当前源码另外通过内存中的打包候选解析和 WorkSSD build 下临时目录的实际六项安装、文件身份与 adoption 指针检查，临时安装已清理。该候选采用明确虚拟 revision，不是正式发布物或提交身份的证据。正式 Corpus builder 要求源已提交，本次未绕过其合同生成正式归档。未新增 Corpus 测试或 Agent 模拟；机械及安装检查不证明实际模型发现、加载、执行的收益。

版本纠正（2026-10-06）：用户指出全部工作应仍属 v15。核实最高远端发布 tag 为 v14.0.0；本地 main 曾停在 b642d04（src/version.json 的源目标已为 14.1.0），fetch 后 origin/main 为 4fe4c66（PR #30 合并，Corpus 与 CLI 源版本 15.0.0）。此前 16/17 均不是发布事件，已撤回源码版本及文档中的虚构发布链。上文 17.0.0 构建记录描述实际发生过的本地检查，不是当前版本或发布证明；其旧构建产物将清理并替换。版本检查同步修正为允许同一未发布目标持续开发，已发布版本不可复用。

纠正后验证：`SVC_BASE_REF=origin/main pdm run check` 全量通过，包含 266 项 CLI/工具回归及格式、lint、类型、依赖边界和发布检查。Corpus 比较支持 main 的历史 src/version.json 及 origin/main 的 corpus/version.json；未发布同版本允许演进，已有目标发行 tag 时按实际源码保护。CLI schema 的 package major 判据改为最近已发布 CLI tag，保留结果 schema 自身合同。`pdm lock --check` 与 `git diff --check` 通过。CLI 15.0.0 wheel/sdist 重建成功，wheel metadata 与 Skill 不内联边界已确认；本轮错误生成的 17.0.0 构建产物已清理。

下一步：汇报版本纠正完成，等待用户明确提交指示，不将未发布版本视为已可下载。

后续工作（2026-10-06）：用户已授权 [Workflow 合并任务](../human-agent-working-models/packet.md)。Methods 与 Verification 归入 svc-workflow，当前源与分发合同收敛为五入口；上述六入口和各次检查描述当时实施事实。V&V 的语义及三份深入参考保留在 Workflow 内，Agent Collaboration 的可选发现指向 Workflow。版本仍为未发布 15.0.0，无自动跨名迁移或额外发布。

最新修订：用户随后恢复独立svc-verification，最终合同为Workflow、Verification、Packet、Agent Collaboration、Specs、Taste六入口；Agent Collaboration分别按名字发现Workflow与Verification，15.0.0不变。
