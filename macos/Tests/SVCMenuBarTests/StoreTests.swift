import Foundation
import Testing
@testable import SVCMenuBar

actor Requests {
    private var pending: [(DevCommand, CheckedContinuation<Data, any Error>)] = []
    func call(_ command: DevCommand) async throws -> Data {
        try await withCheckedThrowingContinuation { pending.append((command, $0)) }
    }
    var count: Int { pending.count }
    func resolveFirst(_ data: Data) { pending.removeFirst().1.resume(returning: data) }
    func failFirst() { pending.removeFirst().1.resume(throwing: CLIError(message: "fixture failure")) }
}

@MainActor
func waitUntil(_ condition: () async -> Bool) async throws {
    for _ in 0..<2000 {
        if await condition() { return }
        try await Task.sleep(for: .milliseconds(5))
    }
    throw CLIError(message: "test condition timed out")
}

@MainActor
func preferences(_ projects: [String]) -> UserDefaults {
    TestPreferences(projects: projects)
}

private final class TestPreferences: UserDefaults {
    private let domain: String
    init(projects: [String]) {
        domain = "svc-macos-tests-\(UUID())"
        super.init(suiteName: domain)!
        set(projects, forKey: "projects")
    }
    deinit { removePersistentDomain(forName: domain) }
}

@Test @MainActor func staleRefreshCannotReplaceNewConfigurationOrRemovedProject() async throws {
    let requests = Requests()
    let store = AppStore(preferences: preferences(["/tmp/project"])) { _, command, _, _ in
        try await requests.call(command)
    }
    let old = Task { await store.refresh("/tmp/project") }
    try await waitUntil { await requests.count == 1 }
    store.setConfiguration(.init(executable: "/new/svc", searchPath: "/bin"))
    try await waitUntil { await requests.count == 2 }
    await requests.resolveFirst(statusData(healthy: true))
    await old.value
    #expect(store.projects[0].snapshot == nil)
    await requests.failFirst()
    try await waitUntil { store.projects[0].error != nil }
    #expect(store.readyCount == 0)
    let next = Task { await store.refresh("/tmp/project") }
    try await waitUntil { await requests.count == 1 }
    store.removeProject("/tmp/project")
    await requests.resolveFirst(statusData(healthy: true))
    await next.value
    #expect(store.projects.isEmpty)
}

@Test @MainActor func sharedOperationsInvalidateOlderReadsAndQuitCanBeCancelled() async throws {
    let requests = Requests()
    let store = AppStore(preferences: preferences(["/tmp/project"])) { _, command, _, _ in
        try await requests.call(command)
    }
    let target = try #require(CLIResponse.decode(DevStatus.self, data: statusData(), command: .status).targets?.first)
    let old = Task { await store.refresh("/tmp/project") }
    try await waitUntil { await requests.count == 1 }
    store.perform(.ensure, target: target, project: "/tmp/project")
    store.perform(.ensure, target: target, project: "/tmp/project")
    try await waitUntil { await requests.count == 2 }
    #expect(store.operations.count == 1)
    await requests.resolveFirst(statusData())
    await old.value
    #expect(store.projects[0].snapshot == nil)
    var quitReply: Bool?
    store.waitToQuit { quitReply = $0 }
    store.cancelQuit()
    #expect(quitReply == false)
    try await waitUntil { await requests.count == 2 }
    store.waitToQuit { quitReply = $0 }
    await requests.resolveFirst(Data("{\"schema_version\":2,\"command\":\"dev ensure\",\"status\":\"started\",\"ready\":true}".utf8))
    try await waitUntil { store.operations.isEmpty }
    #expect(quitReply == true)
    #expect(store.receipts["shared"]?.message == "服务已就绪")
    await requests.resolveFirst(statusData())
}

@Test @MainActor func failedOperationReleasesQuitWait() async throws {
    let requests = Requests()
    let store = AppStore(preferences: preferences(["/tmp/project"])) { _, command, _, _ in
        try await requests.call(command)
    }
    let target = try #require(CLIResponse.decode(DevStatus.self, data: statusData(), command: .status).targets?.first)
    store.perform(.stop, target: target, project: "/tmp/project")
    try await waitUntil { await requests.count == 1 }
    var quitReply = false
    store.waitToQuit { quitReply = $0 }
    await requests.failFirst()
    try await waitUntil { store.operations.isEmpty }
    #expect(quitReply)
    #expect(store.receipts["shared"]?.message == "fixture failure")
}

@Test @MainActor func operationReceiptRemainsReachableAfterRefreshFails() async throws {
    let requests = Requests()
    let store = AppStore(preferences: preferences(["/tmp/project"])) { _, command, _, _ in
        try await requests.call(command)
    }
    let target = try #require(CLIResponse.decode(DevStatus.self, data: statusData(), command: .status).targets?.first)
    store.perform(.ensure, target: target, project: "/tmp/project")
    try await waitUntil { await requests.count == 1 }
    await requests.resolveFirst(Data("""
    {"schema_version":2,"command":"dev ensure","status":"started","ready":true,
    "attempt":{"execution_id":"receipt","logs":{"merged":{"path":"/tmp/output.log"}}}}
    """.utf8))
    try await waitUntil { await requests.count == 1 }
    await requests.failFirst()
    try await waitUntil { store.projects[0].error != nil }
    #expect(store.readyCount == 0)
    let receipt = try #require(store.unavailableReceipts(for: store.projects[0]).first)
    #expect(receipt.target == "web")
    #expect(receipt.message == "服务已就绪")
    #expect(receipt.logPath == "/tmp/output.log")
}
