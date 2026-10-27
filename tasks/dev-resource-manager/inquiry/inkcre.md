# InKCre：复合资源、跨仓引用与控制归属

2026-10-27 读取本地工作树。InKCre 是多仓目录；本轮深入核对 impl-py、impl-ts，补充读取 ui、ext-reg、docs website 与 impl-swift 的开发入口。没有启动服务、读取凭据或连接远端。

观察时 HEAD 与已跟踪变更数：impl-py `c5e672fe155017bc200529ff450cab7353f6aa59`／17；impl-ts `b683c752ab127e6cdad2b75c49ffca7373dbee9b`／44；ui `34c330d0a8d750e6bd30ca96bd8c7921ae0b7ee3`／0；ext-reg `60879eb437c29108a85873e2745e0b5b854787c0`／6；docs `089fec913805ce9ffa15662f9f3250342c0b24bf`／28；impl-swift `d569cab6e591ef9a41a3c6daf13826eac4713db4`／68。结论描述读取时的文件，不能只用这些 HEAD 重建未提交状态。

## 已观察事实

| 编号 | 资源与现有控制 | 证据与边界 |
| --- | --- | --- |
| I1 | impl-py 的 `database` 是 worktree 级复合 runtime，包含 PostgreSQL/pgvector、初始化、Core 与 PostgREST；本机 overlay 选择 SSH provider，本地通过 loopback 隧道访问。 | [开发说明](/Users/lanzhijiang/Development/InKCre/impl-py/docs/40-deployment/development-environment.md)、[声明](/Users/lanzhijiang/Development/InKCre/impl-py/svc.json)、[provider 解析](/Users/lanzhijiang/Development/InKCre/impl-py/scripts/dev_database_provider.py)。只读取本地 overlay 的 provider 与环境变量名称，没有读取 runtime 凭据；配置不证明远端当前可用。 |
| I2 | impl-py 的 `stop` 执行 `compose down --volumes --remove-orphans`，关闭其隧道并删除 runtime 目录；它会删除开发数据库中的数据。 | [停止实现](/Users/lanzhijiang/Development/InKCre/impl-py/scripts/dev_database.py:592)。本地 AGENTS 也明确禁止仅为修复探测不一致而调用它。 |
| I3 | impl-ts 支持 local、ssh、external provider；当前本机配置选择 external，通过绝对 descriptor 引用 impl-py runtime。external ensure 复用所选状态，stop 明确拒绝销毁 impl-py 拥有的 runtime。 | [provider](/Users/lanzhijiang/Development/InKCre/impl-ts/scripts/database-provider.mjs:72)、[ensure／stop](/Users/lanzhijiang/Development/InKCre/impl-ts/scripts/database-runtime-lib.mjs:303)、[运行合同](/Users/lanzhijiang/Development/InKCre/impl-ts/docs/40-deployment/development-runtime.md)。未读取 descriptor 内容，因此不声称当前共享链路已经收敛。 |
| I4 | web、web-ui、webext 有 worktree 级 Portless HTTPS 地址；probe 校验返回的 instance、target，web-ui 还可校验本机 UI 源目录身份。 | [声明](/Users/lanzhijiang/Development/InKCre/impl-ts/svc.json)、[探测](/Users/lanzhijiang/Development/InKCre/impl-ts/scripts/probe-dev.mjs)。有端口响应不足以证明访问了所选工作树。 |
| I5 | `pnpm dev` 的脚本先 ensure database，再 ensure web；通过 SVC 直接进入已声明 web 的 provision 分支时只启动该 web 目标。`dev:stop` 按实例挑选 Portless routes，再尝试清理数据库。 | [启动脚本](/Users/lanzhijiang/Development/InKCre/impl-ts/scripts/dev.mjs)、[停止脚本](/Users/lanzhijiang/Development/InKCre/impl-ts/scripts/dev-stop.mjs)。调用入口不同会改变作用范围，不能把同名操作或项目级脚本默认为逐资源动作。 |
| I6 | UI 有 Vite/Histoire，docs 有 VitePress，ext-reg 有本地 Wrangler Worker 与 D1 初始化；ui、docs、ext-reg 的 `svc.json` 没有 dev targets。 | [UI scripts](/Users/lanzhijiang/Development/InKCre/ui/packages/web/package.json:79)、[文档站 scripts](/Users/lanzhijiang/Development/InKCre/docs/website/package.json)、[Registry 本地入口](/Users/lanzhijiang/Development/InKCre/ext-reg/docs/40-deployment/local-development.md)。已有开发资源并不全部在 SVC 声明中。 |
| I7 | impl-swift 以固定 bundle 身份和显式开发签名进行反复原生验证；系统授权依赖签名身份，运行依赖外部 info-base 和 Capture 执行者；关闭主窗口不会结束进程。 | [原生开发说明](/Users/lanzhijiang/Development/InKCre/impl-swift/README.md)、[打包脚本](/Users/lanzhijiang/Development/InKCre/impl-swift/scripts/build-app.sh)。安装产物、运行实例、连接目标和系统权限是不同事实。 |

## 对产品判断的影响

I1 与 I3 支持资源运行位置、访问通路、控制所有者和引用方分别表达。一个数据库可以被多个仓库引用，但引用方不因此获得销毁权；也不能仅凭两个 target 都叫 database 就合并。

I2 直接说明当前 `stop.kind=exec` 只回答动作如何执行，没有表达保留数据、销毁数据或等待完成等后果。资源管理界面必须避免把这个动作呈现为普通的无损停止；本轮没有修改现有合同或界面。

I4 与 I5 支持展示实例身份和真实动作范围。既有脚本中的准备顺序是可以引用的显式关系，不需要从 Agent 任务、分支名称或所谓开发意图推断。

I6 支持复用已有脚本并登记资源的需要，但尚未决定登记机制。I7 提醒原生资源不适合统一为端口健康检查；系统授权与应用业务连接仍由原生产品拥有。

## 残余

没有执行 probe，未证明远端 runtime 在线或两个仓库目前指向同一健康实例。未深入所有扩展和 worktrees。impl-kotlin 的 README 仍是 CameraX 示例形状，不能据此宣布它有成熟的开发资源合同；此仓仅做入口筛查。没有评估自动发现的精度，也未将本机 overlay 的私有路径、主机或凭据复制进提案。
