# 六个 SVC Skill 入口审查

审查日期：2026-10-10。对象是审查时工作区六份 SKILL.md，包含本会话尚未提交的修改；不是已安装的16.0.0副本。以下保留当时的问题与建议，行号和原文属于审查快照。

后续实施状态：用户已授权并完成两批改进。第一批修正阶段职责和参考条件：Workflow 第二阶段改为 Realize with feedback，第三阶段核对证据覆盖范围并只补实际缺口；Packet 入口内联轻量形状检查；Workflow 的 Verification 路由使用可识别缺口；Taste 及 Workflow 实现路由补齐性能条件。第二批重排核心内容：前置 Workflow 任务恢复，压缩 Packet／Specs／Taste 通用前言，显露 Verification 和 Agent Collaboration 动作结构，并把 Taste 作者扩展指导迁至维护者合同。描述未进一步修改；下文保持审查快照。完成证据和限制见 [Task Packet](packet.md)。

## 总体判断与判据

措辞精简追加完成：六入口正文由核心重排后的4214词收紧至3834词，章节、description、引用、授权和完成边界保留。此数字不是实际加载或执行改进的证据；验证与限制见 Task Packet。

六个入口都已经承担实际职责，并非只有介绍或导航。主要问题是核心动作的可见性、通用前言的比重、入口与参考的条件匹配，以及少量尚未清楚区分的工作边界。不能用总字数或统一三阶段格式替代这些判断。

入口应让 Agent 找到适用条件、第一项有用动作、必要边界、可返回的结果，以及需要时的下一份指导。Workflow 的关键结构是协作阶段与工作方法；Task Packet 是任务状态的恢复、维护和增长；Specs 是知识所有权的选择；Taste 是带有理由与反例的判断视角；Agent Collaboration 是结果责任的安排与采用；Verification 是由主张到证据和结论的关系。

“入口足够开始”允许在识别具体分支后读取专业参考。它不要求把所有专业内容塞回入口，也不要求每个 Skill 增加阶段、表单或检查清单。独立安装要求每个入口保留最小权限和任务连续性责任，不能只靠一个外部 shared core。

## 外部参照

已确认用户此前所指包括 curated `imMamdouhaboammar/matt-skills`。本轮 `git ls-remote` 观察到 curated HEAD 为 `05cfa8bdea1d93ec7253daeb5d89555ccd5a290f`，上游 `mattpocock/skills` HEAD 为 `49dd158d1076134a641b33efb035946536778336`；二者分开使用，不将 fork 的规则当作上游统一合同。

- [writing-for-agents](https://github.com/imMamdouhaboammar/matt-skills/blob/05cfa8bdea1d93ec7253daeb5d89555ccd5a290f/skills/writing-for-agents/SKILL.md) 的有用判断是：所有路径需要的内容内联，分支专属内容按条件展开；同一概念的定义、规则和例外放在一起；完成条件写到能指导下一步的位置。它也明确允许纯参考型 Skill，因此不能把 Taste 强制改成流水线。
- [SKILL-MECHANICS](https://github.com/imMamdouhaboammar/matt-skills/blob/05cfa8bdea1d93ec7253daeb5d89555ccd5a290f/skills/writing-for-agents/SKILL-MECHANICS.md) 和 [engineering-workflow-guide](https://github.com/imMamdouhaboammar/matt-skills/blob/05cfa8bdea1d93ec7253daeb5d89555ccd5a290f/skills/engineering-workflow-guide/SKILL.md) 区分触发与正文，并给路由具体条件。SVC 已有六入口和任务级规则，无需因此增加一个 router Skill。
- [diagnosing-bugs](https://github.com/mattpocock/skills/blob/49dd158d1076134a641b33efb035946536778336/skills/engineering/diagnosing-bugs/SKILL.md) 把当前阶段的可观察完成条件写得很具体，适合借鉴表达方式。其没有运行复现就禁止进入假设的规定属于该方法的取舍，不宜直接推广为 SVC 通用调查规则。
- [tdd](https://github.com/imMamdouhaboammar/matt-skills/blob/05cfa8bdea1d93ec7253daeb5d89555ccd5a290f/skills/tdd/SKILL.md) 要求先与人确认测试边界，并把重构放到 review；这些不应覆盖 SVC 已有的授权延续、按风险验证和自主工程判断。[handoff](https://github.com/imMamdouhaboammar/matt-skills/blob/05cfa8bdea1d93ec7253daeb5d89555ccd5a290f/skills/handoff/SKILL.md) 很短但任务窄，不能用它的长度要求覆盖整个任务生命周期的 Packet。

未将这些文档关于注意力、否定句或特定措辞效果的解释当作实验结论，也没有安装或执行外部 Skills。

## 优先处理的共性问题

### 通用前言压住专业首动作

[Task Packet](../../corpus/svc-task-packet/SKILL.md)、[Specs](../../corpus/svc-specs/SKILL.md)、[Taste](../../corpus/svc-taste/SKILL.md) 的9—15行是完全相同的四段，共252个英文词。按 `wc -w`，占三份入口全文约30%、29%、40%。这是内容顺序和重复展开的问题，不意味着这些责任无用。

建议各自把专业首动作前置，只内联本地必需的最小边界：既有权限、人类专属决定、事实核对、同一任务及 Packet、剩余义务、诚实返回。通用解释不应每次完整展开。不能简单移到必需的公共文件，否则破坏独立安装。

### 参考读取条件需要与正文责任对应

Task Packet 在最小 Packet 建立后无条件要求 early shape preflight，但细则放在 growth reference；其首段却只在管理压力出现时适用。Workflow 以 specialist reasoning 作为 Verification 的路由条件，也比 Verification description 中正常设计、执行和判断证据的范围更难识别。Taste 的 Implementation 路由使用 only when 列表，但未明确包含 description 和目标参考都覆盖的 performance。

这些均不等于实测漏加载。它们是可定位的入口条件问题，优先修正条件和核心动作的摆放，而不是添加更多同义关键词或扩大默认加载集合。

## 逐入口结论

### svc-workflow：阶段的验证责任仍有重叠，启动动作在文末

定位：[阶段表17—19行](../../corpus/svc-workflow/SKILL.md)、[方法与末段29—44行](../../corpus/svc-workflow/SKILL.md)。

第二阶段是 Realize and verify，推进条件已经包括完成 verification；第三阶段再次 Verify and deliver，但未明确还要判断什么。这个问题来自本轮修改，不能因刚改完就跳过。实现者可能重复跑一遍检查，也可能把第三阶段视为只写交付摘要。

建议保留用户确认的 Verify 名称，将第二阶段突出为实现及其局部反馈，第三阶段明确核对现有证据能否支持本次约定结果、哪些义务未满足、是否需要追加观察。已有证据充分时复用，出现实际缺口时再验证；验证仍贯穿工作。无需为区分阶段再制造一套验证术语。

恢复意图、当前事实、授权与 Packet 的首动作目前在最后一个长段，与额外 Skill 路由混在一起。将必要的启动提醒移到默认模式前，其余条件路由留在相应位置。

应保留：description 同时覆盖协作和自主工作；默认模式在入口直接可用；已有确认和授权能够满足前序阶段；只调查的任务可以在所求结果就绪时返回；迭代式只保留选择入口。

另一个中等优先级问题是29行 Verification 路由。建议用能识别的缺口，例如不清楚判据、观察是否覆盖承诺、既有证据是否仍适用，替代先判断是否需要 specialist。并不要求每次普通测试都加载全部专业参考。

### svc-task-packet：基本生命周期可用，但最小启动还依赖增长参考

定位：[21—25行](../../corpus/svc-task-packet/SKILL.md)、[growth前置检查7—16行](../../corpus/svc-task-packet/references/growth.md)。

创建一个小 Packet 后，入口要求 perform the early shape preflight；Agent 为完成这个普通动作需要读增长文档，其中又出现 Track、Phase、Cell 等概念。一个单人、线性、目标明确的非平凡任务也会沿着这条路径增加读取。

建议在入口保留一句轻量判断：当前单一 Packet 是否足以恢复状态、安排下一步和容纳实际协作；有独立所有者、共享依赖或明显的信息管理压力时再读取增长指导。这样保留早期识别复杂形状的责任，同时让简单任务能凭入口继续。不要把“增长”取消，也不要把生命周期变成强制依次建立一组文件。

应保留：最小 packet.md、先恢复后创建、用人类语言、更新权威信息后更新工作状态、按保留规则关闭。description 已有 every non-trivial task，没有证据因为没有逐字列出 grow 就会漏掉该任务，不建议为词面完整继续堆词。

### svc-specs：专业核心已清楚，应前置而非继续拆分

定位：[21—39行的首动作与所有权表](../../corpus/svc-specs/SKILL.md)。

当前专业核心已经很好地回答了“事实归谁、是否需要文档、先改哪里、何时结束”。主要负担是它之前的通用前言，以及其后的 owner 定义与表格部分重复。

建议以“找到事实和消费者 → 查已有可执行或文档所有者 → 修改权威源及必要投影”开场，直接给现有所有权表。保留“没有新文档的必要”作为有效返回。扩展继续按准入条件放在后部，内容细则继续留给对应 reference。

description 当前约53词，是六份中最详细的对象枚举，可改成更紧凑的“为持久项目知识寻找或维护权威所有者，包括判断是否需要文档”。重点是完整表达知识归属职责，不应缩成“编写项目文档”。其 coordination extensions 未限定 admitted 可作次级文字收紧，但 Skill 被触发本身并不授予扩展创建权限，不能据此断言当前正文允许乱建扩展。

### svc-taste：需要突出判断依据，并区分消费者与作者内容

定位：[17—36行](../../corpus/svc-taste/SKILL.md)、[Implementation Taste首段](../../corpus/svc-taste/references/implementation.md)。

252词通用前言之后，入口才说明它如何帮助一个具体选择。四种权威的区分是很好的核心，可以更早呈现；随后用紧凑的判断视角组织候选的后果、成本、反向条件和支持理由。保持参考型形态，不必造 stage。

34行说明如何编写 guidance，36行结尾说明何时增加领域入口，更接近框架作者维护规则。建议把消费者每次都需要的“如何判断当前方案”留在入口，作者扩展规则放到已有 corpus/AGENTS.md，或明确限制到实际维护 guidance 的分支。

21行的 only when 路由列表未包含 performance，而 description 与目标参考均包含。建议明确覆盖该分支或去除穷尽式表达。它支持路由文案有缺口，不证明真实性能任务一定漏加载。

应保留：项目事实、用户偏好、可反驳启发式与任务假设的区别；每项建议有因果理由、代价与反向条件；不把最少代码、深模块或任何模式升为普遍定律。现有 description 的 maintenance 已涵盖未来维护成本，choosing between options 也不必解释成要求用户先给两套方案，未采纳仅因缺少原有词语就认定职责丢失的意见。

### svc-agent-collaboration：有可执行责任链，但藏在十个等权段落里

定位：[9—27行](../../corpus/svc-agent-collaboration/SKILL.md)。

入口已有委派输入、稳定 owner、共享效果、返回采用与整体任务责任，普通委派可以独立执行。问题是全文只有一个主标题，首动作前先解释协作收益和成本，运行中需要的信息也没有明显定位点。恢复一个已在执行的子任务时，读者仍要从总体论述中找当前适用部分。

建议按当前动作组织：是否值得委派；交给谁以及交付什么；执行中何时协调；结果如何采用、修复或交接。开头用一个紧凑的委派合同说明目标、上下文、授权边界、产出及证据；稳定 owner、并发目标和集成责任就近放置。它是可按当前状态进入的责任链，不要求每次恢复工作都从“是否委派”重来。

应保留：并行不是唯一收益；整体 owner 保留集成责任；工作目录不隔离外部效果；另一 Agent 的声明不是验证；采用时不必重做全部工作；普通失败由原 owner 处理。description 已准确覆盖跨 Agent 的触发对象，无需继续压缩。

### svc-verification：核心方法已经在入口，但需要把动作展开成可扫描结构

定位：[13行的执行与返回段](../../corpus/svc-verification/SKILL.md)、[15—19行的规则与参考路由](../../corpus/svc-verification/SKILL.md)。

13行同时承载决定消费者、结果、条件、需求与假设、选择观察、修复观察、执行、结论、复用边界、停止和受阻处理。后续三段又混合基本规则、例子和路由。内容充分，但读者需要自己从长段中提炼出行动关系。

建议把已有方法显式呈现为“明确主张和目的 → 找到判据、条件及可用证据 → 取得必要观察 → 判断支持范围并返回缺口”，其中复用适用证据是合法路径。将过弱／过强 oracle 的简短对照保留在入口，更详细例子和条件留给现有三份参考；无需另加模板或机械核对表。

应保留：verification 与 validation 都属于此 Skill；符合要求不等于服务真实用途；oracle 既拒绝需求违规也接受保持需求的实现变化；证据复用、条件限定、不能证明时明确返回。它不是没有方法，更不能改成“执行测试，全部通过就完成”。description 已覆盖正常验证与结果判断，无需用更多关键词补偿正文结构。

## 改进顺序和验证建议

先处理会影响下一步行为的边界：Workflow 第二／第三阶段的职责区分，Task Packet 的基本 preflight 就地可用，具体参考路由条件。再压缩三个相同前言、显露 Verification 和 Agent Collaboration 的动作结构，最后精简 Specs 和 Taste 的重复或作者内容。其它 description 默认保留，除非具体场景显示有缺口。

用少量实际任务检查改写，而非断言 Markdown 必须含某个词：小型非平凡修复能否恢复 Packet 并开始；已有方案授权能否直接实施；证据已充分时能否避免重复验证；结果绿色但未覆盖跨会话承诺时能否识别缺口；已有子 Agent 返回能否按证据采用并保留 owner；已有代码合同足够时能否返回不新增文档；纯性能选择能否到达适用 Taste；只安装一个 Skill 时能否维持最低权限和任务责任。

这些场景是后续验证建议，本轮未执行行为对照实验。没有以真实触发率、漏读率或节省时间作为已经建立的结论。

## 证据和采用范围

主执行者完整阅读六个当前入口，并核对相关参考；独立审查者负责 Packet／Specs／Taste，advisor 只处理独立安装与前言压缩的设计取舍。采用了有直接文本依据的发现；没有采用“少了某个同义词即职责缺失”或“触发描述宽一点就突破正文授权”的推断。

本轮用 `wc -w` 记录全文规模：Workflow704、Task Packet827、Specs868、Taste634、Agent Collaboration815、Verification693词。该数字包含 frontmatter、标题及表格标记，仅为阅读规模线索。

审查前后 Corpus、版本配置和已有 tracked 变更的 diff 摘要一致：`50d86b85ea40b8e7ce44508e7f230ab9d346a72db754ecfbe6c0936d08335001`。本轮只更新任务材料，没有实施源修改、安装、提交或发布，也没有运行与本轮只读审查无关的 CLI 测试。
