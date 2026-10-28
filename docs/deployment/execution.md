# Local Execution Runtime

Use this [Deployment](index.md) depth when operators or developers need the runtime authority, storage, recovery, and platform behavior shared by `run` and `dev`. Product-visible behavior and cross-unit identity remain with Product Truth and Product TDD.

Shared execution evidence lives under the platform user runtime directory in an `svc/execution` tree. Each UUIDv4 execution has one strict atomically replaced schema-v2 JSON record and policy-selected byte logs; domain coordination pointers and locks are derived from semantic coordination keys. Paths, records, and domain identifiers are validated before access. Files request user-only permissions where supported, but this is the established same-user trust boundary, not protection from a hostile process under the same account.

The runtime is local operational evidence, not archival storage. It may be removed by reboot or platform cleanup, and the first slice adds neither an automatic retention policy nor a reset command. Settled records are not automatically deleted. Missing, malformed, mismatched, or partially published authority fails closed so SVC cannot start a duplicate or fabricate a receipt. Writes use same-directory temporary files and atomic replacement.

The initiating run CLI retains the lifetime lock and child handle. If it is lost uncatchably, an orphan child may remain; the next caller may record `owner-lost` only after acquiring the abandoned lock and must not replace the execution in that invocation. Dev ready actions may deliberately persist `released` after readiness and then relinquish its handle. After release, later dev authority comes from declared observations rather than the historical PID, and complete process-lifetime log capture is not promised.

On POSIX, isolated dev attempts use null stdin, merged log redirection, and a new session so a ready released capability is not tied to the starter terminal. Windows uses `DETACHED_PROCESS`, `CREATE_NEW_PROCESS_GROUP`, and `CREATE_BREAKAWAY_FROM_JOB`: console detachment and job breakaway are separate requirements, and process-group creation alone does not preserve a child when an OpenSSH session job closes. A parent job that forbids breakaway makes launch fail instead of silently weakening persistence. For a terminate-policy action SVC still owns, interruption targets only that exact process group or tree; Windows uses `taskkill /T /F` because a detached process cannot receive the starter console's control event. Wait-policy actions retain ownership until the child actually exits and do not forward SIGINT/SIGTERM. Once released, only explicitly declared actions may control the resource; historical PIDs confer no authority.

## dev 恢复记录

dev 资源按 [App／CLI 合同](../product-tdd/macos-client.md#资源合同) 保持机械 ExecutionRecord schema 2，在其 execution 目录保存 dev 专属 schema 1 补充记录，绑定协调身份和具体 execution ID。补充记录拥有 pending／settled／owner-lost、完整领域回执及单独的恢复确认；机械 exited／released 不证明领域已结算。控制启动前必须依次完成机械记录、pending 元数据和协调指针的发布，任何必要发布失败都不能启动；完整回执与 settled 原子写入。取得无人持有的生命周期锁而领域仍 pending 时持续阻断，机械已有的退出事实保留。确认不覆盖原未知结果，也不启动新的控制动作。运行记录仍是本机、同用户、可能被系统清理的操作证据，不升级为持久资源登记库或业务日志；不能把记录已丢失的情况宣称为已证明旧动作安全结束。恢复入口为 `dev reconcile <resource> --execution <id> --acknowledge-unknown`。

## 一次性受管执行

`dev exec` 在同一 execution 树中保存 run/managed 的 schema 2 记录、stdout.log、stderr.log，以及 activity 拥有的 management.json／termination.json schema 1。后者不复制机械状态；短的 termination.lock 只保护请求升级，生命周期仍由协调锁和前台 CLI 拥有。异常组观察另记 group-error.json，不能将其缺失或损坏解释为组已结束。所有文件仍属于同用户 runtime 信任边界，可能被系统清理；项目配置和持久资源目录不受影响。

App 通过 CLI 使用相同平台 runtime，不扫描自己的另一份数据库。macOS 进程组查询与主进程回收规则见[主机与受管执行合同](../product-tdd/activity.md)。owner 被不可捕获地终止后可能留下孤儿，后续查询只记录 owner-lost，不重新获得控制权。命令自行离开 session／进程组或提交远端操作时，其后续工作不属于本次终止承诺。
