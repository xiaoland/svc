import AppKit
import SwiftUI

@main
struct InspectInterface {
    @MainActor static func main() async throws {
        let app = NSApplication.shared
        app.setActivationPolicy(.prohibited)
        let fixtures = URL(fileURLWithPath: CommandLine.arguments[1])
        let output = URL(fileURLWithPath: CommandLine.arguments[2])
        let temporary = FileManager.default.temporaryDirectory.appendingPathComponent("svc-interface-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: temporary, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: temporary) }
        let cli = temporary.appendingPathComponent("svc")
        let monitor = fixtures.appendingPathComponent("live-monitor.json").path.replacingOccurrences(of: "'", with: "'\\''")
        try "#!/bin/sh\nexec /bin/cat '\(monitor)'\n".write(to: cli, atomically: true, encoding: .utf8)
        try FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: cli.path)
        let suite = "svc-interface-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        let roots = ["/Volumes/WorkSSD/Development/svc-dev-lab", "/Volumes/WorkSSD/Development/svc-dev-lab-peer"]
        defaults.set(roots, forKey: "projects")
        defaults.set(cli.path, forKey: "cliPath")
        let store = AppStore(preferences: defaults) { _, _, path, _ in
            try Data(contentsOf: fixtures.appendingPathComponent(URL(fileURLWithPath: path).lastPathComponent + "-catalog.json"))
        }
        let section = store.createSection("验收")!
        for path in roots { store.moveProject(path, to: section) }
        await store.refreshAll()
        await store.activity.refresh(store.configuration)
        var report: [String: Any] = ["recordedCLIReplay": true]
        for dark in [false, true] {
            let host = NSHostingView(rootView: MenuPanel(store: store, openSettings: {}))
            host.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)
            try await capture(host, width: 420, output: output.appendingPathComponent(dark ? "panel-dark.png" : "panel.png"))
            report[dark ? "darkPanelHeight" : "panelHeight"] = host.bounds.height
        }
        let controller = MainWindowController(store: store, openSettings: {}, closed: {})
        let window = controller.window!
        window.setFrameAutosaveName("")
        for width: CGFloat in [1040, 740] {
            window.setContentSize(NSSize(width: width, height: 780))
            window.contentView?.layoutSubtreeIfNeeded()
            window.displayIfNeeded()
            try await Task.sleep(for: .milliseconds(150))
            if let chrome = window.contentView?.superview { try render(chrome, to: output.appendingPathComponent("main-\(Int(width)).png")) }
        }
        report["windowVisible"] = window.isVisible
        report["toolbar"] = window.toolbar?.items.map(\.label) ?? []
        guard let resource = store.projects.first?.snapshot?.resources.first,
              let execution = store.activity.snapshot?.executions.first(where: { $0.canTerminate && $0.projectPath == roots[0] }) else {
            throw CLIError(message: "缺少实际记录重放对象")
        }
        let row = NSHostingView(rootView: ResourceRow(resource: resource, project: roots[0], store: store).padding(12).background(Color(nsColor: .windowBackgroundColor)))
        try await capture(row, width: 420, output: output.appendingPathComponent("resource.png"))
        report["collapsedResourceHeight"] = row.bounds.height
        report["collapsedResourceButtons"] = buttons(row).map { $0.accessibilityIdentifier() }
        try press(resource.entryId + "/details", in: row)
        try await capture(row, width: 420, output: output.appendingPathComponent("resource-details.png"))
        report["expandedResourceHeight"] = row.bounds.height
        report["resourceExpanded"] = buttons(row).first { $0.accessibilityIdentifier() == resource.entryId + "/details" }?.accessibilityValue() as? String
        let task = NSHostingView(rootView: ExecutionRow(execution: execution, store: store).padding(12).background(Color(nsColor: .windowBackgroundColor)))
        try await capture(task, width: 420, output: output.appendingPathComponent("execution.png"))
        let prefix = "execution/\(execution.id)"
        report["ordinaryStopVisible"] = buttons(task).contains { $0.accessibilityIdentifier() == prefix + "/terminate" && !$0.isHidden }
        report["forceHiddenUntilDetails"] = !buttons(task).contains { $0.accessibilityIdentifier() == prefix + "/force" }
        try press(prefix + "/details", in: task)
        try await capture(task, width: 420, output: output.appendingPathComponent("execution-details.png"))
        try press(prefix + "/force", in: task)
        try await capture(task, width: 420, output: output.appendingPathComponent("force-confirmation.png"))
        report["forceRequiresConfirmation"] = buttons(task).contains { $0.accessibilityIdentifier() == prefix + "/confirm-force" }
        try press(prefix + "/cancel-force", in: task)
        // A changed catalog is presentation-only input; no real control request is sent.
        var catalog = try JSONSerialization.jsonObject(with: Data(contentsOf: fixtures.appendingPathComponent("svc-dev-lab-catalog.json"))) as! [String: Any]
        var item = (catalog["resources"] as! [[String: Any]])[0]
        item["actions"] = [["key": "destroy", "kind": "manual", "intent": "删除验收数据", "traits": ["provision"], "effect_scope": "验收缓存", "data_effect": "delete", "convergent": false, "steps": ["在控制者界面核对数据后删除"]]]
        var observations = item["observations"] as! [[String: Any]]
        observations[0]["state"] = "unknown"
        observations[0]["expires_at"] = nil
        observations[0]["stale"] = false
        observations[0]["message"] = "无法核实当前状态"
        item["observations"] = observations
        catalog["resources"] = [item]
        let adverse = try CLIResponse.decode(DevCatalog.self, data: JSONSerialization.data(withJSONObject: catalog), command: .status).resources[0]
        let warning = NSHostingView(rootView: ResourceRow(resource: adverse, project: roots[0], store: store).padding(12).background(Color(nsColor: .windowBackgroundColor)))
        try await capture(warning, width: 420, output: output.appendingPathComponent("unknown-destructive.png"))
        report["destructiveActionVisible"] = buttons(warning).contains { $0.accessibilityIdentifier() == adverse.entryId + "/destroy" }
        report["applicationActive"] = app.isActive
        report["offscreenHostsHaveWindows"] = [row, task, warning].contains { $0.window != nil }
        let data = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
        try data.write(to: output.appendingPathComponent("interface.json"))
        print(String(decoding: data, as: UTF8.self))
    }

    @MainActor static func buttons(_ view: NSView) -> [NSButton] {
        ([view] + view.subviews.flatMap { descendants($0) }).compactMap { $0 as? NSButton }
    }
    @MainActor static func descendants(_ view: NSView) -> [NSView] { [view] + view.subviews.flatMap { descendants($0) } }
    @MainActor static func press(_ id: String, in view: NSView) throws {
        guard let button = buttons(view).first(where: { $0.accessibilityIdentifier() == id }) else { throw CLIError(message: "未找到产品控件 \(id)") }
        button.performClick(nil)
    }
    @MainActor static func capture<V>(_ host: NSHostingView<V>, width: CGFloat, output: URL) async throws where V: View {
        host.frame = NSRect(x: 0, y: 0, width: width, height: 1000)
        host.layoutSubtreeIfNeeded()
        try await Task.sleep(for: .milliseconds(100))
        host.setFrameSize(NSSize(width: width, height: host.fittingSize.height))
        try render(host, to: output)
    }
    @MainActor static func render(_ view: NSView, to url: URL) throws {
        view.layoutSubtreeIfNeeded()
        guard let bitmap = view.bitmapImageRepForCachingDisplay(in: view.bounds) else { throw CLIError(message: "无法建立离屏图") }
        view.cacheDisplay(in: view.bounds, to: bitmap)
        guard let png = bitmap.representation(using: .png, properties: [:]) else { throw CLIError(message: "无法编码离屏图") }
        try png.write(to: url)
    }
}
