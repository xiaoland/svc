import AppKit
import SwiftUI

struct ExecutionListView: View {
    let store: AppStore
    var projectPaths: Set<String>? = nil
    @State private var showHistory = false
    @State private var showSources = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            let executions = scopedExecutions
            let active = executions.filter(\.currentlyObserved)
            let recent = executions.filter { !$0.currentlyObserved }
            HStack {
                Text("当前执行").font(.system(size: 12, weight: .semibold))
                if !active.isEmpty { Text("\(active.count)").foregroundStyle(.secondary) }
                Spacer()
                Menu {
                    Button("复制 Agent 接入说明") { copyAgentInstructions() }
                } label: { Image(systemName: "ellipsis") }
                    .menuStyle(.borderlessButton).menuIndicator(.hidden).fixedSize()
                    .help("执行列表操作").accessibilityLabel("执行列表操作")
            }
            if let sources = store.activity.snapshot?.integrations, !sources.isEmpty {
                DisclosureGroup(isExpanded: $showSources.immediateDisclosure) {
                    ForEach(Array(sources.enumerated()), id: \.offset) { _, source in
                        VStack(alignment: .leading, spacing: 4) {
                            HStack { Text(source.name); Spacer(); Text(source.stateLabel).foregroundStyle(.secondary) }
                            if source.state != "connected" { Text(source.message).foregroundStyle(.secondary).textSelection(.enabled) }
                        }.padding(.vertical, 4)
                    }
                } label: {
                    HStack {
                        Text("原生来源")
                        Spacer()
                        Text("\(sources.filter { $0.state == "connected" }.count)/\(sources.count) 已连接")
                            .foregroundStyle(.secondary)
                    }
                }.font(.caption)
                    .transaction { $0.animation = nil; $0.disablesAnimations = true }
            }
            if active.isEmpty {
                Text(store.activity.snapshot == nil ? "尚未取得执行清单" : "暂无当前执行")
                    .font(.caption).foregroundStyle(.secondary).padding(.vertical, 16)
                    .frame(maxWidth: .infinity)
            }
            let groups = Dictionary(grouping: active, by: { $0.projectPath ?? "" })
            ForEach(groups.keys.sorted(), id: \.self) { project in
                if projectPaths?.count != 1 {
                    Text(project.isEmpty ? "未归属项目" : URL(fileURLWithPath: project).lastPathComponent)
                        .font(.headline).help(project).accessibilityAddTraits(.isHeader)
                }
                ForEach(groups[project] ?? []) { executionRow($0) }
            }
            if !recent.isEmpty {
                DisclosureGroup("最近记录 · \(recent.count)", isExpanded: $showHistory.immediateDisclosure) {
                    VStack(spacing: 10) {
                        ForEach(recent) { executionRow($0) }
                    }.padding(.top, 8)
                }.font(.caption).foregroundStyle(.secondary)
                    .transaction { transaction in
                        transaction.animation = nil
                        transaction.disablesAnimations = true
                    }
            }
            if let issues = store.activity.snapshot?.issues, !issues.isEmpty {
                DiagnosticView(title: "部分观察不可用", message: issues.joined(separator: "\n"), semanticID: "activity/records")
            }
            if let notice = store.activity.notice {
                HStack(alignment: .top) {
                    Text(notice).font(.caption).textSelection(.enabled)
                    Spacer()
                    Button { store.activity.dismissNotice() } label: { Image(systemName: "xmark") }
                        .buttonStyle(.borderless).help("关闭执行提示").accessibilityLabel("关闭执行提示")
                }
            }
        }.padding(12)
    }

    @ViewBuilder private func executionRow(_ item: ExecutionItem) -> some View {
        switch item {
        case .svc(let execution): ExecutionRow(execution: execution, store: store)
        case .harness(let execution): HarnessExecutionRow(execution: execution, store: store)
        }
    }

    private var scopedExecutions: [ExecutionItem] {
        let snapshot = store.activity.snapshot
        let all = (snapshot?.executions ?? []).map { ExecutionItem.svc($0) }
            + (snapshot?.externalExecutions ?? []).map { ExecutionItem.harness($0) }
        guard let projectPaths else { return all }
        return all.filter { execution in
            execution.projectPath.map { projectPaths.contains($0) } ?? false
        }
    }

    private func copyAgentInstructions() {
        let cli = "'" + (store.configuration.resolvedExecutable ?? "svc").replacingOccurrences(of: "'", with: "'\\''") + "'"
        let text = """
        在启动重任务前，使用 \(cli) dev monitor --json 查询当前机器压力和执行。
        压力偏高时将重任务串行执行、降低工具并发；运行期间继续观察。
        已接入的 Pi 后台任务、Codex 原生终端及 Claude 后台会话可以沿用原管理器；先看 integrations 确认连接及控制范围。
        Claude 停止作用于整个后台会话，交互会话只读；Codex 需要连接拥有终端的同一个共享实例。
        未接入的临时构建、验证或脚本也可通过以下入口运行，无需修改项目配置：
        \(cli) dev exec --source agent --label '执行名称' --project '/项目路径' --cwd '/执行目录' --json -- 命令 参数
        --project 明确归属项目；省略时寻找执行目录最近的 svc.json 祖先，找不到则未归属。
        项目用量仅统计可验证的本机执行进程；页面读入不等于 swap，系统 swap 与压缩指标在机器概览。
        此入口无终端输入，按 argv 执行，日志路径和 execution ID 由 SVC 返回。
        人可在 SVC App 的执行页终止这次执行。结果包含 stopped_by；被人终止后不得自动重试。
        终止范围是本次受管进程组，离开该组的进程和远端工作不在范围内。
        """
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
    }
}
