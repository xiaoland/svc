# Workflow 与 Verification 触发审查

留存说明：以下是 description 审查当时的事实与授权记录。后续默认协作、入口职责、结构和措辞改进归入 [人机工作方式任务](../human-agent-working-models/packet.md)，发布目标经用户确认仍为16.0.1；此前升为17.0.0的判断已撤回。用户现已授权提交全部本次工作；旧“不提交”状态不再代表当前授权。历史安装检查只说明当时的16.0.0副本，不代表当前源码已安装。

- **目标**：审查用户观察到的验证行为不符合 svc-verification 定义和要求的问题，区分宿主发现、入口选择、工作中路由、方法执行和结论质量，提出可验证的改进方向。
- **边界**：用户于 2026-10-10 授权修改六个 Skill 的 description，使 catalog 直接说明触发条件。仅改入口描述及必要的发布同步，不改正文方法、CLI 或安装，不提交或发布。保留六个 Skill 独立使用和按压力加载的约束。
- **完成判据**：源文案和安装链路的结论有明确证据；推荐方向说明触发条件、归属、简单工作的成本和反例；不以静态检查、被提示的模拟或 Skill 读取次数声称真实触发效果。
- **当前事实**：本轮静态审查完成。当前 Corpus 16.0.0 已含独立 svc-verification，当前聊天的可用 Skills 列表也包含它。discovery_audit 比较源与全局 Codex 安装，两个 Skill 的全部文件 SHA-256 一致；CLI 全局 status 返回 current / 16.0.0，revision 与当前 HEAD 一致。该证据排除本机全局副本缺失或过旧，不推断其它消费者或宿主状态。
- **用户澄清**：问题主要是“Agent 开展的验证行为，不太符合 svc-verification 定义、要求的验证”，不是 Skill 读取次数。用户暂时没有具体任务案例；不要求补充，也不据此认定未加载是根因。
- **当前决定**：用户纠正审查复杂度，要求先把 catalog description 写成简短明确的触发条件。此前关于正文衔接的方案仍是未采纳建议，不在此次实施范围。六个描述已改为直接的 Use when / Use for 条件；不通过更多介绍解释 Skill 是什么。
- **发布同步**：discovery_audit 确认已存在 corpus-v16.0.0 且指向当前 HEAD。此次澄清保持协议行为，Corpus 目标版本升为 16.0.1，六个 metadata 使用发布准备命令同步，并添加一条中文变更片段。CLI 不变。
- **完成状态**：六项 description 首轮从 38～56 个英文词收敛为 20～24 个英文词，均直接以使用条件开头；复查后 Agent Collaboration 增加明确的跨 Agent 对象限定，现为 27 词。核对 Task Packet 的每个非平凡任务规则、Workflow 的工作推进与反馈、Verification 的验证设计/执行/判断/复用、Agent Collaboration 的委派与协调、Specs 的知识归属、Taste 的设计取舍后，正文和资源保持不变。
- **验证**：`pdm run prepare-corpus-release` 同步六个 metadata；`pdm run check-corpus-release --compare-ref corpus-v16.0.0` 通过，包含 Skill 元数据、结构、引用、许可和版本检查；`git diff --check` 通过。一次性逐行断言确认六个入口仅 description 和 metadata 改动，正文未改。未新增测试或运行全量 CLI 回归，因为 CLI 与运行行为未变。
- **下一步**：当前授权修改已完成，交付结果。不提交、发布或修改已安装副本；本机安装仍为前述 16.0.0，不能用源码检查声称宿主已采用新描述或实际触发行为已改善。

## 其余四项 description 复查

用户随后要求检查其它 Skill 是否有类似问题。只读检查当前四项 description 及对应正文，discovery_audit 返回独立的目录歧义判断；用户随后同意改进 Agent Collaboration 的描述。

- Task Packet 的 every non-trivial task 与正文一致，开始、恢复、维护和关闭的触发完整。non-trivial 的判断是已有适用边界，不能为了描述长度改成任务规模阈值。
- Agent Collaboration 仍有一处具体歧义：coordinating sessions or dependencies 未限定为 Agent 间的协作依赖，可能把单 Agent 的包依赖升级或普通任务依赖处理也匹配进来。assigning or repairing Agent work 与 adopting results 同样可进一步明确为其它 Agent 的委派和返回。建议使用“是否委派给其它 Agent、安排或协调其工作／会话、请求独立判断、采用其结果或交接责任”的触发条件，保持原正文范围。这是文字歧义，未观察实际误触发。
- Specs 已覆盖项目文档及持久知识归属，正文明确可以返回无需新文档；没有明确缺陷，不为较弱的任务草稿混淆猜测继续加字。
- Taste 已以方案选择为前提，后续影响面说明适用范围；没有必要再列更多案例或机械编辑例外。未发现需要继续修改的具体触发问题。

实施结果：Agent Collaboration description 已明确委派对象为其它 Agent、协调对象为其工作或会话、独立判断来自 Agent、采用对象为其结果，移除无对象限定的 dependencies。其余三项和正文未再改。沿用未发布的 16.0.1，不逐次升版本。修改后 `pdm run check-corpus-release --compare-ref corpus-v16.0.0` 与 `git diff --check` 再次通过。静态审查不证明自动触发率，不新增测试或评测平台。

## 澄清后的建议（覆盖前轮仅以加载为重点的建议）

Workflow 已明确否定“检查通过等于产品完成”，不能报告其允许跑绿就交付。Verification 入口也已有明确首动作和停止条件：从消费决策出发，明确结果和条件，选择能区分重要替代解释的观察，执行并返回有范围的结论。当前更值得改善的是 Implementation 中局部反馈与支持行为结论之间的动作衔接；其现有 specialist 路由和概念性最低责任可能未能改变实际验证选择，但仍只是源审查假设。

建议把 Workflow 现有最低责任与 Implementation 衔接为以下行为合同，而不增加阶段、文档或检查清单：

> 选择或复用检查前，明确当前要支持的行为结论，以及什么有意义的失败会推翻它。采用能观察该差别、且适用条件仍成立的现有证据或最小新观察。执行后据实际观察限定结论；检查通过但目标行为仍可能失败时，继续解决该证据缺口。判据、观察边界或证据适用性不清楚时，使用 svc-verification 的相应指导。

Verification 保持唯一的方法所有者，不再堆同义原则。Workflow 保留独立运行必需的最低动作与路由；已有充分适用证据时可以结束。没有要求必做 E2E、test-first、独立 Agent 审阅或另建验证文档。前轮 description 调整属于配套，不再作为主要修复。

后续行为观察必须区分未加载且遗漏动作、已加载但遗漏动作、理解原则却选择了错误观察、未加载但正确复用证据。前述场景仍可用于校准预期，但在没有真实任务案例时不声称它们能复现用户问题。多读取或多写解释均不能替代有效观察。

## 发现与建议

1. [Workflow 入口](../../corpus/svc-workflow/SKILL.md) 的条件为“Criteria, evidence, or feedback need specialist reasoning”，[Implementation](../../corpus/svc-workflow/references/implementation.md) 又要求 specialist improvement 或 beyond the local loop。但 [Verification description](../../corpus/svc-verification/SKILL.md) 已包括正常实施中取得可靠反馈。入口的路由门槛比被调用能力的适用范围更窄，Agent 需要先识别自己的证据问题才会加载识别问题的指导。
2. Verification description 用较多篇幅描述检查已经暴露问题后的情形，正常设计/实施/收尾时“需要确定什么证据足以支持结果”不够显眼。Workflow description 的 need reasoning / new route 覆盖面很广，但只拓宽它不能改善进入 Workflow 之后的跨 Skill 路由。这是潜在原因，不是测得的描述竞争结果。
3. 两个 Skill 已独立且在本聊天可发现，再次目录拆分没有解决当前证据所指的问题。宿主目录、加载动作、方法执行、结论质量是不同观察；加载次数少而已有充分证据不算失败，加载后仍只返回绿色测试也不算成功。

建议的触发合同是：需要建立或修改判断依据、选择支持行为结论的观察、判断既有证据能否覆盖当前条件，或处理检查与产品结果矛盾时，加载 svc-verification；不要求先知道自己需要专业帮助。已存在适用判据和覆盖当前变化的可靠证据时，直接执行或复用即可。验证责任持续存在，Skill 深度按未解决的判断加载。

| 所有者 | 建议调整 |
| --- | --- |
| svc-verification description | 明确普通设计、实施、修复和完成判断中的证据选择/复用触发，保留误判、反馈时延和检查演进条件。 |
| svc-workflow 方法表和跨 Skill 路由 | 用具体判断缺口替换 specialist reasoning；继续保留单独安装时的最低验证责任。 |
| Implementation 与 Verification Design | 在需要形成观察/判据的当下指向 Verification，而不是只在返回或专业改进时提示；不复制专题内容。 |
| corpus/index.md | 仅同步触发范围投影；不引入第七入口或强制跨 Skill 依赖。 |

暂不需要拆分目录、修改分发或安装代码、增加强制每次加载规则，或新增 Agent 评测平台。Verification 现有三份 references 继续按判据、证据、反馈的实际缺口加载。v15 迁移指南标明自己的适用版本，不能仅因当前源码 v16 就认定它陈旧或是当前低触发的原因。

## 效果判别

在相同宿主、可见 Skill 目录和上下文条件下，使用不点名 Skill 的真实任务观察首次相关判断、加载行为、取得的证据和结论：

| 场景 | 期待行为 |
| --- | --- |
| 保存修复只有成功提示，承诺包含跨会话持久化 | 识别缺少持久化证据，在选择观察时加载 Verification，并取得适用证据或明确缺口。 |
| 同类修复已有适用的跨会话回归检查 | 判断当前变化是否仍在保证范围内；若明确覆盖，直接复用，不为读取次数再加载。 |
| 测试全绿但用户路径失败 | 调查判据、条件、观察与要求的关系，不把本地绿灯当作整体结果。 |
| 可直接观察的简单文案修改 | 保持直接动作，不增加专题读取、测试平台或文件。 |

这些情形是验证方案，尚未执行。不能把 advisor 受提示的分析或静态路由走读当作自动触发实验。若用户随后说明主要问题是“已加载但执行不足”，应优先查首动作和返回边界，而不是继续提高加载率。
