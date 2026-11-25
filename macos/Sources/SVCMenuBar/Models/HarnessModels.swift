import Foundation

struct HarnessExecution: Decodable, Identifiable, Sendable {
    let executionId: String
    let provider: String
    let nativeId: String
    let instanceId: String
    let label: String
    let command: String
    let cwd: String
    let state: String
    let scope: String
    let startedAt: String
    let canTerminate: Bool
    let canReadLogs: Bool
    let stopDescription: String
    let processId: Int?
    let usage: ExecutionUsage?
    let projectPath: String?
    let issues: [String]
    var id: String { executionId }
    var currentlyObserved: Bool { ["running", "idle"].contains(state) || (state == "unknown" && usage != nil) }
    var sourceLabel: String {
        let name = ["pi": "Pi", "codex": "Codex", "claude": "Claude Code"][provider] ?? provider
        return "\(name) · \(scope == "session" ? "会话" : (scope == "terminal" ? "终端" : "执行"))"
    }
    var stateLabel: String {
        switch state {
        case "running": "运行中"
        case "idle": "空闲"
        case "completed": "已完成"
        case "stopped": "已停止"
        case "failed": "失败"
        default: "状态未知"
        }
    }
}

struct HarnessIntegration: Decodable, Sendable {
    let provider: String
    let state: String
    let message: String
    let instances: Int
    var name: String { ["pi": "Pi", "codex": "Codex", "claude": "Claude Code", "configuration": "来源配置"][provider] ?? provider }
    var stateLabel: String {
        switch state {
        case "connected": "已连接"
        case "partial": "部分可用"
        case "waiting": "等待接入"
        default: "未连接"
        }
    }
}

struct ExecutionLogsResponse: Decodable, Identifiable, Sendable {
    let executionId: String
    let text: String
    let truncated: Bool
    var id: String { executionId }
}

struct IntegrationSetupResponse: Decodable, Sendable {
    let provider: String
    let state: String
    let message: String
}

enum ExecutionItem: Identifiable {
    case svc(ExecutionActivity)
    case harness(HarnessExecution)
    var id: String {
        switch self { case .svc(let item): item.id; case .harness(let item): item.id }
    }
    var projectPath: String? {
        switch self { case .svc(let item): item.projectPath; case .harness(let item): item.projectPath }
    }
    var currentlyObserved: Bool {
        switch self { case .svc(let item): item.currentlyObserved; case .harness(let item): item.currentlyObserved }
    }
}
