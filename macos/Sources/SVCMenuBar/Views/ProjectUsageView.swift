import SwiftUI

struct ProjectUsageView: View {
    let project: String
    let activity: ActivityStore
    @State private var expanded = false

    var body: some View {
        let observed = activity.snapshot?.projects?.first { $0.projectPath == project }
        if let observed, observed.usage != nil || !observed.issues.isEmpty {
            DisclosureGroup(isExpanded: $expanded) {
                VStack(alignment: .leading, spacing: 8) {
                    if let usage = observed.usage { ProcessUsageDetails(usage: usage) }
                    Text("\(observed.executionCount) 次执行 · \(observed.resourceCount) 个资源运行")
                        .foregroundStyle(.secondary)
                    Text("仅统计 SVC 已观测的本机进程")
                        .foregroundStyle(.secondary)
                        .help("不涵盖未接入的外部程序、容器内部或远端工作；进程内存之和不等于可释放的物理内存。")
                    if !observed.issues.isEmpty {
                        DiagnosticView(title: "部分用量不可用", message: observed.issues.joined(separator: "\n"), semanticID: "usage/\(project)")
                    }
                }.padding(.top, 6).frame(maxWidth: .infinity, alignment: .leading)
            } label: {
                HStack {
                    Text("用量").foregroundStyle(.secondary)
                    Spacer(minLength: 8)
                    if let usage = observed.usage { ProcessUsageSummary(usage: usage) }
                    if !observed.issues.isEmpty {
                        Image(systemName: "exclamationmark.circle").foregroundStyle(.orange)
                            .accessibilityLabel("部分项目用量不可用")
                    }
                }
            }.font(.caption).accessibilityIdentifier("usage/\(project)/details")
        }
    }
}
