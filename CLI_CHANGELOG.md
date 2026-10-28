## [18.1.0] - 2026-10-28

### Added

- 增加 `dev monitor`、`dev exec` 与 `dev terminate`：人和 Agent 共用带时间的主机压力、跨项目执行清单与终止回执。macOS 临时命令无需项目配置，实际 owner 控制隔离进程组；主进程先退出不提前宣称组结束，人为终止后不自动重试。既有资源与具名 run 合同不变。 (#20261028-execution-pressure)


## [18.0.0] - 2026-10-27

### Changed

- 项目配置升级为 schema 5，以开发资源、具名观察和显式动作替换 targets；新增 list/act/reconcile，支持等待、异步提交与未知结果恢复。旧配置需人工迁移并排空旧客户端调用。 (#resource-manager)



## [17.0.0] - 2026-10-26

此版本随 macOS 0.1.0 预览附件公开，未单独发布到 PyPI。

### Changed

- `svc dev status --json` 的目标观察新增 `stop.kind`（`absent`、`manual` 或 `exec`），使图形客户端可以在执行之前展示停止能力。该查询不执行停止动作；dev-status 结果 schema 升为 3，其他 dev 命令保持原有 schema。严格依赖 schema 2 的消费者需要更新；依据当前 schema 版本政策，CLI package 升为 17.0.0；macOS 预览随附同一源码的 wheel，PyPI 发布仍由 CLI 独立发布流程负责。 (#20261026-dev-status-stop)


## [16.0.0] - 2026-10-06

### Changed

- Skills 安装与更新只下载所选 Skill 独立 ZIP，检查通过发布清单比较文件摘要；支持带发布清单的离线独立包，保留已发布 v15 整体包的读取和安装记录。


## [15.0.0] - 2026-10-06

### Added

- 新增独立 Skills 发行安装、状态、升级检查、明确换版与移除；正文不进入 CLI 包。文件操作使用精确计划和逐 Skill 基线保护，第三方或定制内容保持原样。项目采用与取消采用使用独立的有界常驻指令块，不变换 CLI 配置或自动迁移消费者资料。 (#20261005-skills-management)
- 新增携带完整 payload 的 Agent 轨迹、Codex/Pi 执行拓扑、子 Agent 与分支感知用量分析，以及 analysis v3 的 overview、trace、profile、match 和 read 合同。

### Changed

- CLI 配置切换为 schema 4，删除 `corpus_version`；旧主配置及 overlay 按 hard-cutoff 拒绝且不改写，需人工更新 schema 并保留其余声明。`init/status` 只管理工具配置与集成，受管导航改为 CLI 工具入口，继续保护消费者内容、修改过的生成块与精确计划文件事务。 (#corpus-skills)
- 在 v15 开发期间，Skills 安装、检查与采用的当前六入口将 `svc-sub-agents` 替换为 `svc-agent-collaboration`。CLI 仅接受包含当前六个 Skill 的发行归档，拒绝开发期间的旧六入口或新旧混合归档；默认操作不再选择旧名。已有旧名开发安装仍可通过显式 `--skill svc-sub-agents` 查看和移除，修改过的文件继续受保护。迁移前应确认当前发行物和目标安装位置可用；安装新入口后重新执行 `skills adopt` 可刷新未修改的采用块，并保留块外的项目内容。CLI 不添加别名、不自动重命名目录，也不把跨命令迁移视为原子操作。 (#20261006-agent-collaboration)
- 将 Skills 归档、默认安装及项目采用入口收敛到含 svc-workflow 和独立 svc-verification 的六入口合同；保留旧 Methods 草稿安装记录的显式检查和受保护移除，不自动跨名迁移、不携带 Corpus 正文。此调整归入 v15。 (#20261006-human-agent-workflow)
- CLI 工程移至 `cli/`，其标准 Python src layout 保持为 `cli/src/svc_cli/`。

### Removed

- 移除 `lookup`、`upgrade` 和 `task init/grow`，CLI 不再携带 Corpus 正文、模板或 catalog；Skills 安装管理由独立的 skills 命令消费发行物；任务文件操作由 Task Packet Skill 指导。 (#corpus-skills)
- v15 删除历史 CLI 配置迁移和旧机器合同兼容；旧输入现在只返回明确的拒绝结果。

### Fixed

- 修正 analysis 帮助中的旧版导航流程：通过 match 和 trace 获取关联上下文，仅在精确恢复或原生审计时使用 read。 (#analysis-trace-help)
