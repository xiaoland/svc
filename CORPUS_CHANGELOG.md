## [16.0.1] - 2026-10-17

### Changed

- 将六个 Skill 的 description 精简为直接、明确的使用条件，便于 Agent 从 catalog 识别适用入口；保留正文职责、权限和独立使用边界。 (#skill-catalog-triggers)
- Task Packet 入口直接提供轻量形状检查，简单线性任务不必读取增长参考；已知的独立计划所有者、并行关注点、共享依赖或检索编辑压力仍须及早识别并按需展开。Workflow 的 Verification 路由改用判据不清、观测不足、证据选择或复用不确定、检查与实际结果冲突等可识别条件，已有充分判据和适用证据可直接使用。Taste 的实现参考及 Workflow 实现路由补齐性能取舍条件；独立 Skill 的最小责任和授权边界不变。 (#skill-entry-boundaries)
- 重排六个 Skill 入口，使核心动作、返回和条件参考更容易定位：Workflow 前置当前任务恢复；Task Packet、Specs 和 Taste 压缩重复前言，分别突出状态维护、知识归属和判断依据；Verification 按主张、已有证据、必要观察及限定结论组织；Agent Collaboration 按 owner 选择、责任委派、效果协调与结果采用组织。保留独立安装所需的授权和任务连续性边界，不增加统一阶段或公共依赖。Taste 作者扩展指导归入维护者合同，消费者所需的理由、代价和反向条件仍在入口。

  进一步精简六入口正文的重复解释与抽象措辞，改用直接的动作和对象；保留章节、description、参考条件、授权范围、例外和完成责任，不以删减必要边界换取篇幅。 (#skill-entry-core-organization)
- 每个非平凡任务必读并使用 svc-workflow，涵盖人机协作模式与 Agent 自主工作的探索、设计、规划和实现方法，人类不在场时方法仍适用。入口直接以“明确并确认、在反馈中实现、验证与交付”的产出和推进条件规定默认阶段式，足以开始工作，参考仅按需展开；实现阶段用局部反馈推进和修复，交付阶段核对证据是否支持约定范围，复用充分证据，只补实际缺口。同步 description、消费者指导模板和采用说明。已有项目约定或人类直接指令可选择持续迭代式；Agent 在尚未确认的实质承诺边界核对，已有明确授权继续有效，不增加逐步骤审批。 (#staged-collaboration-default)

### Fixed

- 明确 Agent 协作以完整成果为委派边界：执行者默认独立完成调查、实施、修复和验证后返回，调用方不逐步介入。中途交互仅用于不能等到最终交付的变化或阻塞，以及能提前解除实际依赖的可采用成果；宿主自动交付最终答复时不再主动重复发送完成内容，信息更新不默认要求确认。补齐复用 sub-agent 的适用范围，保留原负责人继续修复、权限边界与必要交接责任。

  精简主文为可独立执行的正常协作路径，补充被委派方接受责任和返回成果的触发；将深入指导按安排责任、采用返回、执行协调、交接恢复拆分，只有对应困难或例外才加载。删除重复展开和通用验证方法，保留开放判断、共享影响及在途操作的必要边界。 (#agent-independent-completion)


## [16.0.0] - 2026-10-06

### Changed

- 从 v16 起按 Skill 发布六个纯源码 ZIP、各自 SHA-256 和外部发布清单，不再生成整体 Corpus ZIP；保持共同发布版本。旧 v15 CLI 必须升级后才能消费新发行格式。


## [15.0.0] - 2026-10-06

### Changed

- 在 v15 开发期间，将 svc-sub-agents 草稿入口收敛为 svc-agent-collaboration，移除旧地址与 Explorer/Executor reference；不另行增加发布版本。指导从协作的认知与执行收益、理解分叉、责任连续性、结果采用与共享影响推导行动，覆盖 sub-agent、独立会话、依赖协调及责任转移；采用依据按主张选择，不再强制星形拓扑或普遍独立 validator 前置要求。新增草稿安装整理、消费者指针更新及当前 CLI 归档合同的说明；不授予额外权限、不改变非平凡任务的 Task Packet 义务。 (#20261006-agent-collaboration)
- 将 Corpus 重组为六个 Agent Skills：Task Packet、Workflow、Verification、Agent Collaboration、Specs 与 Taste。旧概念目录地址移除，深层指导与模板归入唯一所有者的 references/assets；各入口明确触发条件、按需加载、首动作和返回边界，正文不再按固定列宽换行。
  保留 Task Packet 对所有非平凡任务的职责和共同协作权限契约；消费者应更新常驻指针及旧内容引用，采用指导不再依赖 CLI 携带或检索框架内容。

  各 Skill 内含执行所需的权限与任务责任边界，本地资源引用不越出 Skill 目录；根 index 仅作介绍和导航，跨 Skill 指导按名称条件发现，不要求父级文件或其它 Skill 已安装。 (#20261005-agent-skills)
- 将 svc-methods 升级为独立 svc-workflow：以阶段确认式和持续迭代式规范人机协作，按当前缺口组合 Explore、Design、Planning 和 Implementation，并按名称发现独立 svc-verification 的判据、证据与反馈指导。保留各自最低工作责任与独立安装能力；六入口共用 v15，不保留 Methods 旧名别名。 (#20261006-human-agent-workflow)
- Corpus 版本统一由根 `pyproject.toml` 管理，发布准备会同步六个 Skill 的 `metadata.version`。Corpus Release 提供包含六个自包含 Skill、manifest 和外部 SHA-256 校验文件的精简 ZIP；CLI 不携带这些正文。 (#20261005-skills-release)
- 扩展独立 svc-verification 的 V&V 指导：从产品目的与行为约束推导判据、条件选择、观察证据和实现反馈，明确 Oracle 对需求差异敏感、对保持需求的实现变化不敏感。提供三份按需指导，覆盖要求与判据、证据取得与解释、反馈与演进；归并 Methods 的 Test Design 专业内容，保留 Design 的协调责任与独立使用能力。保持 Task Packet、Human 验收和效果权限边界，不新增强制流程或 Skill 安装依赖。 (#20261006-verification-vv)
- Corpus 权威源移至明确命名的 `corpus/`；Corpus 与 CLI 从此使用独立版本和发布记录。

### Removed

- v15 将 Corpus 建立为新的兼容锚点，不再携带 v10–v14 的运行时迁移选择链。

### Fixed

- 明确 Design 如何从代表性用户旅程形成决策，以及 Implementation 如何在规划前探测可能改变实施路线的未知条件。 (#factory26-method-routes)
