import SwiftUI

struct ProjectUsageView: View {
    let project: String
    let activity: ActivityStore

    var body: some View {
        let observed = activity.snapshot?.projects?.first { $0.projectPath == project }
        VStack(alignment: .leading, spacing: 7) {
            HStack {
                Text("已观测用量").fontWeight(.medium)
                    .help("仅统计由 SVC 启动、身份仍可验证的本机进程；容器内部、远端和未接入的外部进程不在此范围。")
                Spacer()
                if let observed {
                    Text("\(observed.executionCount) 次执行 · \(observed.resourceCount) 个资源运行")
                        .foregroundStyle(.secondary)
                }
            }.font(.caption)
            if let usage = observed?.usage {
                ProcessUsageView(usage: usage)
            } else {
                Text(activity.snapshot == nil ? "尚未采样" : "暂无已观测进程")
                    .font(.caption).foregroundStyle(.secondary)
            }
            if let issues = observed?.issues, !issues.isEmpty {
                DiagnosticView(title: "部分用量不可用", message: issues.joined(separator: "\n"), semanticID: "usage/\(project)")
            }
        }
    }
}
