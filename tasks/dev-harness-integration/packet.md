# 原生 Agent 执行接入

用户先要求调查 Pi／Codex，随后追加 Claude Code 并明确“三者一起做”，已授权实现、本机提交和安装。沿用 App 0.2.0、低负载、不打扰前台及不增加自动化测试的约束；本轮仅写有限验收脚本，没有新增测试。此前仅调查的限制已由实现请求替代；本轮不公开发布或推送。

SVC 拥有跨来源展示、项目归属与已验证用量，原 harness 拥有执行生命周期和原生停止。外部执行采用独立投影和来源实例＋原生 ID，不伪装为 ExecutionStore 启动的进程，不从旧 PID 接管。Pi 为单项后台任务，Codex 为原生后台终端，Claude 为整个后台会话；Claude 交互会话只读，内层 Bash 不冒充独立可控制任务。三种连接状态区分未接入与空清单。

当前实现包括公开 CLI、Pi activation 内桥接、Codex Unix WebSocket、Claude 原生 agents／logs／stop，以及 App 项目执行页、来源设置、日志和停止确认。所有来源共享 3 秒读取预算；单项来源故障不阻塞主机采样。项目归属优先当前 cwd 所在的最深 App 项目根，外部用量复用物理进程去重。公开 monitor schema 3、logs／integrate schema 1，CLI 18.3.0；App 始终保持 0.2.0。另一个用户授权的侧会话已在 d53d93c 将 App 改为依赖用户安装的 CLI，本轮继续该边界，安装器不会部署私有 runtime。

Pi 真实 pi-background-tasks 2.6.10 registry＋Host API 已通过清单、最近日志、原生停止、密钥拒绝和重载后旧 ID 失效；Claude 2.1.292 在隔离原生配置下创建无输入后台会话，已通过列举／日志／整个会话停止。Codex 真实私有 Unix WebSocket 握手、后台终端列举与停止也已通过：按独立 advisor 建议，以本机固定 Responses 事件驱动真实 app-server 创建 unified_exec；实际原生终端停止后从清单移除，原连接收到命令完成通知，没有调用真实模型。此前 shellCommand 空清单符合另一执行路径，已用有判别力的原生验收替代。当前 Desktop 未开放默认共享入口，不能宣称已附着 Desktop。

原生离屏检查覆盖 420／740 宽度、明暗外观、图标可访问名称、详情及停止确认；应用未激活、宿主没有前台窗口。App 实际 CLIClient 已经通过 monitor／logs／terminate 与真实 Pi Host 相连，并确认结果。实现已提交 f37fc2c，并安装 /Applications/SVC.app 0.2.0（84）；Apple Development 身份与 Team 7J9DJNJ782 的严格校验通过，实际进程来自该路径并以 --background 启动。安装前后全部六项偏好相同，保留三个当前项目。既有 pdm run check 已通过 259 项，Swift 既有 13 项通过（条件生命周期／离屏项按原开关跳过）；之后的有意义修改按影响复核。持久合同放在 docs/product-tdd/activity.md 及 macos-client.md，使用说明在 USER_MANUAL.md。

实施路线见 [plan.md](plan.md)，协议研究及有限观察位于 evidence／scripts。Human 当前无需额外决定；App 视觉体验仍留给真实使用反馈，脚本结果不等同于 Human 接受。


本机系统 CLI 已由 mise 选择用户目录 local-cli/18.3.0，不是 App 私有 runtime；wheel 保留在 ~/.local/share/svc/artifacts/18.3.0，App 安装器没有安装 CLI。Pi 扩展已由已安装 wheel 写入并逐字节核对；现有 Pi 未自动重载，也没有向用户会话发消息。当前机器的 Pi 等待加载、Codex 默认共享入口仍不可用、Claude 自动连接；真实安装包的 Python runtime 再次通过三种原生来源的有限验收。没有推送或发布，没有新增自动化测试，没有遗留本轮验收服务器或睡眠任务。

本轮已交付。Codex Desktop 的共享入口可用性与 Pi 当前会话重载是使用条件；不能用独立验收实例冒充已接入日常 Desktop。Human 可从执行页及设置查看实际状态并反馈体验。源实现、既有检查、真实原生脚本、离屏图与 installation.json 构成证据，不替代 Human 接受。
