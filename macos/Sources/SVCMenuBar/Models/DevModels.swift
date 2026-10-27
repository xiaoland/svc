import Foundation

struct CLIConfiguration: Equatable, Sendable {
    var executable: String
    var searchPath: String
}

enum DevCommand: String, Sendable {
    case list, status, act, reconcile
    var schemaVersion: Int { self == .status ? 4 : 1 }
    var title: String {
        switch self {
        case .list: "资源"
        case .status: "刷新"
        case .act: "操作"
        case .reconcile: "确认未知结果"
        }
    }
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
        guard header.schemaVersion == command.schemaVersion, header.command == "dev \(command.rawValue)" else {
            throw CLIError(message: "CLI 协议不兼容。请使用配套 CLI，或在设置中更新所选路径。")
        }
        do { return try decoder.decode(type, from: data) }
        catch { throw CLIError(message: "CLI 结果不完整：\(error.localizedDescription)") }
    }
}

struct DevCatalog: Decodable, Sendable {
    let status: String
    let resources: [DevResource]
}

struct DevResource: Decodable, Identifiable, Sendable {
    let resource: String
    let label: String
    let entryId: String
    let source: String
    let declarationDigest: String
    let coordination: Coordination?
    let controller: String?
    let access: [String]
    let relations: [String]
    let actions: [ResourceAction]
    var observations: [ResourceObservation]
    let facets: [ObservationDescription]
    let execution: ResourceExecution?
    let error: Failure?
    var id: String { entryId }
    var needsReconciliation: Bool { execution?.phase == "owner-lost" && execution?.acknowledged == false }
    var scopeLabel: String {
        switch coordination?.scope {
        case "repository": "仓库共享"
        case "host": "主机共享"
        case "worktree": "工作树"
        default: "协调范围未知"
        }
    }
}

struct Coordination: Decodable, Sendable {
    let coordinationId: String
    let scope: String
    let scopeId: String
    let ownerRepo: String
    let ownerResource: String
}

struct ResourceAction: Decodable, Identifiable, Sendable {
    let key: String
    let kind: String
    let intent: String
    let traits: [String]
    let effectScope: String
    let dataEffect: String
    let completion: String?
    let interruption: String?
    let convergent: Bool
    let steps: [String]
    var id: String { key }
    var traitLabels: String {
        traits.map { ["observe": "观察访问", "runtime": "运行", "provision": "供应销毁", "connection": "连接", "installation": "安装更新"][$0] ?? $0 }.joined(separator: " · ")
    }
    var effectLabel: String {
        switch dataEffect {
        case "unchanged": "保留持久数据"
        case "modify": "可能修改数据"
        case "delete": "可能删除数据"
        default: "数据影响未知"
        }
    }
}

struct ObservationDescription: Decodable, Identifiable, Sendable {
    let key: String
    let label: String
    let automatic: Bool
    let purpose: String
    let provider: String
    var id: String { key }
}

struct ResourceObservation: Decodable, Identifiable, Sendable {
    let key: String
    let label: String
    let state: String
    let source: String
    let checkedAt: String
    let dataAt: String?
    let expiresAt: String?
    let stale: Bool
    let value: JSONValue?
    let message: String?
    let instance: String?
    let error: Failure?
    var id: String { key }
    var isStale: Bool {
        if stale { return true }
        guard let expiresAt else { return false }
        let format = ISO8601DateFormatter()
        format.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return format.date(from: expiresAt).map { $0 < Date() } ?? true
    }
    var stateLabel: String {
        if isStale { return "已过期" }
        switch state {
        case "satisfied": return "满足"
        case "unsatisfied": return "未满足"
        default: return "未知"
        }
    }
    var symbol: String {
        if isStale { return "clock.badge.exclamationmark" }
        switch state {
        case "satisfied": return "checkmark.circle"
        case "unsatisfied": return "circle"
        default: return "questionmark.circle"
        }
    }
}

indirect enum JSONValue: Decodable, Sendable {
    case string(String), number(Double), bool(Bool), array([JSONValue]), object([String: JSONValue]), null
    init(from decoder: Decoder) throws {
        let value = try decoder.singleValueContainer()
        if value.decodeNil() { self = .null }
        else if let text = try? value.decode(String.self) { self = .string(text) }
        else if let flag = try? value.decode(Bool.self) { self = .bool(flag) }
        else if let number = try? value.decode(Double.self) { self = .number(number) }
        else if let array = try? value.decode([JSONValue].self) { self = .array(array) }
        else { self = .object(try value.decode([String: JSONValue].self)) }
    }
    var text: String {
        switch self {
        case .string(let value): value
        case .number(let value): value.formatted()
        case .bool(let value): value ? "true" : "false"
        case .null: ""
        case .array(let values): values.map(\.text).joined(separator: ", ")
        case .object(let values): values.keys.sorted().map { "\($0): \(values[$0]!.text)" }.joined(separator: ", ")
        }
    }
}

struct Failure: Decodable, Sendable { let message: String }
struct CLIFailureResult: Decodable { let schemaVersion: Int; let error: Failure }
struct ResourceExecution: Decodable, Sendable {
    let executionId: String
    let state: String
    let phase: String
    let acknowledged: Bool
    let action: String?
    let entryId: String?
    let exitCode: Int?
    let logPath: String
}
struct OperationReference: Decodable, Sendable { let id: String; let url: String? }
struct DevResult: Decodable, Sendable {
    let resource: String
    let entryId: String
    let action: String
    let status: String
    let message: String
    let execution: ResourceExecution?
    let observations: [ResourceObservation]
    let operation: OperationReference?
    let steps: [String]
    let requestedSignal: String?
}
struct OperationReceipt: Sendable {
    let projectPath: String
    let entryId: String
    let resource: String
    let action: String
    let message: String
    let date: Date
    let logPath: String?
    let result: DevResult?
}
