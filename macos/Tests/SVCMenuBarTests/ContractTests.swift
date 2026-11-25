import Foundation
import Testing
@testable import SVCMenuBar

func statusData(healthy: Bool = false, stop: String = "exec", version: Int = 4) -> Data {
    var actions: [[String: Any]] = [
        ["key": "ensure", "kind": "exec", "intent": "启动", "traits": ["runtime"], "effect_scope": "当前实例", "data_effect": "unchanged", "completion": "ready", "interruption": "terminate", "convergent": true, "steps": []]
    ]
    if stop != "absent" {
        actions.append(["key": "stop", "kind": stop, "intent": "停止", "traits": ["runtime"], "effect_scope": "当前实例", "data_effect": "unchanged", "completion": "exit", "interruption": "wait", "convergent": false, "steps": stop == "manual" ? ["停止外部控制者"] : []])
    }
    return try! JSONSerialization.data(withJSONObject: [
        "schema_version": version, "command": "dev status", "status": "ok", "resources": [[
            "resource": "web", "label": "Web 服务", "entry_id": "entry-web", "source": "/tmp/svc.json", "declaration_digest": "fixture",
            "coordination": ["coordination_id": "shared", "scope": "host", "scope_id": "host", "owner_repo": "/tmp", "owner_resource": "web"],
            "access": ["http://localhost"], "relations": [], "actions": actions,
            "facets": [["key": "ready", "label": "就绪", "automatic": true, "purpose": "state", "provider": "exec"]],
            "observations": [["key": "ready", "label": "就绪", "state": healthy ? "satisfied" : "unsatisfied", "source": "exec", "checked_at": "2026-10-27T00:00:00.000Z", "stale": false]]
        ]]
    ])
}

func actionData(_ action: String = "ensure") -> Data {
    Data("""
    {"schema_version":1,"command":"dev act","resource":"web","entry_id":"entry-web","action":"\(action)",
    "status":"completed","message":"声明动作已完成。","observations":[],"steps":[],
    "execution":{"execution_id":"receipt","state":"exited","phase":"settled","acknowledged":false,"log_path":"/tmp/output.log"}}
    """.utf8)
}

@Test func readinessIsNotProcessLivenessAndStopRequiresDeclaration() throws {
    let snapshot = try CLIResponse.decode(DevCatalog.self, data: statusData(stop: "absent"), command: .status)
    let resource = try #require(snapshot.resources.first)
    #expect(resource.observations.first?.state == "unsatisfied")
    #expect(resource.actions.contains { $0.key == "ensure" })
    #expect(!resource.actions.contains { $0.key == "stop" })
    #expect(resource.scopeLabel == "主机共享")
    let manual = try CLIResponse.decode(DevCatalog.self, data: statusData(stop: "manual"), command: .status).resources[0]
    #expect(manual.actions.first { $0.key == "stop" }?.kind == "manual")
}

@Test func incompatibleOrIncompleteContractsFailClearly() throws {
    #expect(throws: CLIError.self) {
        try CLIResponse.decode(DevCatalog.self, data: statusData(version: 2), command: .status)
    }
    let missing = statusData().replacingUTF8("entry_id", with: "missing_id")
    #expect(throws: CLIError.self) {
        try CLIResponse.decode(DevCatalog.self, data: missing, command: .status)
    }
    #expect(throws: CLIError.self) {
        try CLIResponse.decode(DevCatalog.self, data: statusData().replacingUTF8("dev status", with: "dev act"), command: .status)
    }
    #expect(throws: CLIError.self) {
        try CLIResponse.decode(DevCatalog.self, data: Data("not json".utf8), command: .status)
    }
}

@Test func targetConfigurationErrorsDoNotBecomeHealthy() throws {
    var payload = try #require(JSONSerialization.jsonObject(with: statusData()) as? [String: Any])
    var resource = try #require((payload["resources"] as? [[String: Any]])?.first)
    resource["coordination"] = NSNull()
    resource["error"] = ["message": "owner unavailable"]
    resource["observations"] = []
    payload["resources"] = [resource]
    let data = try JSONSerialization.data(withJSONObject: payload)
    let value = try #require(CLIResponse.decode(DevCatalog.self, data: data, command: .status).resources.first)
    #expect(value.observations.isEmpty)
    #expect(value.coordination == nil && value.error != nil)
}

@Test func processClientHandlesSpacesNonzeroJSONAndLargeStderr() async throws {
    let root = FileManager.default.temporaryDirectory.appendingPathComponent("svc test \(UUID())")
    try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
    defer { try? FileManager.default.removeItem(at: root) }
    let executable = root.appendingPathComponent("fake svc")
    let encoded = String(decoding: statusData(), as: UTF8.self)
    let source = """
    #!/usr/bin/python3
    import json, os, sys
    assert sys.argv[1:4] == ['dev', 'status', '--repo']
    assert os.path.realpath(sys.argv[4]) == os.getcwd()
    assert sys.argv[5:] == ['--json']
    assert os.environ['PATH'] == '/usr/bin:/bin'
    sys.stderr.write('x' * 1000000)
    print(\(String(reflecting: encoded)))
    sys.exit(3)
    """
    try source.write(to: executable, atomically: true, encoding: .utf8)
    try FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: executable.path)
    let client = CLIClient(configuration: .init(executable: executable.path, searchPath: "/usr/bin:/bin"))
    let data = try await client.request(.status, repo: root.path)
    let snapshot = try CLIResponse.decode(DevCatalog.self, data: data, command: .status)
    #expect(snapshot.resources.first?.observations.first?.state == "unsatisfied")
}

@Test func missingCLIIsAnActionableError() async {
    let client = CLIClient(configuration: .init(executable: "/no-such-svc", searchPath: "/usr/bin"))
    await #expect(throws: CLIError.self) { try await client.request(.status, repo: "/tmp") }
}

extension Data {
    func replacingUTF8(_ before: String, with after: String) -> Data {
        Data(String(decoding: self, as: UTF8.self).replacingOccurrences(of: before, with: after).utf8)
    }
}
