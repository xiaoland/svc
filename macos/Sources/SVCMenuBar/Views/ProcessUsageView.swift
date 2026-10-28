import SwiftUI

struct ProcessUsageView: View {
    let usage: ExecutionUsage

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 18) {
                Text("CPU \(usage.cpuPercent, specifier: "%.0f")%")
                    .help("进程 CPU 以一个核心为 100%，不等于顶部整机 CPU 百分比。")
                if let memory = usage.memoryFootprintBytes {
                    Text("内存 \(activityBytes(memory))")
                        .help("macOS 为已观测进程计入的内存 footprint，包含压缩内存；进程之和不等于可释放的物理内存。")
                } else {
                    Text("RSS \(activityBytes(usage.rssBytes))")
                        .help("未取得 footprint；RSS 之和可能重复共享内存，不包含全部压缩内存。")
                }
                Text("\(usage.processCount) 个进程").foregroundStyle(.secondary)
                if usage.complete == false {
                    Image(systemName: "exclamationmark.circle").foregroundStyle(.orange)
                        .accessibilityLabel("用量统计不完整")
                        .help((usage.issues ?? ["部分进程指标不可用"]).joined(separator: "\n"))
                }
            }
            HStack(spacing: 18) {
                Text("磁盘读 \(activityRate(usage.diskReadBytesPerSecond))")
                Text("写 \(activityRate(usage.diskWriteBytesPerSecond))")
            }.foregroundStyle(.secondary)
                .help("当前可验证进程的磁盘 I/O 采样，不能代表项目全部资源，也不能据此判断磁盘已饱和。")
        }.font(.caption).monospacedDigit()
    }
}

func activityRate(_ value: Double?) -> String {
    value.map { "\(activityBytes(Int64($0)))/s" } ?? "不可用"
}

func activityPageRate(_ value: Double?) -> String {
    value.map { "\($0.formatted(.number.precision(.fractionLength(0)))) 页/s" } ?? "不可用"
}
