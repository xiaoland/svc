# bl-gallery：多服务入口、持久数据与等待在途工作的停止

2026-10-27 读取本地工作树，HEAD `c2706414f473ec1f971730342aeeda16aa1d191f`，26 项已跟踪变更。未读取书库／图片／模型缓存／密钥，未启动服务或请求模型。

## 已观察事实

| 编号 | 资源与现有控制 | 证据与边界 |
| --- | --- | --- |
| B1 | `pnpm dev` 并行启动 Vue/Vite 与 Hono API，默认 5173／8080；`pnpm start` 运行构建后的 API。开发启动不发起分类。 | [根 scripts](/Users/lanzhijiang/Development/bl-gallery/package.json)、[前端代理](/Users/lanzhijiang/Development/bl-gallery/web/vite.config.js:8)、[API 监听](/Users/lanzhijiang/Development/bl-gallery/server/src/index.ts:398)。一个项目已有多个可独立访问的资源。 |
| B2 | Observer 查看器 8321、Exp Console 8322、Inbox 8324、Inbox HMR 8325 有各自入口；HMR 显式代理 API 与图片至 8324。 | [使用入口](/Users/lanzhijiang/Development/bl-gallery/README.md)、[Inbox 配置](/Users/lanzhijiang/Development/bl-gallery/ai-classify/inbox/web/vite.config.ts:5)。这些端口是配置／默认值，不是本次运行观察。 |
| B3 | Exp Console 拒绝 POST；Inbox 启动只扫描并创建 Worker，模型请求必须由明确操作触发。Observer 也有控制 API，因此不能把所有“查看器”都假定为只读。 | [Console](/Users/lanzhijiang/Development/bl-gallery/ai-classify/exp-console/server.py:101)、[Inbox 初始化](/Users/lanzhijiang/Development/bl-gallery/ai-classify/inbox/server.py:22)、[Observer 控制](/Users/lanzhijiang/Development/bl-gallery/ai-classify/observer/server.py:344)。SVC 的观察／打开服务应与领域操作分开。 |
| B4 | Inbox 用数据目录内的文件锁避免重复实例。SIGTERM／SIGINT 后标记 stopping、暂停 Worker、停止 HTTP 接收，并等待执行器中的在途工作结束，最后关闭数据库。 | [进程入口](/Users/lanzhijiang/Development/bl-gallery/ai-classify/inbox/server.py:160)、[Worker 暂停](/Users/lanzhijiang/Development/bl-gallery/ai-classify/inbox/worker.py:154)。停止可能需要等待，不能用短超时加强杀等同于成功。 |
| B5 | 部署要求先排空在途分类并备份，不终止付费请求；仅恢复用户原先明确请求且条件未变的内容，不自动重试失败或启动新分类。 | [局部规则](/Users/lanzhijiang/Development/bl-gallery/ai-classify/inbox/AGENTS.md)、[部署说明](/Users/lanzhijiang/Development/bl-gallery/ai-classify/inbox/README.md:90)。资源重启不能顺势重放业务任务。 |
| B6 | SQLite、封面、截图与 inbox 是项目本地持久数据，Git 不包含它们；根 clean 只清理 Node 依赖与构建输出。静态导出、模型分类是有限作业，有自己的效果与费用。 | [根约束](/Users/lanzhijiang/Development/bl-gallery/AGENTS.md)、[使用说明](/Users/lanzhijiang/Development/bl-gallery/README.md)、[scripts](/Users/lanzhijiang/Development/bl-gallery/package.json)。数据路径可以作为保护与关联事实，不意味着需要为每个文件建立可操作资源对象。 |

## 对产品判断的影响

B1 与 B2 支持按显式资源和访问入口组织管理：同仓不等于同生命周期，开发与日常使用的服务也不能仅凭目录推断隔离范围。

B3 与 B5 支持把启动资源与执行其内部任务明确分开。SVC Dev 无需理解分类策略、图组或用户整理目标；它需要遵守已有服务的生命周期合同。

B4 让“等待安全结束”成为真实控制特性；在途工作属于服务内部事实，资源管理器最多消费其公开的忙碌／等待状态，不接管业务队列。

B6 支持将停止运行、清理构建物和删除数据作为不同效果。不能因为都由脚本执行就合并为通用 cleanup。

## 残余

未确认各入口当前运行情况、使用频次、停止等待时长，也未验证默认端口冲突。没有为这些项目创建 SVC 声明。有限分类作业继续由原工具拥有；是否在资源界面提供跳转入口，尚未形成产品承诺。
