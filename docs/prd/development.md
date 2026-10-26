# Declared Development Capabilities

Use this [Product Truth](index.md) projection when a project declares a long-lived development capability. It owns what independent callers can observe and request; cross-domain execution mechanics and runtime persistence remain with Product TDD and Deployment.

SVC lets independent Agent, Human, editor, and CI callers observe and express one named long-lived development capability without starting the same intent twice. Readiness, coordination scope, provisioning, access, and optional stop cleanup remain Consumer declarations integrated by SVC rather than reimplementations of HTTP servers, package managers, Compose, or project scripts. Once readiness is proved, the capability survives the starter CLI and native output remains available through a stable shared log.

Ensure and stop serialize at the same capability boundary, while equivalent callers converge on the same observable execution. Stop runs only declared Consumer cleanup and verifies the final readiness state; a historical PID is never cleanup authority. This preserves Consumer ownership rules such as an attached client refusing to tear down another repository's runtime.

## CLI Contract

An optional `dev.targets` map declares named capabilities directly. Each target has a scope (`worktree`, `repository`, or `host`), one readiness probe (`http`, `tcp`, or `exec`), an executable or manual provisioner, and an optional target-local executable or manual `stop` action. Default text serves ordinary Agent/Human use; compact JSON is the deliberate scripts/CI projection:

```bash
svc dev identity --repo /path/to/project --json
svc dev status --repo /path/to/project --json
svc dev status frontend --repo /path/to/project --json
svc dev ensure frontend --repo /path/to/project --json
svc dev stop frontend --repo /path/to/project --json
```

Root `status` summarizes declarations only; `svc dev status` observes declared targets without starting or taking over a process. `ensure` handles one declared target, reuses a healthy endpoint, refuses an occupied but unhealthy endpoint, and does not run a `manual` provisioner. `stop` runs only Consumer-declared cleanup and never infers authority from a recorded PID. Executable work is coordinated at the declared scope and releases process authority once readiness succeeds. Worktree scope is the default and its probe endpoint must prove the resolved instance; host scope requires a declared `host_key`.

Dev values may interpolate only `${dev.instance}`, `${dev.worktree.id}`, and `${dev.target}`. Commands are argument arrays, not shell snippets, and their configured working directories must remain inside the workspace.

## macOS 菜单栏客户端

原生 macOS App 为用户添加的本机项目和工作树提供统一入口，查看 `dev.targets` 的当前就绪状态，并逐项启动、停止和访问服务。它沿用上述 CLI 控制与共享规则，不独立解析配置或接管进程。CLI 公开返回停止能力，App 据此区分自动停止、手动操作和未声明停止；查询不执行停止动作。两者的职责、调用和版本兼容由 [App 与 CLI 合同](../product-tdd/macos-client.md) 拥有。

面板区分就绪、未就绪、有响应但不健康和状态未知。检查失败不能延续旧的就绪结论，未就绪也不能单独证明进程已停止。关闭面板、移除项目或退出 App 不停止已经就绪的服务。日志入口只展示实际操作回执可提供的日志，不承诺所有服务的历史或实时日志。构建、设置与本地验收入口见 [macOS App](../../macos/README.md)。
