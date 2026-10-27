# Velune：远端观察资源、连接与隔离应用实例

2026-10-27 读取本地工作树，HEAD `05e0c2fa68f15c8a4184de9f7e86b367c6b33262`，107 项已跟踪变更。未运行 Velune、读取真实 Harness 会话或凭据，也未连接遥测服务或设备。

## 已观察事实

| 编号 | 资源与现有控制 | 证据与边界 |
| --- | --- | --- |
| V1 | 当前 Mac App 嵌入 Rust 核心，不依赖常驻 Host；本地配对 CLI socket 随 App 生命周期存在。开发说明中后面的 Host／IPC 段落被标为历史原型。 | [开发说明](/Users/lanzhijiang/Development/Velune/docs/development.md:11)、[原生核心接入](/Users/lanzhijiang/Development/Velune/app/mac/Transport.swift:60)。不能从旧目录或旧文档推导需要管理一个当前 Host daemon。 |
| V2 | 开发遥测使用远端 LGTM，提供 Grafana 与 OTLP/gRPC 两个 loopback 入口，经 SSH 访问；Compose stop 保留卷，停止 SSH 隧道不停止远端服务。 | [部署记录](/Users/lanzhijiang/Development/Velune/tasks/otlp-observability/deployment.md:32)、[Compose 配置](/Users/lanzhijiang/Development/Velune/tasks/otlp-observability/deployment/compose.yaml)。部署记录是既有观察，不是本次在线检查。 |
| V3 | `dev-telemetry.py launch` 会检查／建立 SSH 隧道，生成独立 profile、业务 home、OS home 和 run manifest，再启动指定应用。接收端不可用时继续启动应用并报告未接入。 | [ready 与 launch](/Users/lanzhijiang/Development/Velune/scripts/dev-telemetry.py:55)。遥测是显式可选依赖，不能把所有关联资源未就绪都当成应用禁止启动。 |
| V4 | 同一脚本的 Android 路径使用 ADB install/reverse 和应用私有 profile；Simulator 路径安装并重新启动指定 App。设备必须已启动且专用于合成验收。 | [移动入口](/Users/lanzhijiang/Development/Velune/scripts/dev-telemetry.py:108)、[开发说明](/Users/lanzhijiang/Development/Velune/docs/development.md:481)。设备、设备上的 App、转发连接分别有身份和生命周期。 |
| V5 | status 校验 run ID 与 45 秒新鲜度；状态不可读返回 unavailable。query 则先调用 ready，可能建立隧道，再查询信号。 | [状态与查询实现](/Users/lanzhijiang/Development/Velune/scripts/dev-telemetry.py:137)。不能仅凭名称 query 就假设动作没有控制副作用。 |
| V6 | iPad 安装需要明确源码目录、设备和签名团队；验证安装回执对应设备和 bundle ID。Mac 安装说明强调覆盖安装保留数据，不自动打开 iPad App。 | [安装实现](/Users/lanzhijiang/Development/Velune/app/mac/IPadInstaller.swift:106)、[操作说明](/Users/lanzhijiang/Development/Velune/app/mac/README.md:61)。构建成功、安装成功和运行就绪各自需要证据。 |
| V7 | 仓库明确不引入 SVC CLI、运行时或额外工程。 | [仓库约束](/Users/lanzhijiang/Development/Velune/AGENTS.md:17)。本轮只读；未来若纳入 SVC Dev，不能默认改造项目或要求它先采用 SVC 工程结构。 |

## 对产品判断的影响

V2 与 V4 支持将连接本身识别为资源：隧道与 ADB 转发有独立的建立、检查和断开行为，不能把断开连接解释为服务已停止。

V3 与 V5 支持明确显示观察来源、新鲜度、实例身份及动作副作用。隔离 App 实例是资源事实，不需要引入开发任务；run ID 在这里属于可观测性实例关联，不等于 Agent 任务身份。

V6 支持安装型资源与运行型资源分开表达。V7 让“外部登记既有脚本／仅观察资源”成为需要讨论的接入方向，但没有据此选定技术方案或给 Velune 添加任何配置。

Agent 会话管理、模型路由、设备配对批准和遥测内容分析继续属于 Velune。SVC Dev 可以管理被明确登记的开发资源及访问入口，不能顺势接管这些产品内部行为。

## 文档时效与残余

部署记录开头仍写“产品代码尚未接入”，但当前 `docs/development.md`、`ClientTelemetry` 与 Transport 已有接入入口。本调查只采用部署记录中由当前脚本／Compose 交叉支持的服务与连接事实，不把旧整体阶段判断当作现状。

未检查远端服务或设备当前在线状态，未实测 SDK 上报、查询权限、连接恢复与实际使用频次。没有重新运行历史验收，也没有复制私有查询 token、地址配置或运行数据。
