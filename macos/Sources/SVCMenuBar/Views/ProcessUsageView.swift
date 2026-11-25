import SwiftUI

struct ProcessUsageView: View {
    let usage: ExecutionUsage

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            ProcessUsageSummary(usage: usage)
            ProcessUsageDetails(usage: usage)
        }
    }
}

struct ProcessUsageSummary: View {
    let usage: ExecutionUsage

    var body: some View {
        HStack(spacing: 18) {
            Text("CPU \(usage.cpuPercent, specifier: "%.0f")%")
                .help("进程 CPU 以一个核心为 100%，不等于整机 CPU 百分比。")
            if let memory = usage.memoryFootprintBytes {
                Text("内存 \(activityBytes(memory))")
                    .help("macOS 为进程计入的 footprint，包含压缩内存；进程之和不等于可释放的物理内存。")
            } else {
                Text("RSS \(activityBytes(usage.rssBytes))")
                    .help("未取得 footprint；RSS 之和可能重复共享页，不包含全部压缩内存。")
            }
            if usage.complete == false {
                Image(systemName: "exclamationmark.circle").foregroundStyle(.orange)
                    .accessibilityLabel("用量统计不完整")
                    .help((usage.issues ?? ["部分进程指标不可用"]).joined(separator: "\n"))
            }
        }.font(.caption).monospacedDigit()
    }
}

struct ProcessUsageDetails: View {
    let usage: ExecutionUsage

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text("\(usage.processCount) 个进程")
            HStack(spacing: 18) {
                Text("磁盘读 \(activityRate(usage.diskReadBytesPerSecond))")
                Text("写 \(activityRate(usage.diskWriteBytesPerSecond))")
            }.help("当前可验证进程的磁盘 I/O，不能代表项目全部资源，也不能据此判断磁盘已饱和。")
            Text("页面读入 \(activityPageRate(usage.pageinsPerSecond))")
                .help("包含文件页，不能解释为项目 swap 换入。")
            ForEach(usage.issues ?? [], id: \.self) { Text($0).foregroundStyle(.orange).textSelection(.enabled) }
        }.font(.caption).monospacedDigit().foregroundStyle(.secondary)
    }
}

func activityRate(_ value: Double?) -> String {
    value.map { $0 == 0 ? "0 B/s" : "\(activityBytes(Int64($0)))/s" } ?? "不可用"
}

func activityPageRate(_ value: Double?) -> String {
    value.map { "\($0.formatted(.number.precision(.fractionLength(0)))) 页/s" } ?? "不可用"
}
