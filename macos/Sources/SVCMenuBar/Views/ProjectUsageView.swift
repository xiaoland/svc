import SwiftUI

struct ProjectUsageView: View {
    let project: String
    let activity: ActivityStore
    var title: String? = nil
    @State private var expanded = false

    var body: some View {
        let observed = activity.snapshot?.projects?.first { $0.projectPath == project }
        if let observed, observed.usage != nil || !observed.issues.isEmpty {
            DisclosureGroup(isExpanded: $expanded.immediateDisclosure) {
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
                    if let title {
                        Text(title).lineLimit(1).help(project)
                        Spacer(minLength: 8)
                    }
                    if let usage = observed.usage {
                        ProcessUsageSummary(usage: usage)
                    } else {
                        Text("用量不可用").foregroundStyle(.secondary)
                    }
                    if !observed.issues.isEmpty {
                        Image(systemName: "exclamationmark.circle").foregroundStyle(.orange)
                            .accessibilityLabel("部分项目用量不可用")
                    }
                }.frame(maxWidth: .infinity, alignment: .leading)
                    .help("已观测的项目用量，展开查看磁盘活动和进程详情")
            }.font(.caption).accessibilityIdentifier("usage/\(project)/details")
                .transaction { transaction in
                    transaction.animation = nil
                    transaction.disablesAnimations = true
                }
        }
    }
}
