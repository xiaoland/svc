import AppKit
import SwiftUI

// A finite presentation replay. It never calls an actual resource controller.
@main struct ObserveInformationHierarchy {
    @MainActor static func main() async throws {
        DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + 20) { _exit(124) }
        let app = NSApplication.shared
        app.setActivationPolicy(.prohibited)
        let repository = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        let output = repository.appendingPathComponent("tasks/dev-interface-simplification/evidence/hierarchy")
        let fixtures = repository.appendingPathComponent("tasks/dev-project-usage/evidence")
        let monitor = repository.appendingPathComponent("tasks/dev-harness-integration/evidence/owned-pi-monitor.json")
        let temporary = FileManager.default.temporaryDirectory.appendingPathComponent("svc-hierarchy-\(UUID())")
        try FileManager.default.createDirectory(at: temporary, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: temporary) }
        let cli = temporary.appendingPathComponent("svc")
        try "#!/bin/sh\nexec /bin/cat '\(monitor.path.replacingOccurrences(of: "'", with: "'\\''"))'\n".write(to: cli, atomically: true, encoding: .utf8)
        try FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: cli.path)
        let suite = "svc-hierarchy-\(UUID())"
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        let roots = ["/Volumes/WorkSSD/Development/svc-dev-lab", "/Volumes/WorkSSD/Development/svc-dev-lab-peer"]
        defaults.set(roots, forKey: "projects")
        defaults.set(cli.path, forKey: "cliPath")
        let store = AppStore(preferences: defaults) { _, command, path, _ in
            guard command == .status else { throw CLIError(message: "呈现脚本禁止控制请求") }
            return try Data(contentsOf: fixtures.appendingPathComponent(URL(fileURLWithPath: path).lastPathComponent + "-catalog.json"))
        }
        await store.refreshAll()
        await store.activity.refresh(store.configuration)
        guard let resource = store.projects.first?.snapshot?.resources.first,
              let snapshot = store.activity.snapshot else { throw CLIError(message: "未读到记录的快照") }
        var report: [String: Any] = ["recordedMonitorSchema": 3, "scope": "Offscreen product view replay; no live popover anchoring, VoiceOver or human acceptance", "controlRequestsSent": 0]
        for dark in [false, true] {
            let panel = NSHostingView(rootView: MenuPanel(store: store, openSettings: {}))
            panel.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)
            report[dark ? "darkPanelHeight" : "panelHeight"] = try await capture(panel, width: 420, to: output.appendingPathComponent(dark ? "panel-dark.png" : "panel.png"))
        }
        let pressure = NSHostingView(rootView: HostPressureView(activity: store.activity).background(Color(nsColor: .windowBackgroundColor)))
        report["pressureSummaryHeight"] = try await capture(pressure, width: 420, to: output.appendingPathComponent("pressure-summary.png"))
        for stale in [false, true] {
            let details = NSHostingView(rootView: HostPressureDetails(pressure: snapshot.pressure, checkedAt: store.activity.checkedAt, stale: stale, close: {}).background(Color(nsColor: .windowBackgroundColor)))
            report[stale ? "stalePressureDetailsHeight" : "pressureDetailsHeight"] = try await capture(details, width: 340, to: output.appendingPathComponent(stale ? "pressure-stale.png" : "pressure.png"))
        }
        let row = NSHostingView(rootView: ResourceRow(resource: resource, project: roots[0], store: store).padding(12).frame(width: 420).background(Color(nsColor: .windowBackgroundColor)))
        report["collapsedResourceHeight"] = try await capture(row, width: 420, to: output.appendingPathComponent("resource.png"))
        report["actionsBeforeExpansion"] = buttons(row).filter { resource.actions.map { resource.entryId + "/" + $0.key }.contains($0.accessibilityIdentifier()) }.map { $0.title }
        try press(resource.entryId + "/details", in: row)
        report["expandedResourceHeight"] = try await capture(row, width: 420, to: output.appendingPathComponent("resource-expanded.png"))
        report["diagnosticsInitiallyCollapsed"] = buttons(row).first { $0.accessibilityIdentifier() == resource.entryId + "/diagnostics" }?.accessibilityValue() as? String
        try press(resource.entryId + "/diagnostics", in: row)
        report["diagnosticsHeight"] = try await capture(row, width: 420, to: output.appendingPathComponent("resource-diagnostics.png"))
        report["diagnosticsAfterClick"] = buttons(row).first { $0.accessibilityIdentifier() == resource.entryId + "/diagnostics" }?.accessibilityValue() as? String
        try press(resource.entryId + "/diagnostics", in: row)
        report["restoredExpandedResourceHeight"] = try await capture(row, width: 420, to: output.appendingPathComponent("resource-restored.png"))
        // Explicit adverse presentation input; not a recorded real resource or action.
        var catalog = try JSONSerialization.jsonObject(with: Data(contentsOf: fixtures.appendingPathComponent("svc-dev-lab-catalog.json"))) as! [String: Any]
        var item = (catalog["resources"] as! [[String: Any]])[0]
        item["actions"] = [["key": "destroy", "kind": "manual", "intent": "删除验收数据", "traits": ["provision"], "effect_scope": "验收缓存", "data_effect": "delete", "convergent": false, "steps": ["在控制者界面核对数据后删除"]]]
        var observations = item["observations"] as! [[String: Any]]
        observations[0]["state"] = "unknown"; observations[0]["expires_at"] = nil; observations[0]["stale"] = false
        item["observations"] = observations; catalog["resources"] = [item]
        let adverse = try CLIResponse.decode(DevCatalog.self, data: JSONSerialization.data(withJSONObject: catalog), command: .status).resources[0]
        let warning = NSHostingView(rootView: ResourceRow(resource: adverse, project: roots[0], store: store).padding(12).frame(width: 420).background(Color(nsColor: .windowBackgroundColor)))
        _ = try await capture(warning, width: 420, to: output.appendingPathComponent("unknown-destructive.png"))
        report["destructiveActionLabel"] = buttons(warning).first { $0.accessibilityIdentifier() == adverse.entryId + "/destroy" }?.accessibilityLabel()
        let controller = MainWindowController(store: store, openSettings: {}, closed: {})
        let window = controller.window!
        window.setFrameAutosaveName("")
        window.setContentSize(NSSize(width: 740, height: 780))
        window.contentView?.layoutSubtreeIfNeeded()
        try await Task.sleep(for: .milliseconds(150))
        if let chrome = window.contentView?.superview { try render(chrome, to: output.appendingPathComponent("main-740.png")) }
        report["mainWindowVisible"] = window.isVisible
        report["applicationActive"] = app.isActive
        report["offscreenHostsHaveWindows"] = [row, pressure, warning].contains { $0.window != nil }
        try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]).write(to: output.appendingPathComponent("interface.json"))
        print("captured")
    }
    @MainActor static func descendants(_ view: NSView) -> [NSView] { [view] + view.subviews.flatMap { descendants($0) } }
    @MainActor static func buttons(_ view: NSView) -> [NSButton] { descendants(view).compactMap { $0 as? NSButton } }
    @MainActor static func press(_ id: String, in view: NSView) throws {
        guard let button = buttons(view).first(where: { $0.accessibilityIdentifier() == id }) else { throw CLIError(message: "未找到产品控件 \(id)") }
        button.performClick(nil)
    }
    @MainActor static func capture<V: View>(_ view: NSHostingView<V>, width: CGFloat, to url: URL) async throws -> CGFloat {
        view.frame = NSRect(x: 0, y: 0, width: width, height: 1000)
        view.layoutSubtreeIfNeeded()
        try await Task.sleep(for: .milliseconds(100))
        for _ in 0..<2 {
            view.setFrameSize(NSSize(width: width, height: view.fittingSize.height))
            view.layoutSubtreeIfNeeded()
            try await Task.sleep(for: .milliseconds(100))
        }
        try render(view, to: url)
        return view.bounds.height
    }
    @MainActor static func render(_ view: NSView, to url: URL) throws {
        view.layoutSubtreeIfNeeded()
        guard let bitmap = view.bitmapImageRepForCachingDisplay(in: view.bounds) else { throw CLIError(message: "无法建立离屏图") }
        view.cacheDisplay(in: view.bounds, to: bitmap)
        guard let png = bitmap.representation(using: .png, properties: [:]) else { throw CLIError(message: "无法编码 PNG") }
        try png.write(to: url)
    }
}
