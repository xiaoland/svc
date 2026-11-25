# Shared Execution Contract

Use this [Product TDD](index.md) depth when `run` and `dev` must share process execution without sharing domain authority. It returns the cross-unit identity, ownership, lifecycle, and failure contract; Product behavior and runtime data locations remain with Product Truth and Deployment.

dev 资源领域合同由 [App／CLI 资源合同](macos-client.md#资源合同) 拥有：有限动作竞争返回 busy，wait 动作不转发中断信号，未解决 owner-lost 持续阻断变更。这些规则不改变 run 或 double 的领域语义；共享机制只拥有锁、进程、日志和机械状态。

`run` and `dev` are separate public/configuration domains that share only a private mechanical execution boundary. Domain controllers derive convergence identity and retain semantic authority: declared `run` owns one named bounded command intent in a worktree; resource `dev` owns observations, explicit action completion, convergence, coordination scope, and recovery. The shared mechanism owns one concrete execution ID, atomic lifecycle facts, process ownership, policy-selected capture, observation, settlement, and explicit release. Its neutral persisted identity is `domain`, `operation`, `subject`, `workspace_instance`, `intent_digest`, and `coordination_key`; domain projections restore names such as run entry/effective-entry digest or dev resource/declaration digest.

一次性 `dev exec` 由 [activity 单元](activity.md)拥有，以 run/managed 复用 schema 2 的独立有限执行和 split 日志，不参与具名 run 的收敛或 follow／inspect。它使用独立 session 和受控请求通道；保留未回收主进程直到组收敛的规则仅用于该入口，不改变旧 run 或资源动作的终止语义。机械记录不因出现这个公共入口变成任意历史 PID 的控制凭据。

One coordination lock is the ownership authority. The winning caller holds it from publication through domain settlement; the domain decides whether contenders may join or must return busy. Run retains its existing wait/re-evaluate behavior; dev finite actions do not queue. The execution record is authoritative for its neutral identity, resolved argv/cwd, non-secret env-file paths, log addresses, owner PID, timestamps, and mechanical state. Native output remains project-owned bytes addressed through exact log references rather than being interpreted as SVC results.

Run lifecycle is `starting -> running -> exited | interrupted | start-failed | capture-failed | owner-lost`. Dev may additionally request `released` only after its own readiness proof. An abandoned lifetime lock plus an active record proves owner loss; the first later caller records that fact without starting a replacement in the same invocation. PID observation alone never grants takeover or kill authority.

Dev keeps entry identity separate from coordination identity and observed instance identity. Direct coordination keys retain the existing namespace, scope, scope ID and resource-key algorithm. Explicit one-hop owners share coordination only. The domain re-parses under the lock, rejects stale declarations, and settles its complete receipt atomically in dev metadata. Mechanical exited/released does not prove domain settlement. A pending dev record whose lifetime lock is abandoned remains blocked until explicit reconciliation, without PID takeover.

Foreground run inherits stdin and the terminal process group, captures stdout and stderr separately, and stays owned until child exit plus both stream EOFs. An owner interrupt affects the execution; a follower interrupt only detaches that caller. Dev provisioners remain isolated with null stdin and merged logs. No shared public lifecycle API, daemon, process-tree guarantee, output-order invention, readiness state, or project-artifact model follows from this reuse. Schema-v1 execution records are an unreleased local cutoff: a still-held legacy lifetime lock blocks v2 publication, settled files remain untouched, and explicit inspection fails with `execution-record-schema-unsupported` rather than field aliases or PID action.


前台 run 的启动回调允许其领域控制器在机械 running 记录发布后保存可选观察来源，回调不转移进程句柄或协调锁。项目与用量来源由 [activity 合同](activity.md#项目归属与用量观察)拥有，保存在独立补充文件，不能给严格的机械 schema 2 加入客户端显示字段，也不能据此改变 wait、ready 释放或控制权限。
