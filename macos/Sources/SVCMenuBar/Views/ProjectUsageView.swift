import AppKit
import SwiftUI

struct ProjectUsageView: View {
    let project: String
    let activity: ActivityStore
    var title: String? = nil
    @State private var showingDetails = false

    var body: some View {
        TimelineView(.periodic(from: .now, by: 5)) { context in
            let observed = activity.snapshot?.projects?.first { $0.projectPath == project }
            let stale = activity.snapshot != nil && (activity.error != nil || activity.checkedAt.map { context.date.timeIntervalSince($0) > 15 } ?? true)
            let pressure = ProjectUsagePressure(usage: observed?.usage, host: activity.snapshot?.pressure, stale: stale)
            let limited = observed?.usage?.complete == false || !(observed?.issues.isEmpty ?? true)
                || !(observed?.usage?.issues?.isEmpty ?? true)
            let status = pressure.label(hasUsage: observed?.usage != nil) + (limited ? " · 统计不完整" : "")
            HStack(spacing: 6) {
                if let title { Text(title).lineLimit(1).help(project) }
                ResourceActionButton(title: "", semanticID: "usage/\(project)/details", bordered: false,
                    symbol: "info.circle", accessibilityName: "\(projectName) 资源占用：\(status)",
                    tint: tint(pressure.level), accessibilityHelp: "\(status)。查看已观测的 CPU、内存、磁盘活动与统计范围") {
                        showingDetails = true
                    }
                    .frame(width: 22, height: 22)
                    .popover(isPresented: $showingDetails, arrowEdge: .bottom) {
                        ProjectUsageDetails(project: project, observed: observed, pressure: pressure,
                                            checkedAt: activity.checkedAt, error: activity.error,
                                            close: { showingDetails = false })
                    }
            }
        }
    }

    private var projectName: String { URL(fileURLWithPath: project).lastPathComponent }

    private func tint(_ level: ProjectUsagePressure.Level) -> NSColor {
        switch level {
        case .neutral: .secondaryLabelColor
        case .elevated: .systemYellow
        case .critical: .systemRed
        }
    }
}
