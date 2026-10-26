import AppKit
import Foundation
import SwiftUI
import Testing
@testable import SVCMenuBar

@Test(.enabled(if: ProcessInfo.processInfo.environment["SVC_RENDER_DIR"] != nil, "设置 SVC_RENDER_DIR 生成离屏界面证据"))
@MainActor func offscreenPanelRendersWithoutActivatingApplication() async throws {
    let directory = URL(fileURLWithPath: try #require(ProcessInfo.processInfo.environment["SVC_RENDER_DIR"]))
    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    let foregroundBefore = NSWorkspace.shared.frontmostApplication?.processIdentifier
    let application = NSApplication.shared
    application.setActivationPolicy(.prohibited)
    let defaults = preferences(["/Users/developer/Projects/atlas"])
    let data = try renderData()
    let store = AppStore(preferences: defaults) { _, _, _, _ in data }
    await store.refreshAll()
    for appearance in ["light", "dark"] {
        let host = NSHostingView(rootView:
            MenuPanel(store: store, openSettings: {})
                .background(Color(nsColor: .windowBackgroundColor))
                .environment(\.colorScheme, appearance == "dark" ? .dark : .light)
        )
        host.appearance = NSAppearance(named: appearance == "dark" ? .darkAqua : .aqua)
        host.frame = NSRect(x: 0, y: 0, width: 420, height: 640)
        host.layoutSubtreeIfNeeded()
        host.setFrameSize(host.fittingSize)
        host.layoutSubtreeIfNeeded()
        let bitmap = try #require(host.bitmapImageRepForCachingDisplay(in: host.bounds))
        host.cacheDisplay(in: host.bounds, to: bitmap)
        let png = try #require(bitmap.representation(using: .png, properties: [:]))
        try png.write(to: directory.appendingPathComponent("panel-\(appearance).png"))
        #expect(png.count > 1000)

        #expect(host.window == nil)
    }
    #expect(NSWorkspace.shared.frontmostApplication?.processIdentifier == foregroundBefore)
}

private func renderData() throws -> Data {
    var snapshot = try #require(JSONSerialization.jsonObject(with: statusData(healthy: true)) as? [String: Any])
    let healthy = try #require((snapshot["targets"] as? [[String: Any]])?.first)
    var offline = healthy
    offline["target"] = "worker"
    offline["capability"] = ["capability_id": "worker", "scope": "worktree"]
    offline["probe"] = ["healthy": false, "responded": false, "reason": "unreachable", "endpoint_identity": "tcp://127.0.0.1:3001"]
    var manual = offline
    manual["target"] = "database"
    manual["capability"] = ["capability_id": "database", "scope": "repository"]
    manual["stop"] = ["kind": "absent"]
    manual["provision"] = ["kind": "manual"]
    snapshot["targets"] = [healthy, offline, manual]
    return try JSONSerialization.data(withJSONObject: snapshot)
}

@Test @MainActor func hiddenNativeControlsInvokeActionsWithoutTakingFocus() async throws {
    let foreground = NSWorkspace.shared.frontmostApplication?.processIdentifier
    NSApplication.shared.setActivationPolicy(.prohibited)
    let defaults = preferences(["/tmp/native-control"])
    let store = AppStore(preferences: defaults) { _, command, _, _ in
        if command == .status { return statusData(healthy: true) }
        return Data("{\"schema_version\":2,\"command\":\"dev ensure\",\"status\":\"started\",\"ready\":true}".utf8)
    }
    let target = try #require(CLIResponse.decode(DevStatus.self, data: statusData(), command: .status).targets?.first)
    let host = NSHostingView(rootView: TargetRow(target: target, project: "/tmp/native-control", store: store))
    let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 420, height: 150),
                          styleMask: [.borderless], backing: .buffered, defer: false)
    window.isReleasedWhenClosed = false
    window.contentView = host
    window.alphaValue = 0
    window.ignoresMouseEvents = true
    window.orderBack(nil)
    host.layoutSubtreeIfNeeded()
    try await Task.sleep(for: .milliseconds(100))
    func subviews(_ view: NSView) -> [NSView] { [view] + view.subviews.flatMap(subviews) }
    let buttons = subviews(host).compactMap { $0 as? NSButton }

    // The first native action in the rendered offline row is Start; disclosure follows both actions.
    let startButton = try #require(buttons.min { $0.frame.minX < $1.frame.minX })
    startButton.performClick(nil)
    try await waitUntil { store.receipts["shared"] != nil }
    #expect(store.receipts["shared"]?.message == "服务已就绪")
    #expect(!window.isKeyWindow && window.alphaValue == 0)
    #expect(NSWorkspace.shared.frontmostApplication?.processIdentifier == foreground)
    window.close()
}
