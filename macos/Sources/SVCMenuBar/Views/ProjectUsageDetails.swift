import SwiftUI

struct ProjectUsageDetails: View {
    let project: String
    let observed: ProjectActivity?
    let pressure: ProjectUsagePressure
    let checkedAt: Date?
    let error: String?
    let close: () -> Void
    @State private var showingPolicy = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text(URL(fileURLWithPath: project).lastPathComponent).font(.headline).lineLimit(2).help(project)
                Spacer()
                Button(action: close) { Image(systemName: "xmark") }
                    .buttonStyle(.borderless).help("关闭项目资源占用").accessibilityLabel("关闭项目资源占用")
            }.padding(16)
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text(pressure.label(hasUsage: observed?.usage != nil)).font(.subheadline.weight(.semibold))
                    if let usage = observed?.usage {
                        Grid(alignment: .leading, horizontalSpacing: 16, verticalSpacing: 10) {
                            metric("CPU", "\(usage.cpuPercent.formatted(.number.precision(.fractionLength(0))))%")
                                .help("一个逻辑核心占满为 100%；项目之和可以超过 100%。")
                            metric(usage.memoryFootprintBytes == nil ? "RSS" : "内存", activityBytes(usage.memoryFootprintBytes ?? usage.rssBytes))
                                .help("优先使用 macOS footprint，包含压缩内存；RSS 可能重复共享页，不代替 footprint 判断颜色。")
                            metric("占本机 CPU 容量", share(pressure.cpuShare))
                            metric("占本机内存容量", share(pressure.memoryShare))
                            metric("进程", "\(usage.processCount)")
                            metric("磁盘读取", activityRate(usage.diskReadBytesPerSecond))
                            metric("磁盘写入", activityRate(usage.diskWriteBytesPerSecond))
                            metric("页面读入", activityPageRate(usage.pageinsPerSecond))
                                .help("包含文件页，不能解释为项目 Swap 换入。")
                        }
                        if usage.complete == false {
                            Text("用量统计不完整，颜色仅反映已观测部分。").foregroundStyle(.secondary)
                        }
                        if pressure.memoryShare == nil {
                            Text("未取得可比较的 footprint 或本机内存容量，内存未参与颜色判断。").foregroundStyle(.secondary)
                        }
                        if pressure.cpuShare == nil {
                            Text("本机 CPU 容量不可用，CPU 未参与颜色判断。").foregroundStyle(.secondary)
                        }
                    } else {
                        Text(error != nil ? "项目用量暂不可用。" : (checkedAt == nil ? "尚未取得项目用量快照。" : "暂无已观测的本机进程用量。"))
                            .foregroundStyle(.secondary)
                    }
                    if let observed {
                        Text("\(observed.executionCount) 次执行 · \(observed.resourceCount) 个资源运行").foregroundStyle(.secondary)
                    }
                    let issues = Array(Set((observed?.issues ?? []) + (observed?.usage?.issues ?? []) + (error.map { [$0] } ?? []))).sorted()
                    ForEach(issues, id: \.self) { Text($0).foregroundStyle(.secondary).textSelection(.enabled) }
                    Text("仅统计 SVC 已观测的本机进程，不涵盖未接入、容器内部或远端工作；进程内存之和不等于可释放的物理内存。")
                        .font(.caption).foregroundStyle(.secondary)
                    DisclosureGroup(isExpanded: $showingPolicy.immediateDisclosure) {
                        Text("黄色：CPU 占本机容量至少 50%，或 footprint 占内存容量至少 20%。红色：分别达到 80% 或 40%。这是已观测占用的启发式提示，不是系统内存压力或饱和证明；磁盘与换页不参与着色。数据过期或无可比较指标时使用中性颜色；不完整数据按已观测部分提示，未达阈值也不保证完整或正常。")
                            .font(.caption).foregroundStyle(.secondary).padding(.top, 8)
                    } label: { Text("颜色说明") }
                        .font(.caption)
                        .transaction { $0.animation = nil; $0.disablesAnimations = true }
                    if let checkedAt {
                        Text("更新于 \(checkedAt.formatted(date: .omitted, time: .standard))").font(.caption).foregroundStyle(.secondary)
                    }
                }.padding(16).frame(maxWidth: .infinity, alignment: .leading)
            }.frame(maxHeight: 440)
        }.font(.callout).frame(width: 340).fixedSize(horizontal: false, vertical: true)
    }

    private func share(_ fraction: Double?) -> String {
        fraction.map { $0.formatted(.percent.precision(.fractionLength(1))) } ?? "不可用"
    }

    private func metric(_ title: String, _ value: String) -> some View {
        GridRow(alignment: .firstTextBaseline) {
            Text(title).foregroundStyle(.secondary)
            Text(value).monospacedDigit().textSelection(.enabled).frame(maxWidth: .infinity, alignment: .trailing)
        }
    }
}
