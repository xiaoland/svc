import SwiftUI

struct HostPressureView: View {
    let activity: ActivityStore
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            if let snapshot = activity.snapshot {
                let pressure = snapshot.pressure
                TimelineView(.periodic(from: .now, by: 5)) { context in
                    let stale = activity.error != nil || activity.checkedAt.map { context.date.timeIntervalSince($0) > 15 } ?? true
                    HStack(spacing: 6) {
                        Circle().fill(stale ? Color.secondary : tint(pressure.level)).frame(width: 7, height: 7).accessibilityHidden(true)
                        Text("本机").fontWeight(.semibold)
                        Text(stale ? "上次采样 · 已过期" : pressure.levelLabel).fontWeight(.medium)
                        Spacer()
                        if let time = activity.checkedAt {
                            Text(time, style: .time).font(.system(size: 12)).foregroundStyle(.primary)
                        }
                        ResourceActionButton(title: "", semanticID: "host/details", bordered: false,
                            symbol: expanded ? "chevron.up" : "chevron.down",
                            accessibilityName: expanded ? "收起机器详情" : "展开机器详情", expanded: expanded) {
                                expanded.toggle()
                            }.frame(width: 28, height: 28)
                    }
                }
                HStack(alignment: .firstTextBaseline, spacing: 18) {
                    HStack(alignment: .firstTextBaseline, spacing: 5) {
                        Text("CPU").foregroundStyle(.primary)
                        Text("\(pressure.cpuPercent, specifier: "%.0f")%").monospacedDigit().fontWeight(.medium)
                    }.help("整机 CPU 使用率；\(pressure.logicalCpus) 个逻辑核心，采样 \(pressure.sampleWindowMs) 毫秒")
                    HStack(alignment: .firstTextBaseline, spacing: 5) {
                        Text("内存").foregroundStyle(.primary)
                        Text(pressure.memoryLabel).fontWeight(.medium)
                        Text("可用 \(activityBytes(pressure.memoryAvailableBytes))").foregroundStyle(.primary)
                    }.help("系统内存压力与可用内存分别显示，不根据已用比例推断压力。")
                }
                .accessibilityElement(children: .ignore)
                .accessibilityAddTraits(.isStaticText)
                .accessibilityLabel("上次采样的本机用量")
                .accessibilityValue("整机 CPU \(pressure.cpuPercent.formatted(.number.precision(.fractionLength(0)))) 百分比；内存压力\(pressure.memoryLabel)，可用 \(activityBytes(pressure.memoryAvailableBytes))")
                if expanded {
                    HStack {
                        Text("磁盘  读 \(rate(pressure.diskReadBytesPerSecond))  ·  写 \(rate(pressure.diskWriteBytesPerSecond))")
                        Spacer()
                        Text("\(pressure.sampleWindowMs) ms")
                    }.font(.system(size: 12)).foregroundStyle(.primary)
                    Text(pressure.recommendation).font(.system(size: 12)).textSelection(.enabled)
                    ForEach(pressure.issues, id: \.self) { Text($0).font(.system(size: 12)).foregroundStyle(.orange) }
                }
            } else if activity.error == nil {
                HStack {
                    ProgressView().controlSize(.small)
                    Text("正在读取本机压力…").foregroundStyle(.primary)
                }
            }
            if let error = activity.error {
                DiagnosticView(title: "无法更新机器与执行", message: error, semanticID: "activity/error")
            }
        }.font(.system(size: 12)).padding(.horizontal, 16).padding(.vertical, 12)
    }

    private func tint(_ level: String) -> Color {
        switch level {
        case "normal": .green
        case "elevated": .orange
        case "critical": .red
        default: .secondary
        }
    }

    private func rate(_ value: Double?) -> String {
        value.map { "\(activityBytes(Int64($0)))/s" } ?? "未知"
    }
}
