import Foundation

struct ActivitySnapshot: Decodable, Sendable {
    let pressure: HostPressure
    let executions: [ExecutionActivity]
    let issues: [String]
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
    var id: String { executionId }
    var active: Bool { ["starting", "running"].contains(state) }
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
