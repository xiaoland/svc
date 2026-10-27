import AppKit
import Foundation
import SwiftUI
import Testing
@testable import SVCMenuBar

@Test(.enabled(if: ProcessInfo.processInfo.environment["SVC_RENDER_DIR"] != nil, "设置 SVC_RENDER_DIR 生成离屏界面证据"))
@MainActor func offscreenPanelRendersWithoutActivatingApplication() async throws {
    let directory = URL(fileURLWithPath: try #require(ProcessInfo.processInfo.environment["SVC_RENDER_DIR"]))
    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
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
    #expect(!NSApplication.shared.isActive)
}

private func renderData() throws -> Data {
    var snapshot = try #require(JSONSerialization.jsonObject(with: statusData(healthy: true)) as? [String: Any])
    let healthy = try #require((snapshot["resources"] as? [[String: Any]])?.first)
    var offline = healthy
    offline["resource"] = "worker"
    offline["label"] = "后台控制者"
    offline["entry_id"] = "entry-worker"
    offline["observations"] = [["key": "state", "label": "运行状态", "state": "unknown", "source": "tcp://127.0.0.1:3001", "checked_at": "2026-10-27T00:00:00.000Z", "stale": false]]
    var manual = offline
    manual["resource"] = "database"
    manual["label"] = "开发数据库"
    manual["entry_id"] = "entry-database"
    manual["actions"] = [["key": "destroy", "kind": "manual", "intent": "销毁数据库", "traits": ["provision"], "effect_scope": "共享数据库", "data_effect": "delete", "convergent": false, "steps": ["在数据库控制台中确认删除"]]]
    snapshot["resources"] = [healthy, offline, manual]
    return try JSONSerialization.data(withJSONObject: snapshot)
}

@Test @MainActor func hiddenNativeControlsInvokeActionsWithoutTakingFocus() async throws {
    NSApplication.shared.setActivationPolicy(.prohibited)
    let defaults = preferences(["/tmp/native-control"])
    let store = AppStore(preferences: defaults) { _, command, _, _ in
        if command == .status { return statusData(healthy: true) }
        return actionData()
    }
    let target = try #require(CLIResponse.decode(DevCatalog.self, data: statusData(), command: .status).resources.first)
    let host = NSHostingView(rootView: ResourceRow(resource: target, project: "/tmp/native-control", store: store))
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

    let startButton = try #require(buttons.first { $0.accessibilityIdentifier() == "entry-web/ensure" })
    startButton.performClick(nil)
    try await waitUntil { store.receipts["entry-web"] != nil }
    #expect(store.receipts["entry-web"]?.message == "声明动作已完成。")
    #expect(!window.isKeyWindow && window.alphaValue == 0)
    #expect(!NSApplication.shared.isActive)
    window.close()
}
