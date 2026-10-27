import AppKit
import SwiftUI
import Foundation

@MainActor func descendants(_ view: NSView) -> [NSView] { [view] + view.subviews.flatMap(descendants) }

@MainActor final class SectionObserver: NSObject, NSApplicationDelegate {
    let root: URL
    let cli: String
    var report: [String: Any] = [:]
    var windows: [NSWindow] = []
    var tokens: [NSObjectProtocol] = []
    var activations = 0
    var keys = 0
    init(root: URL, cli: String) { self.root = root; self.cli = cli }
    func applicationDidFinishLaunching(_ notification: Notification) {
        tokens.append(NotificationCenter.default.addObserver(forName: NSApplication.didBecomeActiveNotification, object: nil, queue: .main) { [weak self] _ in MainActor.assumeIsolated { self?.activations += 1 } })
        tokens.append(NotificationCenter.default.addObserver(forName: NSWindow.didBecomeKeyNotification, object: nil, queue: .main) { [weak self] _ in MainActor.assumeIsolated { self?.keys += 1 } })
        Task {
            do { try await observe() } catch { report["error"] = error.localizedDescription }
            for window in windows { window.close() }
            report["activation_events"] = activations
            report["key_window_events"] = keys
            report["active"] = NSApp.isActive
            try! JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]).write(to: root.appendingPathComponent("report.json"))
            NSApp.terminate(nil)
        }
    }
    func until(_ condition: () -> Bool) async throws {
        let deadline = Date().addingTimeInterval(40)
        while !condition() {
            if Date() > deadline { throw CLIError(message: "observation timeout") }
            try await Task.sleep(for: .milliseconds(20))
        }
    }
    func host<V: View>(_ view: V) async throws -> NSHostingView<some View> {
        let host = NSHostingView(rootView: view.frame(width: 420).background(Color(nsColor: .windowBackgroundColor)))
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 420, height: 640), styleMask: [.borderless], backing: .buffered, defer: false)
        window.isReleasedWhenClosed = false
        window.contentView = host
        window.alphaValue = 0
        window.ignoresMouseEvents = true
        window.orderBack(nil)
        windows.append(window)
        host.layoutSubtreeIfNeeded()
        try await Task.sleep(for: .milliseconds(100))
        return host
    }
    func press(_ host: NSView, _ id: String) throws {
        let matches = descendants(host).compactMap { $0 as? NSButton }.filter { $0.accessibilityIdentifier() == id }
        guard matches.count == 1 else { throw CLIError(message: "control not unique: \(id)") }
        matches[0].performClick(nil)
    }
    func render(_ store: AppStore, _ name: String) throws {
        for dark in [false, true] {
            let host = NSHostingView(rootView: MenuPanel(store: store, openSettings: {})
                .background(Color(nsColor: .windowBackgroundColor)).environment(\.colorScheme, dark ? .dark : .light))
            host.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)
            host.frame = NSRect(x: 0, y: 0, width: 420, height: 640)
            host.layoutSubtreeIfNeeded();host.setFrameSize(host.fittingSize);host.layoutSubtreeIfNeeded()
            guard let bitmap = host.bitmapImageRepForCachingDisplay(in: host.bounds) else { throw CLIError(message: "no bitmap") }
            host.cacheDisplay(in: host.bounds, to: bitmap)
            try bitmap.representation(using: .png, properties: [:])!.write(to: root.appendingPathComponent("\(name)-\(dark ? "dark" : "light").png"))
        }
    }
    func observe() async throws {
        let domain = "svc-sections-\(UUID())"
        let preferences = UserDefaults(suiteName: domain)!
        defer { preferences.removePersistentDomain(forName: domain) }
        let paths = ["alpha", "beta", "gamma"].map { root.appendingPathComponent($0).path }
        preferences.set(paths, forKey: "projects")
        preferences.set(cli, forKey: "cliPath")
        preferences.set("/usr/bin:/bin", forKey: "searchPath")
        let store = AppStore(preferences: preferences)
        await store.refreshAll()
        report["legacy_ungrouped"] = store.projects(in: nil).map(\.path) == paths && store.organization.sections.isEmpty
        report["legacy_not_rewritten"] = preferences.object(forKey: "projectSections") == nil
        var editorClosed = false
        let editor = try await host(SectionNameEditor(sectionID: nil, name: "", store: store) { editorClosed = true })
        let fields = descendants(editor).compactMap { $0 as? NSTextField }.filter { $0.placeholderString == "Section 名称" }
        guard fields.count == 1 else { throw CLIError(message: "name field not unique") }
        fields[0].stringValue = "  InKCre  "
        fields[0].delegate?.controlTextDidChange?(Notification(name: NSControl.textDidChangeNotification, object: fields[0]))
        try await Task.sleep(for: .milliseconds(100))
        try press(editor, "section-editor/save")
        guard let first = store.organization.sections.first?.id else { throw CLIError(message: "no created Section") }
        report["native_editor_saved"] = editorClosed && store.organization.sections[0].name == "InKCre"
        let second = store.createSection("工具")!
        store.moveProject(paths[0], to: first)
        store.moveProject(paths[1], to: first)
        report["membership"] = store.projects(in: first).map(\.path)
        let menuHost = try await host(MenuPanel(store: store, openSettings: {}))
        report["native_menu_inventory"] = descendants(menuHost).compactMap { view -> [String: Any]? in
            guard let menu = view.menu, !menu.items.isEmpty else { return nil }
            return ["class": String(describing: type(of: view)), "items": menu.items.map(\.title)]
        }
        try render(store, "expanded")
        let group = try await host(ProjectSectionView(section: store.organization.sections[0], store: store, addProject: {}, rename: {}))
        try press(group, "section/\(first)/toggle")
        report["native_collapse"] = store.organization.sections[0].collapsed
        store.moveSection(second, offset: -1)
        let renamed = try await host(SectionNameEditor(sectionID: second, name: "工具与多个项目组成的很长分组名称用于检查菜单栏宽度", store: store) {})
        try press(renamed, "section-editor/save")
        try render(store, "collapsed-long-name")
        let reopened = AppStore(preferences: preferences)
        report["reopened_order"] = reopened.organization.sections.map(\.name)
        report["reopened_collapsed"] = reopened.organization.sections.first { $0.id == first }?.collapsed
        report["reopened_members"] = reopened.projects(in: first).map(\.path)
        report["preferences_preserved"] = preferences.stringArray(forKey: "projects") == paths && reopened.configuration.executable == cli
        report["empty_rejected"] = store.createSection(" \n ") == nil
        report["duplicate_rejected"] = store.createSection("INKCRE") == nil
        store.addProject(URL(fileURLWithPath: paths[0]), sectionID: second)
        report["duplicate_project"] = ["count": store.projects.count, "same_section": store.organization.assignments[paths[0]] == first, "revealed": store.projectReveal?.path == paths[0], "expanded": store.organization.sections.first { $0.id == first }?.collapsed == false]
        let resource = store.projects[0].snapshot!.resources[0]
        let actionHost = try await host(ResourceRow(resource: resource, project: paths[0], store: store))
        try press(actionHost, resource.entryId + "/wait")
        try await until { FileManager.default.fileExists(atPath: self.root.appendingPathComponent("started").path) }
        store.moveProject(paths[0], to: second)
        store.toggleSection(second)
        store.deleteSection(first)
        report["inflight_after_move_delete"] = ["operations": store.operations.count, "running_badge": store.sectionActivity(second).running, "unassigned_beta": store.organization.assignments[paths[1]] == nil]
        try render(store, "inflight")
        try Data().write(to: root.appendingPathComponent("gate"))
        try await until { store.operations.isEmpty && store.refreshes.isEmpty }
        report["receipt_after_move"] = ["path": store.receipts[resource.entryId]?.projectPath ?? "", "status": store.receipts[resource.entryId]?.result?.status ?? "missing"]
        let current = store.projects[0].snapshot!.resources[0]
        store.perform(current.actions.first { $0.key == "fail" }!, resource: current, project: paths[0])
        try await until { store.operations.isEmpty && store.refreshes.isEmpty }
        report["collapsed_failure_visible"] = store.sectionActivity(second).attention
        try render(store, "failure")
        store.deleteSection(second)
        report["delete_preserves_projects"] = store.projects(in: nil).map(\.path) == paths
        report["delete_preserves_receipt"] = store.receipts[resource.entryId]?.projectPath == paths[0]
        let empty = store.createSection("空组")!
        try render(store, "empty-section")
        store.deleteSection(empty)
        let corrupt = Data("{\"schemaVersion\":999,\"sections\":[],\"assignments\":{}}".utf8)
        preferences.set(corrupt, forKey: "projectSections")
        let invalid = AppStore(preferences: preferences)
        report["invalid_preferences"] = ["error_visible": invalid.sectionStorageError != nil, "editing_blocked": invalid.createSection("不能覆盖") == nil, "raw_preserved": preferences.data(forKey: "projectSections") == corrupt, "projects_retained": invalid.projects.map(\.path) == paths]
    }
}

@main struct ObserveSections {
    @MainActor static func main() {
        let root = URL(fileURLWithPath: CommandLine.arguments[1])
        setenv("XDG_RUNTIME_DIR", root.appendingPathComponent("runtime").path, 1)
        let app = NSApplication.shared
        app.setActivationPolicy(.accessory)
        let observer = SectionObserver(root: root, cli: CommandLine.arguments[2])
        app.delegate = observer
        app.run()
    }
}
