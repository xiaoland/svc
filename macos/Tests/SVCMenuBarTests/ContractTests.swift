import Foundation
import Testing
@testable import SVCMenuBar

func statusData(healthy: Bool = false, stop: String = "exec", version: Int = 3) -> Data {
    Data("""
    {"schema_version":\(version),"command":"dev status","status":"action-required","targets":[{
    "target":"web","capability":{"capability_id":"shared","scope":"host"},
    "probe":{"healthy":\(healthy),"responded":\(healthy),"reason":"fixture","endpoint_identity":"http://localhost"},
    "access":["http://localhost"],"provision":{"kind":"exec"},"stop":{"kind":"\(stop)"}}]}
    """.utf8)
}

@Test func readinessIsNotProcessLivenessAndStopRequiresDeclaration() throws {
    let snapshot = try CLIResponse.decode(DevStatus.self, data: statusData(stop: "absent"), command: .status)
    let target = try #require(snapshot.targets?.first)
    #expect(target.health == .notReady)
    #expect(target.canStart)
    #expect(!target.canStop)
    #expect(target.scopeLabel == "主机共享")
    let unhealthy = statusData().replacingUTF8("\"responded\":false", with: "\"responded\":true")
    let blocked = try CLIResponse.decode(DevStatus.self, data: unhealthy, command: .status).targets![0]
    #expect(blocked.health == .unhealthy)
    #expect(!blocked.canStart)
    let manual = try CLIResponse.decode(DevStatus.self, data: statusData(stop: "manual"), command: .status).targets![0]
    #expect(!manual.canStop)
}

@Test func incompatibleOrIncompleteContractsFailClearly() throws {
    #expect(throws: CLIError.self) {
        try CLIResponse.decode(DevStatus.self, data: statusData(version: 2), command: .status)
    }
    let missingStop = statusData().replacingUTF8(",\"stop\":{\"kind\":\"exec\"}", with: "")
    #expect(throws: CLIError.self) {
        try CLIResponse.decode(DevStatus.self, data: missingStop, command: .status)
    }
    #expect(throws: CLIError.self) {
        try CLIResponse.decode(DevStatus.self, data: statusData().replacingUTF8("dev status", with: "dev stop"), command: .status)
    }
    #expect(throws: CLIError.self) {
        try CLIResponse.decode(DevStatus.self, data: Data("not json".utf8), command: .status)
    }
}

@Test func targetConfigurationErrorsDoNotBecomeHealthy() throws {
    let data = Data("""
    {"schema_version":3,"command":"dev status","status":"action-required", "targets":[
    {"target":"bad","error":{"message":"invalid probe"}}]}
    """.utf8)
    let target = try #require(CLIResponse.decode(DevStatus.self, data: data, command: .status).targets?.first)
    #expect(target.health == .unknown)
    #expect(!target.canStart && !target.canStop)
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
    let snapshot = try CLIResponse.decode(DevStatus.self, data: data, command: .status)
    #expect(snapshot.targets?.first?.health == .notReady)
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
