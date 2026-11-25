import Foundation

// An App presentation hint based on observed capacity share, not OS pressure or causality.
struct ProjectUsagePressure {
    enum Level: String {
        case neutral, elevated, critical

        var label: String {
            switch self {
            case .neutral: "已观测占用未达提示阈值"
            case .elevated: "已观测占用偏高"
            case .critical: "已观测占用很高"
            }
        }
    }

    let level: Level
    let cpuShare: Double?
    let memoryShare: Double?
    let stale: Bool

    init(usage: ExecutionUsage?, host: HostPressure?, stale: Bool) {
        self.stale = stale
        if let usage, let host, host.logicalCpus > 0, usage.cpuPercent.isFinite, usage.cpuPercent >= 0 {
            cpuShare = usage.cpuPercent / (Double(host.logicalCpus) * 100)
        } else { cpuShare = nil }
        // RSS can double-count shared pages; it is displayed but never substituted here.
        if let footprint = usage?.memoryFootprintBytes, footprint >= 0,
           let total = host?.memoryTotalBytes, total > 0 {
            memoryShare = Double(footprint) / Double(total)
        } else { memoryShare = nil }
        if stale {
            level = .neutral
        } else if cpuShare.map({ $0 >= 0.8 }) == true || memoryShare.map({ $0 >= 0.4 }) == true {
            level = .critical
        } else if cpuShare.map({ $0 >= 0.5 }) == true || memoryShare.map({ $0 >= 0.2 }) == true {
            level = .elevated
        } else { level = .neutral }
    }

    func label(hasUsage: Bool) -> String {
        if stale { return "采样已过期" }
        if !hasUsage { return "暂无可观测用量" }
        if cpuShare == nil && memoryShare == nil { return "容量占比不可用" }
        return level.label
    }
}
