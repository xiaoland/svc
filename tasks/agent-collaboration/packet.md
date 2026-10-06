# 改进 Agent 间协作 Skill

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
