import AppKit
import SwiftUI

struct ExecutionListView: View {
    let store: AppStore
    var projectPaths: Set<String>? = nil
    @State private var showHistory = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            let executions = scopedExecutions
            let active = executions.filter(\.currentlyObserved)
            let recent = executions.filter { !$0.currentlyObserved }
            HStack {
                Text("当前执行").font(.system(size: 12, weight: .semibold))
                Text("\(active.count)").foregroundStyle(.secondary)
                Spacer()
                Menu {
                    Button("复制 Agent 接入说明") { copyAgentInstructions() }
                } label: { Image(systemName: "ellipsis") }
                    .menuStyle(.borderlessButton).menuIndicator(.hidden).fixedSize()
                    .accessibilityLabel("执行列表操作")
            }
            if active.isEmpty {
                Text(store.activity.snapshot == nil ? "尚未取得执行清单" : "暂无运行中的受管执行")
                    .font(.caption).foregroundStyle(.secondary).padding(.vertical, 16)
                    .frame(maxWidth: .infinity)
            }
            let groups = Dictionary(grouping: active, by: { $0.projectPath ?? "" })
            ForEach(groups.keys.sorted(), id: \.self) { project in
                if projectPaths?.count != 1 {
                    Text(project.isEmpty ? "未归属项目" : URL(fileURLWithPath: project).lastPathComponent)
                        .font(.headline).help(project).accessibilityAddTraits(.isHeader)
                }
                ForEach(groups[project] ?? []) { ExecutionRow(execution: $0, store: store) }
            }
            if !recent.isEmpty {
                DisclosureGroup("最近记录 · \(recent.count)", isExpanded: $showHistory) {
                    VStack(spacing: 10) {
                        ForEach(recent) { ExecutionRow(execution: $0, store: store) }
                    }.padding(.top, 8)
                }.font(.caption).foregroundStyle(.secondary)
            }
            if let issues = store.activity.snapshot?.issues, !issues.isEmpty {
                DiagnosticView(title: "部分观察不可用", message: issues.joined(separator: "\n"), semanticID: "activity/records")
            }
            if let notice = store.activity.notice {
                HStack(alignment: .top) {
                    Text(notice).font(.caption).textSelection(.enabled)
                    Spacer()
                    Button { store.activity.dismissNotice() } label: { Image(systemName: "xmark") }
                        .buttonStyle(.borderless).accessibilityLabel("关闭执行提示")
                }
            }
        }.padding(12)
    }

    private var scopedExecutions: [ExecutionActivity] {
        let all = store.activity.snapshot?.executions ?? []
        guard let projectPaths else { return all }
        return all.filter { execution in
            execution.projectPath.map { projectPaths.contains($0) } ?? false
        }
    }

    private func copyAgentInstructions() {
        let cli = "'" + store.configuration.executable.replacingOccurrences(of: "'", with: "'\\''") + "'"
        let text = """
        在启动重任务前，使用 \(cli) dev monitor --json 查询当前机器压力和执行。
        压力偏高时将重任务串行执行、降低工具并发；运行期间继续观察。
        临时构建、验证或脚本通过以下入口运行，无需修改项目配置：
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
