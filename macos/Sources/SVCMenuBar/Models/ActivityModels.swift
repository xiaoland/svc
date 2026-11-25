import Foundation

struct ActivitySnapshot: Decodable, Sendable {
    let pressure: HostPressure
    let executions: [ExecutionActivity]
    let issues: [String]
    let projects: [ProjectActivity]?
    let resources: [ResourceActivity]?
    let externalExecutions: [HarnessExecution]?
    let integrations: [HarnessIntegration]?
}

struct HostPressure: Decodable, Sendable {
    let sampledAt: String
    let sampleWindowMs: Int
    let cpuPercent: Double
    let logicalCpus: Int
    let memoryTotalBytes: Int64
    let memoryAvailableBytes: Int64
    let memoryPressure: String
    let diskReadBytesPerSecond: Double?
    let diskWriteBytesPerSecond: Double?
    let level: String
    let recommendation: String
    let issues: [String]
    let swapUsedBytes: Int64?
    let swapTotalBytes: Int64?
    let compressedBytes: Int64?
    let pageSizeBytes: Int?
    let pageinsPerSecond: Double?
    let pageoutsPerSecond: Double?
    let swapinsPerSecond: Double?
    let swapoutsPerSecond: Double?
    let compressionsPerSecond: Double?
    let decompressionsPerSecond: Double?

    var levelLabel: String {
        switch level {
        case "normal": "CPU／内存正常"
        case "elevated": "压力偏高"
        case "critical": "压力很高"
        default: "压力未知"
        }
    }
    var memoryLabel: String {
        switch memoryPressure {
        case "normal": "正常"
        case "warning": "偏高"
        case "critical": "很高"
        default: "未知"
        }
    }
}

struct ExecutionUsage: Decodable, Sendable {
    let cpuPercent: Double
    let rssBytes: Int64
    let processCount: Int
    let scope: String
    let memoryFootprintBytes: Int64?
    let diskReadBytesPerSecond: Double?
    let diskWriteBytesPerSecond: Double?
    let pageinsPerSecond: Double?
    let complete: Bool?
    let issues: [String]?
}

struct ProjectActivity: Decodable, Sendable {
    let projectPath: String?
    let executionCount: Int
    let resourceCount: Int
    let usage: ExecutionUsage?
    let issues: [String]
}

struct ResourceActivity: Decodable, Sendable {
    let executionId: String
    let projectPath: String?
    let entryId: String
    let resource: String
    let usage: ExecutionUsage?
}

struct ExecutionActivity: Decodable, Identifiable, Sendable {
    let executionId: String
    let domain: String
    let operation: String
    let label: String
    let source: String
    let cwd: String
    let argv: [String]
    let state: String
    let startedAt: String
    let finishedAt: String?
    let exitCode: Int?
    let canTerminate: Bool
    let terminationRequested: String?
    let groupState: String?
    let usage: ExecutionUsage?
    let logs: [String]
    let issues: [String]
    let projectPath: String?
    let projectSource: String?
    var id: String { executionId }
    var active: Bool { ["starting", "running"].contains(state) }
    var currentlyObserved: Bool { active || (state == "owner-lost" && usage != nil) }
    var projectName: String { projectPath.map { URL(fileURLWithPath: $0).lastPathComponent } ?? "未归属项目" }
    var stateLabel: String {
        if state == "owner-lost" { return "执行者已丢失 · 结果未知" }
        if active {
            if terminationRequested == "kill" { return "强制终止中" }
            if terminationRequested != nil { return "终止中" }
            if groupState == "descendants-running" { return "子进程仍在运行" }
            if groupState == "unknown" { return "进程组状态未知" }
        }
        switch state {
        case "starting": return "正在启动"
        case "running": return "运行中"
        case "interrupted": return terminationRequested == nil ? "已中断" : "已终止 · 进程组已结束"
        case "exited": return exitCode == 0 ? "已完成" : "退出 \(exitCode ?? -1)"
        case "released": return "已交由资源控制者管理"
        case "start-failed": return "启动失败"
        case "capture-failed": return "日志采集失败"
        default: return state
        }
    }
}

struct TerminationReceipt: Decodable, Sendable {
    let executionId: String
    let status: String
    let mode: String
    let message: String
}

func activityBytes(_ value: Int64) -> String {
    ByteCountFormatter.string(fromByteCount: value, countStyle: .memory)
}
