# 调查：SVC 的发现、加载与执行

本调查服务于入口与内容重组决策。2026-10-05 核对仓库源码并调查 `mattpocock/skills` 上游和 `imMamdouhaboammar/matt-skills` curated 版。源码能够证明指令结构，不能证明宿主 Agent 的触发成功率或行为改善。

## SVC 当前事实

[集成入口](../../cli/src/svc_cli/integration.py) 的 `agent_body()` 只介绍 CLI 命令，`navigation_body()` 仅要求相关时使用 lookup，没有具体任务触发条件。 [Corpus 入口](../../corpus/index.md) 要求非平凡任务先使用 Task Packet； [方法索引](../../corpus/methods/index.md) 按缺失的返回区分方法，但 Agent 要先进入 Corpus 才能看到这些条件。

Explore 和 Verification 已有调查动作、证据规则与结束边界；问题不是没有方法，而是入口常先介绍抽象定义和权责，Agent 仍需将现场问题翻译成概念。这一解释是基于源码的判断，尚未经过对照行为评测。

执行 `pdm run svc lookup --keyword <词> --scope both --limit 3 --json`：

| 查询 | 实际结果 |
| --- | --- |
| `debugging` | 无候选 |
| `resume` | 仅命中 multi-repo 扩展与其共享文档模板 |
| `architecture` | 返回 Implementation Taste、Unit TDD、Taste |
| `design` | 返回 Design 及 Test/Product Design 子入口 |

这是有限的词汇导航抽查，支持任务词与概念词存在落差；没有测量整体触发率，也不能据此认定查询耗时是主要瓶颈。这些结果用于改善指导的发现与到达方式，不构成缩小 Task Packet 或其他现有职责的依据。

## matt-skills 参考

调查版本：上游 `24fe0ef7737efae15c87225755e9f6f5965e4888`；curated `05cfa8bdea1d93ec7253daeb5d89555ccd5a290f`。

- [上游 ask-matt](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/ask-matt/SKILL.md)禁用了模型隐式调用；它是供人主动使用的流程地图。
- [curated 路由入口](https://github.com/imMamdouhaboammar/matt-skills/blob/05cfa8bdea1d93ec7253daeb5d89555ccd5a290f/skills/engineering-workflow-guide/SKILL.md)在工作类型不明确或重叠时读取短 catalog，选择最窄的主要 Skill，按需要增加独立阶段或质量门。目录中 34 个 Skill 均未禁用模型隐式调用。
- [writing-for-agents](https://github.com/imMamdouhaboammar/matt-skills/blob/05cfa8bdea1d93ec7253daeb5d89555ccd5a290f/skills/writing-for-agents/SKILL.md)将引用视为目标与到达条件，并建议把所有分支需要的内容内联、仅部分分支需要的内容按需加载。这是作者的方法主张，尚未由本任务实测验证。
- [调试正文](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/skills/engineering/diagnosing-bugs/SKILL.md)用报错、失败和变慢等任务信号触发，先建立针对实际症状且已经运行过的反馈循环，阶段末尾给出完成条件。其禁止无复现循环时进入假设阶段的要求，不宜成为 SVC 通用调查的固定门槛。

本次没有安装或执行外部 Skills。可借鉴指针、起手动作和结束条件，不把作者关于注意力、措辞或效果的解释当作已经证明的性能保证。

## CLI 解耦边界

迁移前的打包钩子 `cli/pdm_build.py` 将 Corpus 带入 sdist 并投影到 wheel。 资源访问 `cli/src/svc_cli/resources.py` 同时支持 wheel 与源码回退。 lookup 完全消费 Corpus；init/status/upgrade 和配置保存并比较 Corpus 基线；集成块生成 lookup 导航；task 命令 `cli/src/svc_cli/task_packet.py`读取 Packet 模板并维护拓扑提示。因此只移除打包钩子不能完成解耦。

以上为迁移前事实；移除命令与 schema 4 的范围随后已获用户确认，现已实施。

## 尚缺证据

需要用相同任务比较现状与候选入口，记录正确触发、漏触发、误触发、首次有效行动前的无关读取，以及实际行动质量。宿主是否暴露描述、如何加载正文属于评测环境事实；Skills 安装边界不在当前决策范围。

## 方案收敛所需的补充调查

用户确认六 Skill 拆分后，进一步核对了 config、project、integration、task、输出 schema 注册、构建和发布 workflow。迁移前配置严格限定 schema 3，要求 `corpus_version`，overlay 也要求 schema 3；迁移前产品合同 明确 init 不执行配置迁移。upgrade 唯一的领域职责是 Corpus 基线采用，没有独立的 CLI 配置升级功能。

lookup、upgrade、task 命令在仓库测试、文档和 CI 中有消费者，调查没有找到真实外部项目或脚本的采用证据。这不证明没有外部用户，因此移除公开命令和改变配置版本仍是兼容范围的产品决定。

保留 task 命令并复制模板进 CLI 能保留机械便利，但会让规范模板落入 CLI 权威或产生副本；让调用者传入模板并将 grow 泛化为目录清单则新增接口。advisor 建议将任务指导、模板与操作全部归 Task Packet Skill，不新增这些接口。该方案不能把现有文件工具当作旧命令原子创建、路径保护等全部保证的等价实现。

advisor 还建议采用 schema 4 current-only 合同和人工迁移说明，而不是扩大 init 为自动迁移入口。精确计划机制虽可复用，但自动迁移还需要主配置与 overlay 的联合前置条件、受管块处理和失败状态合同；当前没有证据证明这些成本必要。用户随后确认移除命令并继续按 hard-cutoff 处理，兼容范围已经闭合，详见 [决策记录](decisions.md)。

[计划事务](../../cli/src/svc_cli/plans.py) 与 project/integration 仍从 catalog 导入 JSON 编码和散列小函数；删除 Corpus catalog 时必须保留这些真实事务消费者，并迁到既有机械 owner。CLI 的输出 schema 也位于 data 下，不能为了删除 Corpus 直接删除整个 data 目录。

共同规则的工程安排是继续由根 index 唯一拥有，六 Skill 与 Consumer AGENTS 使用加载指针，不复制完整规则。这是源码关系与完整采用的前提，不提前决定安装布局；没有常驻采用指针时，不能宣称全局约束已在所有 Skill 选择前生效。

## 实施后的导航试验

独立 Agent 先仅读取六份 name/description，再按场景选择正文和参考：未知间歇性测试失败选择 Methods→Explore，恢复与数据权威分歧选择 Methods→Design 及 technical、Taste implementation 参考，已知标点机械编辑判断无需 Skill 或 Packet。前两种场景能给出具体首动作、所需证据和转向条件，没有先遍历全部参考。共同契约可从所选入口到达。

这是源码路径下的只读实验，没有创建 Packet 或执行变更，不能证明宿主自动注入、真实安装布局或统计触发可靠性；也没有同条件迁移前后性能对照。试验支持入口可理解与按条件导航，不支持量化导航性能提升。
