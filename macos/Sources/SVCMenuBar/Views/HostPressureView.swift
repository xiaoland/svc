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
                            Text(time, style: .time).font(.caption2).foregroundStyle(.secondary)
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
                        Text("CPU").foregroundStyle(.secondary)
                        Text("\(pressure.cpuPercent, specifier: "%.0f")%").monospacedDigit().fontWeight(.medium)
                    }.help("整机 CPU 使用率；\(pressure.logicalCpus) 个逻辑核心，采样 \(pressure.sampleWindowMs) 毫秒")
                    HStack(alignment: .firstTextBaseline, spacing: 5) {
                        Text("内存").foregroundStyle(.secondary)
                        Text(pressure.memoryLabel).fontWeight(.medium)
                        Text("可用 \(activityBytes(pressure.memoryAvailableBytes))").foregroundStyle(.secondary)
                    }.help("系统内存压力与可用内存分别显示，不根据已用比例推断压力。")
                }
                .accessibilityElement(children: .ignore)
                .accessibilityAddTraits(.isStaticText)
                .accessibilityLabel("上次采样的本机用量")
                .accessibilityValue("整机 CPU \(pressure.cpuPercent.formatted(.number.precision(.fractionLength(0)))) 百分比；内存压力\(pressure.memoryLabel)，可用 \(activityBytes(pressure.memoryAvailableBytes))")
                HStack(spacing: 18) {
                    Text("磁盘读 \(activityRate(pressure.diskReadBytesPerSecond))")
                    Text("写 \(activityRate(pressure.diskWriteBytesPerSecond))")
                }.monospacedDigit()
                    .help("整机磁盘活动；吞吐量不等于磁盘饱和度，也不能直接归因到某个项目。")
                ViewThatFits(in: .horizontal) {
                    HStack(spacing: 18) { swapUsage(pressure); swapActivity(pressure) }
                    VStack(alignment: .leading, spacing: 5) { swapUsage(pressure); swapActivity(pressure) }
                }.monospacedDigit()
                if expanded {
                    Text("压缩内存 \(pressure.compressedBytes.map(activityBytes) ?? "不可用")")
                    Text("页面读入 \(activityPageRate(pressure.pageinsPerSecond)) · 写出 \(activityPageRate(pressure.pageoutsPerSecond))")
                        .help("页面读入包含文件页，不能当作 swap 换入。")
                    Text("压缩 \(activityPageRate(pressure.compressionsPerSecond)) · 解压 \(activityPageRate(pressure.decompressionsPerSecond))")
                    Text("采样 \(pressure.sampleWindowMs) ms · 页面 \(pressure.pageSizeBytes.map { activityBytes(Int64($0)) } ?? "不可用")")
                        .font(.caption2).foregroundStyle(.secondary)
                    Text(pressure.recommendation).font(.caption).textSelection(.enabled)
                    ForEach(pressure.issues, id: \.self) { Text($0).font(.caption).foregroundStyle(.orange) }
                }
            } else if activity.error == nil {
                HStack {
                    ProgressView().controlSize(.small)
                    Text("正在读取本机压力…").foregroundStyle(.secondary)
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

    private func swapUsage(_ pressure: HostPressure) -> some View {
        Text("Swap 已用 \(pressure.swapUsedBytes.map(activityBytes) ?? "不可用")")
            .help("当前磁盘上的 swap 占用；不能单凭已用量判断当前是否发生换页或卡顿。")
    }

    private func swapActivity(_ pressure: HostPressure) -> some View {
        Text("换入 \(activityPageRate(pressure.swapinsPerSecond)) · 换出 \(activityPageRate(pressure.swapoutsPerSecond))")
            .help("真实系统 swap 页面计数的速率，不是页面读入／写出的别名，也不能分摊到某个项目。")
    }
}
