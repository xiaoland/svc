import AppKit
import SwiftUI
import Foundation

let bundleID = "dev.svc.resource-observation"

@MainActor func descendants(_ view: NSView) -> [NSView] { [view] + view.subviews.flatMap(descendants) }

@MainActor final class ObservationDelegate: NSObject, NSApplicationDelegate {
    let root: URL
    let cli: String
    var tokens: [NSObjectProtocol] = []
    var activations = 0
    var keys = 0
    var report: [String: Any] = [:]
    var productDelegate: AppDelegate?
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        productDelegate?.applicationShouldTerminate(sender) ?? .terminateNow
    }
    init(root: URL, cli: String) { self.root = root; self.cli = cli }
    func applicationDidFinishLaunching(_ note: Notification) {
        tokens.append(NotificationCenter.default.addObserver(forName: NSApplication.didBecomeActiveNotification, object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.activations += 1 }
        })
        tokens.append(NotificationCenter.default.addObserver(forName: NSWindow.didBecomeKeyNotification, object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.keys += 1 }
        })
        Task {
            do { try await observe() } catch { report["error"] = error.localizedDescription }
            report["policy"] = NSApp.activationPolicy() == .accessory ? "accessory" : "other"
            report["activation_events"] = activations
            report["key_window_events"] = keys
            report["active"] = NSApp.isActive
            let data = try! JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
            try! data.write(to: root.appendingPathComponent("native.json"))
            NSApp.terminate(nil)
        }
    }
    func until(_ condition: () -> Bool) async throws {
        let end = Date().addingTimeInterval(120)
        while !condition() {
            if Date() > end { throw CLIError(message: "observation timeout") }
            try await Task.sleep(for: .milliseconds(20))
        }
    }
    func render(_ store: AppStore, name: String) throws {
        for dark in [false, true] {
            let host = NSHostingView(rootView: MenuPanel(store: store, openSettings: {})
                .background(Color(nsColor: .windowBackgroundColor))
                .environment(\.colorScheme, dark ? .dark : .light))
            host.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)
            host.frame = NSRect(x: 0, y: 0, width: 420, height: 640)
            host.layoutSubtreeIfNeeded()
            host.setFrameSize(host.fittingSize)
            host.layoutSubtreeIfNeeded()
            guard let bitmap = host.bitmapImageRepForCachingDisplay(in: host.bounds) else { throw CLIError(message: "no bitmap") }
            host.cacheDisplay(in: host.bounds, to: bitmap)
            try bitmap.representation(using: .png, properties: [:])!.write(to: root.appendingPathComponent("\(name)-\(dark ? "dark" : "light").png"))
            let rows = NSHostingView(rootView: VStack(alignment: .leading, spacing: 16) {
                ForEach(store.projects) { project in
                    ForEach(project.snapshot?.resources ?? []) { resource in
                        ResourceRow(resource: resource, project: project.path, store: store)
                    }
                }
            }.padding(16).frame(width: 420).background(Color(nsColor: .windowBackgroundColor))
                .environment(\.colorScheme, dark ? .dark : .light))
            rows.appearance = host.appearance
            rows.layoutSubtreeIfNeeded()
            rows.setFrameSize(rows.fittingSize)
            rows.layoutSubtreeIfNeeded()
            if let image = rows.bitmapImageRepForCachingDisplay(in: rows.bounds) {
                rows.cacheDisplay(in: rows.bounds, to: image)
                try image.representation(using: .png, properties: [:])!.write(to: root.appendingPathComponent("\(name)-rows-\(dark ? "dark" : "light").png"))
            }

        }
    }
    func observe() async throws {
        let domain = "svc-native-observe-\(UUID())"
        let defaults = UserDefaults(suiteName: domain)!
        defer { defaults.removePersistentDomain(forName: domain) }
        let project = root.appendingPathComponent("开发资源与很长名称的隔离项目").path
        defaults.set([project], forKey: "projects")
        defaults.set(cli, forKey: "cliPath")
        defaults.set("/usr/bin:/bin", forKey: "searchPath")
        let store = AppStore(preferences: defaults)
        productDelegate = AppDelegate(store: store)
        await store.refreshAll()
        guard let initial = store.projects.first?.snapshot else { throw CLIError(message: store.projects.first?.error ?? "no snapshot") }
        report["initial_resources"] = initial.resources.map(\.resource)
        report["observations"] = initial.resources.map { ["resource": $0.resource, "states": $0.observations.map { ["key": $0.key, "state": $0.state, "stale": String($0.isStale), "value": $0.value?.text ?? ""] }] }
        try render(store, name: "resources")
        var effects: [[String: Any]] = []
        for (name, action) in [("shared", "destroy"), ("reference", "manual"), ("connection", "disconnect"), ("install", "update"), ("install", "manual"), ("wait", "stop"), ("wait", "reject")] {
            guard let resource = store.projects.first?.snapshot?.resources.first(where: { $0.resource == name }) else { throw CLIError(message: "missing resource") }
            let host = NSHostingView(rootView: ResourceRow(resource: resource, project: project, store: store)
                .frame(width: 388).background(Color(nsColor: .windowBackgroundColor)).environment(\.colorScheme, .light))
            host.appearance = NSAppearance(named: .aqua)
            let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 420, height: 320), styleMask: [.borderless], backing: .buffered, defer: false)
            window.isReleasedWhenClosed = false
            window.contentView = host
            window.alphaValue = 0
            window.ignoresMouseEvents = true
            window.orderBack(nil)
            defer { window.close() }
            host.layoutSubtreeIfNeeded()
            try await Task.sleep(for: .milliseconds(100))
            if name == "install" && action == "manual" {
                let native = descendants(host).compactMap { $0 as? NSButton }
                report["detail_controls"] = native.map { ["title": $0.title, "label": $0.accessibilityLabel() ?? "", "identifier": $0.accessibilityIdentifier()] }
                let disclosure = native.filter { $0.accessibilityLabel() == resource.label + " 详情" }
                if disclosure.count == 1 {
                    disclosure[0].performClick(nil)
                    try await Task.sleep(for: .milliseconds(100))
                    report["detail_opened"] = true
                }
                let observe = native.filter { $0.accessibilityIdentifier() == resource.entryId + "/observe/permission" }
                if observe.count == 1 {
                    observe[0].performClick(nil)
                    try await until { !store.refreshes.isEmpty }
                    try await until { store.refreshes.isEmpty }
                    try await Task.sleep(for: .milliseconds(100))
                    report["manual_facet_requested"] = store.projects[0].snapshot?.resources.first { $0.resource == "install" }?.observations.contains { $0.key == "permission" }
                }
            }
            let found = descendants(host).compactMap { $0 as? NSButton }.filter { $0.accessibilityIdentifier() == resource.entryId + "/" + action }
            guard found.count == 1 else { throw CLIError(message: "semantic button not unique") }
            found[0].performClick(nil)
            if name == "wait" && action == "stop" {
                try await until { FileManager.default.fileExists(atPath: self.root.appendingPathComponent("waiting").path) }
                // AppKit waits in a nested modal loop; cancel from that loop, not the blocked Task.
                let cancel = Timer(timeInterval: 0.2, repeats: false) { [self] _ in
                    MainActor.assumeIsolated {
                        report["quit_pending_before_cancel"] = store.quitPending
                        do { try render(store, name: "waiting") } catch { report["waiting_render_error"] = error.localizedDescription }
                        store.cancelQuit()
                        report["quit_pending_after_cancel"] = store.quitPending
                        report["operation_survived_cancel_quit"] = !store.operations.isEmpty
                    }
                }
                RunLoop.main.add(cancel, forMode: .modalPanel)
                RunLoop.main.add(cancel, forMode: .default)
                NSApp.terminate(nil)
                try Data().write(to: root.appendingPathComponent("gate"))
            }
            try await until { store.operations.isEmpty && store.refreshes.isEmpty }
            if name == "install" && action == "manual" {
                host.setFrameSize(host.fittingSize)
                host.layoutSubtreeIfNeeded()
                if let bitmap = host.bitmapImageRepForCachingDisplay(in: host.bounds) {
                    host.cacheDisplay(in: host.bounds, to: bitmap)
                    try bitmap.representation(using: .png, properties: [:])!.write(to: root.appendingPathComponent("manual-details.png"))
                    report["manual_details_rendered"] = true
                }
            }
            let receipt = store.receipts[resource.entryId]
            effects.append(["resource": name, "action": action, "status": receipt?.result?.status ?? "error", "message": receipt?.message ?? "missing", "button": found[0].accessibilityIdentifier(), "key_window": window.isKeyWindow])
        }
        report["manual_facet_retained"] = store.projects[0].snapshot?.resources.first { $0.resource == "install" }?.observations.contains { $0.key == "permission" }
        var bindingEffects: [String] = []
        let binding = NSHostingView(rootView: ResourceActionButton(title: "安装", semanticID: "first/install") { bindingEffects.append("first") })
        binding.layoutSubtreeIfNeeded()
        descendants(binding).compactMap { $0 as? NSButton }.first { $0.accessibilityIdentifier() == "first/install" }?.performClick(nil)
        binding.rootView = ResourceActionButton(title: "安装", semanticID: "second/install") { bindingEffects.append("second") }
        binding.layoutSubtreeIfNeeded()
        descendants(binding).compactMap { $0 as? NSButton }.first { $0.accessibilityIdentifier() == "second/install" }?.performClick(nil)
        report["rebound_effects"] = bindingEffects
        report["receipts_by_entry"] = store.receipts.values.map { ["resource": $0.resource, "entry_id": $0.entryId, "action": $0.action, "status": $0.result?.status ?? "error"] }
        report["actions"] = effects
        try render(store, name: "after-actions")
        let reopened = AppStore(preferences: defaults)
        report["reopened_preferences"] = reopened.projects.map(\.path)
        report["explicit_cli_preserved"] = reopened.configuration.executable == cli
        report["reopened_has_old_snapshot"] = reopened.projects.contains { $0.snapshot != nil }
        await reopened.refreshAll()
        report["reopened_resources"] = reopened.resourceCount
        try Data("{\"schema_version\":4}".utf8).write(to: URL(fileURLWithPath: project).appendingPathComponent("svc.json"))
        await reopened.refreshAll()
        report["migration_message"] = reopened.projects.first?.error
        report["invalid_configuration_snapshot_cleared"] = reopened.projects.first?.snapshot == nil
        try render(reopened, name: "migration")
    }
}

@MainActor func monitor(bundle: String, root: URL, cli: String) throws {
    var activated = 0
    let workspace = NSWorkspace.shared
    let token = workspace.notificationCenter.addObserver(forName: NSWorkspace.didActivateApplicationNotification, object: nil, queue: .main) { event in
        let app = event.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication
        let matches = app?.bundleIdentifier == bundleID
        MainActor.assumeIsolated { if matches { activated += 1 } }
    }
    defer { workspace.notificationCenter.removeObserver(token) }
    let launcher = Process()
    launcher.executableURL = URL(fileURLWithPath: "/usr/bin/open")
    launcher.arguments = ["-g", "-n", "-W", bundle, "--args", root.path, cli]
    try launcher.run()
    let deadline = Date().addingTimeInterval(240)
    while launcher.isRunning && Date() < deadline { RunLoop.current.run(until: Date().addingTimeInterval(0.05)) }
    if launcher.isRunning { launcher.terminate(); throw CLIError(message: "native observer timeout") }
    var report = try JSONSerialization.jsonObject(with: Data(contentsOf: root.appendingPathComponent("native.json"))) as! [String: Any]
    report["external_activation_events"] = activated
    report["launcher_exit"] = launcher.terminationStatus
    FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]))
}

@main struct NativeObservation {
    @MainActor static func main() throws {
        let args = CommandLine.arguments
        if args[1] == "--monitor" { try monitor(bundle: args[2], root: URL(fileURLWithPath: args[3]), cli: args[4]) }
        else {
            setenv("XDG_RUNTIME_DIR", URL(fileURLWithPath: args[1]).appendingPathComponent("runtime").path, 1)
            let app = NSApplication.shared
            app.setActivationPolicy(.accessory)
            let delegate = ObservationDelegate(root: URL(fileURLWithPath: args[1]), cli: args[2])
            app.delegate = delegate
            app.run()
        }
    }
}
