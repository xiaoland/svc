# 改进 svc-verification

当前状态：用户已认可 [Design](design.md)，并于 2026-10-06 明确授权实施。新方案已落实，此前未采纳草稿已替换，相邻责任归并与内容核对完成。本次未授权提交或发布。

目标：基于 factory26 的 V&V 会话，让 Agent 建立、使用和改进产品迭代的判断依据，以可信、及时、成本可控的反馈约束实现搜索，同时保留满足要求的实现自由。

输入：[会话总结](../../../factory26/tasks/verification-system.md) 和原会话中的用户消息及关键回答是讨论材料，不是标准或已验证的通用流程。[Inquiry](inquiry.md) 保存重新整理的认识依据；Design 保存获认可的内容方案。前序 Skills 分发工作已提交为 f30896e，与本次修改分开。

边界：保持 Human 权限与验收责任、所有非平凡任务使用 Task Packet，以及六个 Skill 独立安装和使用的能力。正文按语义段落换行；不新增 Corpus 测试、验证平台、固定测试比例、强制 E2E 或全量 test-first。

## 实施与责任

svc-verification 的入口与三份 reference 由 verification_content 实施，主 Agent 接收并核对语义边界。入口从产品目的、行为要求、观察与判定的关系推导行动；深入内容分别处理要求与判据、证据取得与解释、反馈与演进。原草稿的两份 reference 被替换。

主 Agent 负责相邻 Methods、框架导航、版本及任务材料。根据 verification_advisor 对专业所有权和独立使用边界的判断，删除 Methods 的 test-design.md，将必要的协调与最小观察责任收回 Design；专业 V&V 指导由 svc-verification 唯一维护。Implementation 在反馈或判据需要改进时按名发现 VV；这些路由不要求安装其它 Skill。

用户指出此前将开发阶段逐次升至 16.2.0、17.0.0 是错误的：这些调整尚未发布，仍共同归入 v15。本任务及后续 [Agent 协作任务](../agent-collaboration/packet.md) 的共同 Corpus 预备版本为 15.0.0，CLI 同为 15.0.0。六个 metadata 使用现有发布准备命令同步，没有发布发行物，也不把源码版本当作已可下载版本。

## 核对与完成边界

内容核对确认：入口解释产品目的、要求、观察与判定的区别，并连接到立即行动；Oracle 的双向辨别保留明确合同细节的例外，观察载体与规范预期分开；条件选择与判据不同，局部/组合/产品路径的证据互补而不天然独立；既有静态保证可按假设复用；反馈从判据和时延影响实现搜索推导 TDD、整体检查与演进。Methods 的 Design 仍能独立选择要求相关的观察并返回缺口，不要求安装 VV。

`pdm run prepare-corpus-release` 已同步六个 Skill metadata 与许可副本。`pdm run check-skills`、`SVC_BASE_REF=HEAD pdm run check-corpus-release` 和 `git diff --check` 通过；旧 references 和 test-design.md 的当前 Corpus 引用已移除。机械检查只能确认源结构，不能证明模型发现、加载与执行的实际收益。CLI 源未变，不因纯指导改写重复 CLI 测试。

此前草稿虽通过静态检查及一个只读场景实验，但用户指出其未触及问题核心，不能作为本轮内容有效性的证据。该实验首轮也出现过度推断，经针对原输入追问才修正；它不能证明自动触发、无提示执行或真实产品验证可靠性。本轮不以新增模拟测试代替实际采用观察。

后续工作（2026-10-06）：用户已授权 [Workflow 合并任务](../human-agent-working-models/packet.md)。Methods 与 Verification 归入 svc-workflow，当前源与分发合同收敛为五入口；上述六入口和各次检查描述当时实施事实。V&V 的语义及三份深入参考保留在 Workflow 内，Agent Collaboration 的可选发现指向 Workflow。版本仍为未发布 15.0.0，无自动跨名迁移或额外发布。

最新修订：用户随后决定保留独立svc-verification，入口与三份专业参考已恢复，Workflow仅按名字发现；当前最终六入口，15.0.0不变。上段五入口描述已被此决定覆盖。
