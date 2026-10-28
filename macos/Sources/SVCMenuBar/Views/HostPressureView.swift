import SwiftUI

struct HostPressureView: View {
    let activity: ActivityStore
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let snapshot = activity.snapshot {
                let pressure = snapshot.pressure
                DisclosureGroup(isExpanded: $expanded) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("CPU \(pressure.cpuPercent, specifier: "%.0f")% · 内存压力\(pressure.memoryLabel)")
                        Text("可用内存 \(activityBytes(pressure.memoryAvailableBytes)) · 压缩 \(pressure.compressedBytes.map(activityBytes) ?? "不可用")")
                        Text("磁盘读 \(activityRate(pressure.diskReadBytesPerSecond)) · 写 \(activityRate(pressure.diskWriteBytesPerSecond))")
                            .help("整机磁盘吞吐量，不代表饱和度或所选项目的用量。")
                        Text("Swap 已用 \(pressure.swapUsedBytes.map(activityBytes) ?? "不可用")")
                        Text("Swap 换入 \(activityPageRate(pressure.swapinsPerSecond)) · 换出 \(activityPageRate(pressure.swapoutsPerSecond))")
                        Text("页面读入 \(activityPageRate(pressure.pageinsPerSecond)) · 写出 \(activityPageRate(pressure.pageoutsPerSecond))")
                            .help("页面读入包含文件页，不能当作 swap 换入。")
                        Text("压缩 \(activityPageRate(pressure.compressionsPerSecond)) · 解压 \(activityPageRate(pressure.decompressionsPerSecond))")
                        if let time = activity.checkedAt {
                            Text("更新于 \(time.formatted(date: .omitted, time: .standard)) · 采样 \(pressure.sampleWindowMs) ms")
                                .foregroundStyle(.secondary)
                        }
                        Text("\(pressure.logicalCpus) 个逻辑核心 · 页面 \(pressure.pageSizeBytes.map { activityBytes(Int64($0)) } ?? "不可用")")
                            .foregroundStyle(.secondary)
                        Text(pressure.recommendation).textSelection(.enabled)
                        ForEach(pressure.issues, id: \.self) { Text($0).foregroundStyle(.orange).textSelection(.enabled) }
                    }.monospacedDigit().padding(.top, 6)
                        .frame(maxWidth: .infinity, alignment: .leading)
                } label: {
                    TimelineView(.periodic(from: .now, by: 5)) { context in
                        let stale = activity.error != nil || activity.checkedAt.map { context.date.timeIntervalSince($0) > 15 } ?? true
                        HStack(spacing: 6) {
                            Circle().fill(stale ? Color.secondary : tint(pressure.level))
                                .frame(width: 7, height: 7).accessibilityHidden(true)
                            Text("本机")
                            Text(stale ? "采样已过期" : pressure.levelLabel)
                                .foregroundStyle(.secondary)
                            if !pressure.issues.isEmpty {
                                Image(systemName: "exclamationmark.circle").foregroundStyle(.orange)
                                    .accessibilityLabel("部分机器指标不可用")
                            }
                        }.frame(maxWidth: .infinity, alignment: .leading)
                    }
                }.accessibilityIdentifier("host/details")
                .transaction { transaction in
                    transaction.animation = nil
                    transaction.disablesAnimations = true
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
        }.font(.caption).padding(.horizontal, 16).padding(.vertical, 10)
    }

    private func tint(_ level: String) -> Color {
        switch level {
        case "normal": .green
        case "elevated": .orange
        case "critical": .red
        default: .secondary
        }
    }
}
