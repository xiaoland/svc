# Sustainable Vibe Coding distribution

This member builds the `sustainable-vibe-coding` Python distribution: the `svc` command and its local development-collaboration runtime. Framework guidance is released separately as six self-contained Agent Skills. `svc skills` installs an explicit official release or offline archive, protects local modifications, and manages project adoption separately from installation. The CLI package contains no Corpus content and builds independently of the parent repository.

The canonical framework source and repository development instructions remain in the workspace root. This file owns only package-index metadata for the independently rebuildable member distribution. The distribution is licensed under MIT and carries its own license notice.

SVC Dev 通过 `dev list`、`dev status`、`dev act` 和 `dev reconcile` 提供开发资源接口，CLI 18.1 另以 `dev monitor`、`dev exec` 和 `dev terminate` 提供本机压力与一次性受管执行。macOS App 是同一能力的图形入口，不拥有额外的配置或进程权限。资源配置要求 schema 5；机器采样与临时执行无需项目配置。一次性执行目前支持 macOS；终止只请求实际 owner 控制本次进程组，不从历史 PID 接管。迁移和生命周期边界见仓库用户手册。


CLI 18.2 的 monitor 进一步提供项目归属、已观测进程用量及系统 swap／压缩活动。dev exec 可用 --project 明确来源，省略时只在启动时查最近 svc.json 祖先。用量来自可验证本机进程，页面读入不等于 swap，也不新增旧执行或资源的终止权限；公开 monitor 结果升级为 schema 2，exec／terminate schema 1 保持不变。


CLI 18.3 的 dev monitor schema 3 增加独立原生执行与来源状态，dev integrate 安装 Pi Host API 桥接或配置现有 Codex／Claude 入口，dev logs 读取来源允许的有界日志。Pi 管理后台任务，Codex 必须连接拥有终端的同一 app-server，Claude 原生 stop 管理整个后台会话；交互会话只读。不从旧 PID 接管，不把外部记录写成 SVC 自己启动的执行；缺失指标保持未知。
