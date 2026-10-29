import SwiftUI

struct HostPressureView: View {
    let activity: ActivityStore
    @State private var showingDetails = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let snapshot = activity.snapshot {
                let pressure = snapshot.pressure
                Button { showingDetails = true } label: {
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
                            Spacer(minLength: 8)
                            Image(systemName: "info.circle").foregroundStyle(.secondary).accessibilityHidden(true)
                        }.contentShape(Rectangle())
                    }
                }.buttonStyle(.plain)
                    .help("查看本机压力、内存与磁盘活动")
                    .accessibilityIdentifier("host/details")
                    .popover(isPresented: $showingDetails, arrowEdge: .bottom) {
                        HostPressureDetails(pressure: pressure, checkedAt: activity.checkedAt,
                                            stale: activity.error != nil || activity.checkedAt.map { Date().timeIntervalSince($0) > 15 } ?? true,
                                            close: { showingDetails = false })
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

struct HostPressureDetails: View {
    let pressure: HostPressure
    let checkedAt: Date?
    let stale: Bool
    let close: () -> Void
    @State private var showingDiagnostics = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("本机压力").font(.headline)
                Spacer()
                Button(action: close) { Image(systemName: "xmark") }
                    .buttonStyle(.borderless).help("关闭本机压力")
                    .accessibilityLabel("关闭本机压力")
            }.padding(16)
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(stale ? "采样已过期" : pressure.levelLabel).font(.subheadline.weight(.semibold))
                        if !stale { Text(pressure.recommendation).foregroundStyle(.secondary) }
                    }
                    Grid(alignment: .leading, horizontalSpacing: 20, verticalSpacing: 10) {
                        metric("CPU", "\(pressure.cpuPercent.formatted(.number.precision(.fractionLength(0))))%")
                        metric("内存压力", pressure.memoryLabel)
                        metric("可用内存", activityBytes(pressure.memoryAvailableBytes))
                        metric("压缩内存", pressure.compressedBytes.map(activityBytes) ?? "不可用")
                        metric("Swap 已用", pressure.swapUsedBytes.map(activityBytes) ?? "不可用")
                    }
                    Divider()
                    Grid(alignment: .leading, horizontalSpacing: 20, verticalSpacing: 10) {
                        metric("磁盘读取", activityRate(pressure.diskReadBytesPerSecond))
                        metric("磁盘写入", activityRate(pressure.diskWriteBytesPerSecond))
                        metric("Swap 换入", activityPageRate(pressure.swapinsPerSecond))
                        metric("Swap 换出", activityPageRate(pressure.swapoutsPerSecond))
                    }.help("整机磁盘活动，不代表磁盘饱和度或所选项目的用量。")
                    DisclosureGroup(isExpanded: $showingDiagnostics.immediateDisclosure) {
                        VStack(alignment: .leading, spacing: 10) {
                            Grid(alignment: .leading, horizontalSpacing: 20, verticalSpacing: 10) {
                                metric("页面读入", activityPageRate(pressure.pageinsPerSecond))
                                metric("页面写出", activityPageRate(pressure.pageoutsPerSecond))
                                metric("压缩", activityPageRate(pressure.compressionsPerSecond))
                                metric("解压", activityPageRate(pressure.decompressionsPerSecond))
                                metric("逻辑核心", "\(pressure.logicalCpus)")
                                metric("页面大小", pressure.pageSizeBytes.map { activityBytes(Int64($0)) } ?? "不可用")
                                metric("采样时长", "\(pressure.sampleWindowMs) ms")
                            }
                            Text("页面读入包含文件页，不能当作 Swap 换入。")
                                .foregroundStyle(.secondary)
                        }.padding(.top, 10)
                    } label: { Text("采样与底层指标") }
                        .transaction { $0.animation = nil; $0.disablesAnimations = true }
                    ForEach(pressure.issues, id: \.self) { Text($0).foregroundStyle(.orange).textSelection(.enabled) }
                    if let checkedAt {
                        Text("更新于 \(checkedAt.formatted(date: .omitted, time: .standard))")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }.padding(16).frame(maxWidth: .infinity, alignment: .leading)
            }.frame(maxHeight: 460)
        }.font(.callout).frame(width: 340).fixedSize(horizontal: false, vertical: true)
    }

    private func metric(_ label: String, _ value: String) -> some View {
        GridRow(alignment: .firstTextBaseline) {
            Text(label).foregroundStyle(.secondary)
            Text(value).monospacedDigit().textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .trailing)
        }
    }
}
