import Foundation

struct CLIConfiguration: Equatable, Sendable {
    var executable: String
    var searchPath: String
}

enum DevCommand: String, Sendable {
    case status, ensure, stop
    var title: String { self == .ensure ? "启动" : self == .stop ? "停止" : "刷新" }
    var schemaVersion: Int { self == .status ? 3 : 2 }
}

struct CLIError: LocalizedError, Sendable {
    let message: String
    var errorDescription: String? { message }
}

struct CLIHeader: Decodable {
    let schemaVersion: Int
    let command: String
}

enum CLIResponse {
    static func decode<T: Decodable>(_ type: T.Type, data: Data, command: DevCommand) throws -> T {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        guard let header = try? decoder.decode(CLIHeader.self, from: data) else {
            throw CLIError(message: "CLI 未返回有效的 SVC 结果。请检查设置中的 CLI 路径。")
        }
        guard header.schemaVersion == command.schemaVersion else {
            throw CLIError(message: "CLI 结果版本不兼容（\(header.schemaVersion)）。请更新或重新选择 CLI。")
        }
        guard header.command == "dev \(command.rawValue)" else {
            throw CLIError(message: "CLI 返回了其他命令的结果：\(header.command)。")
        }
        do { return try decoder.decode(type, from: data) }
        catch { throw CLIError(message: "CLI 结果不完整。请更新 CLI。\n\(error.localizedDescription)") }
    }
}

struct DevStatus: Decodable, Sendable {
    let status: String
    let reason: String?
    let targets: [DevTarget]?
}

struct DevTarget: Decodable, Identifiable, Sendable {
    let target: String
    let capability: Capability?
    let probe: Probe?
    let access: [String]?
    let provision: Declaration?
    let stop: Declaration?
    let error: Failure?
    var id: String { target }

    // Error targets have no observation; a successful observation must include stop authority.
    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        target = try values.decode(String.self, forKey: .target)
        error = try values.decodeIfPresent(Failure.self, forKey: .error)
        if error != nil {
            capability = nil; probe = nil; access = nil; provision = nil; stop = nil
        } else {
            capability = try values.decode(Capability.self, forKey: .capability)
            probe = try values.decode(Probe.self, forKey: .probe)
            access = try values.decode([String].self, forKey: .access)
            provision = try values.decode(Declaration.self, forKey: .provision)
            stop = try values.decode(Declaration.self, forKey: .stop)
        }
    }
    private enum CodingKeys: String, CodingKey {
        case target, capability, probe, access, provision, stop, error
    }
    var health: TargetHealth {
        guard error == nil, let probe else { return .unknown }
        if probe.healthy { return .ready }
        return probe.responded ? .unhealthy : .notReady
    }
    var canStart: Bool {
        error == nil && provision?.kind == "exec" && health == .notReady
    }
    var canStop: Bool { error == nil && stop?.kind == "exec" }
    var scopeLabel: String {
        switch capability?.scope {
        case "repository": "仓库共享"
        case "host": "主机共享"
        default: "当前工作树"
        }
    }
}

struct Capability: Decodable, Sendable {
    let capabilityId: String
    let scope: String
}
struct Declaration: Decodable, Sendable { let kind: String }
struct Failure: Decodable, Sendable { let message: String }
struct Probe: Decodable, Sendable {
    let healthy: Bool
    let responded: Bool
    let reason: String
    let endpointIdentity: String
}

enum TargetHealth: String, Sendable {
    case ready = "就绪", notReady = "未就绪", unhealthy = "响应异常", unknown = "状态未知"
    var symbol: String {
        switch self {
        case .ready: "checkmark.circle.fill"
        case .notReady: "circle"
        case .unhealthy: "exclamationmark.circle.fill"
        case .unknown: "questionmark.circle"
        }
    }
}

struct DevResult: Decodable, Sendable {
    let status: String
    let ready: Bool?
    let attempt: Attempt?
    let probeError: Failure?

    func message(for command: DevCommand) -> String {
        switch status {
        case "reused", "started", "joined": return ready == true ? "服务已就绪" : "服务尚未就绪"
        case "stopped": return "停止成功"
        case "manual-action-required": return "需要按项目配置手动操作"
        case "conflict": return "端点被占用或有其他操作进行中"
        case "still-ready": return "停止命令结束，但服务仍然就绪"
        case "stop-unverified": return "无法确认停止结果"
        case "stop-failed": return "停止失败"
        case "readiness-timeout", "activation-timeout": return "等待服务就绪超时"
        case "child-exit": return "启动进程提前退出"
        case "interrupted": return "操作已中断"
        default: return ready == true ? "服务已就绪" : "\(command.title)结果：\(status)"
        }
    }
}
struct Attempt: Decodable, Sendable {
    let executionId: String
    let logs: AttemptLogs
}
struct AttemptLogs: Decodable, Sendable { let merged: LogReference }
struct LogReference: Decodable, Sendable { let path: String }

struct OperationReceipt: Sendable {
    let projectPath: String
    let target: String
    let command: DevCommand
    let message: String
    let date: Date
    let logPath: String?
}
