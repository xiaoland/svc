import AppKit
import SwiftUI
import Foundation
import Testing
@testable import SVCMenuBar

@Test(.enabled(if: ProcessInfo.processInfo.environment["SVC_TEST_CLI"] != nil, "设置 SVC_TEST_CLI 以运行真实生命周期测试"))
func realCLIServiceSurvivesClientsAndStopsThroughDeclaredCleanup() async throws {
    guard let executable = ProcessInfo.processInfo.environment["SVC_TEST_CLI"] else { return }
    let directory = FileManager.default.temporaryDirectory.appendingPathComponent("svc lifecycle \(UUID())")
    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    defer { try? FileManager.default.removeItem(at: directory) }
    let fixture = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
        .appendingPathComponent("Fixtures/http_service.py")
    try FileManager.default.copyItem(at: fixture, to: directory.appendingPathComponent("http_service.py"))
    let python = ProcessInfo.processInfo.environment["SVC_TEST_PYTHON"] ?? "/usr/bin/python3"
    let config: [String: Any] = ["schema_version": 4, "dev": ["targets": ["web": [
        "scope": "repository", "readiness_timeout": 10, "poll_interval": 0.1,
        "probe": ["kind": "exec", "argv": [python, "http_service.py", "probe"], "timeout": 2],
        "provision": ["kind": "exec", "mode": "run", "argv": [python, "http_service.py", "serve"]],
        "stop": ["kind": "exec", "argv": [python, "http_service.py", "stop"], "timeout": 5]
    ]]]]
    try JSONSerialization.data(withJSONObject: config).write(to: directory.appendingPathComponent("svc.json"))
    let configuration = CLIConfiguration(executable: executable, searchPath: "/usr/bin:/bin")
    let client = CLIClient(configuration: configuration)
    let initial = try await client.request(.status, repo: directory.path)
    #expect(try CLIResponse.decode(DevStatus.self, data: initial, command: .status).targets?.first?.health == .notReady)
    let started = try await client.request(.ensure, repo: directory.path, target: "web")
    do {
        let result = try CLIResponse.decode(DevResult.self, data: started, command: .ensure)
        #expect(result.ready == true)
        #expect(result.attempt?.logs.merged.path != nil)
        // A new client has no process handle or in-memory knowledge of the provisioner.
        let secondClient = CLIClient(configuration: configuration)
        let observed = try await secondClient.request(.status, repo: directory.path)
        #expect(try CLIResponse.decode(DevStatus.self, data: observed, command: .status).targets?.first?.health == .ready)
        let reused = try await secondClient.request(.ensure, repo: directory.path, target: "web")
        #expect(try CLIResponse.decode(DevResult.self, data: reused, command: .ensure).status == "reused")
    } catch {
        _ = try? await client.request(.stop, repo: directory.path, target: "web")
        throw error
    }
    let stopped = try await client.request(.stop, repo: directory.path, target: "web")
    #expect(try CLIResponse.decode(DevResult.self, data: stopped, command: .stop).status == "stopped")
    let final = try await client.request(.status, repo: directory.path)
    #expect(try CLIResponse.decode(DevStatus.self, data: final, command: .status).targets?.first?.health == .notReady)
}


@Test(.enabled(if: ProcessInfo.processInfo.environment["SVC_TEST_CLI"] != nil, "设置 SVC_TEST_CLI 以验证原生按钮控制真实服务"))
@MainActor func nativeButtonsControlRealServerWithoutForegroundChanges() async throws {
    let executable = try #require(ProcessInfo.processInfo.environment["SVC_TEST_CLI"])
    let foreground = NSWorkspace.shared.frontmostApplication?.processIdentifier
    NSApplication.shared.setActivationPolicy(.prohibited)
    let directory = FileManager.default.temporaryDirectory.appendingPathComponent("svc native \(UUID())")
    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    defer { try? FileManager.default.removeItem(at: directory) }
    let fixture = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
        .appendingPathComponent("Fixtures/http_service.py")
    try FileManager.default.copyItem(at: fixture, to: directory.appendingPathComponent("http_service.py"))
    let python = ProcessInfo.processInfo.environment["SVC_TEST_PYTHON"] ?? "/usr/bin/python3"
    let config: [String: Any] = ["schema_version": 4, "dev": ["targets": ["web": [
        "scope": "repository", "readiness_timeout": 10, "poll_interval": 0.1,
        "probe": ["kind": "exec", "argv": [python, "http_service.py", "probe"], "timeout": 2],
        "provision": ["kind": "exec", "mode": "run", "argv": [python, "http_service.py", "serve"]],
        "stop": ["kind": "exec", "argv": [python, "http_service.py", "stop"], "timeout": 5]
    ]]]]
    try JSONSerialization.data(withJSONObject: config).write(to: directory.appendingPathComponent("svc.json"))
    let defaults = preferences([directory.path])
    defaults.set(executable, forKey: "cliPath")
    defaults.set("/usr/bin:/bin", forKey: "searchPath")
    let store = AppStore(preferences: defaults)
    await store.refreshAll()
    let target = try #require(store.projects.first?.snapshot?.targets?.first)
    #expect(target.health == .notReady)
    let id = try #require(target.capability?.capabilityId)
    let client = CLIClient(configuration: store.configuration)
    do {
        try await pressPrimaryNativeAction(target: target, project: directory.path, store: store)
        try await waitUntil { store.projects.first?.snapshot?.targets?.first?.health == .ready }
        let log = try #require(store.receipts[id]?.logPath)
        #expect(FileManager.default.fileExists(atPath: log))
        #expect(try String(contentsOfFile: log, encoding: .utf8).contains("SVC fixture ready"))
        #expect(AppDelegate(store: store).applicationShouldTerminate(NSApplication.shared) == .terminateNow)
        let reopened = AppStore(preferences: defaults)
        await reopened.refreshAll()
        let running = try #require(reopened.projects.first?.snapshot?.targets?.first)
        #expect(running.health == .ready)
        try await pressPrimaryNativeAction(target: running, project: directory.path, store: reopened)
        try await waitUntil { reopened.receipts[id]?.message == "停止成功" }
        let final = try await client.request(.status, repo: directory.path)
        #expect(try CLIResponse.decode(DevStatus.self, data: final, command: .status).targets?.first?.health == .notReady)
        #expect(NSWorkspace.shared.frontmostApplication?.processIdentifier == foreground)
    } catch {
        _ = try? await client.request(.stop, repo: directory.path, target: "web")
        throw error
    }
}

@MainActor private func pressPrimaryNativeAction(target: DevTarget, project: String, store: AppStore) async throws {
    let host = NSHostingView(rootView: TargetRow(target: target, project: project, store: store))
    let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 420, height: 150),
                          styleMask: [.borderless], backing: .buffered, defer: false)
    window.isReleasedWhenClosed = false
    window.contentView = host
    window.alphaValue = 0
    window.ignoresMouseEvents = true
    window.orderBack(nil)
    defer { window.close() }
    host.layoutSubtreeIfNeeded()
    try await Task.sleep(for: .milliseconds(100))
    func subviews(_ view: NSView) -> [NSView] { [view] + view.subviews.flatMap(subviews) }
    let buttons = subviews(host).compactMap { $0 as? NSButton }
    let primary = try #require(buttons.min { $0.frame.minX < $1.frame.minX })
    primary.performClick(nil)
    #expect(!window.isKeyWindow && window.alphaValue == 0)
}
