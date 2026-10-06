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
