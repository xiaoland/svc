import AppKit
import SwiftUI

@main
struct InspectLayout {
    @MainActor static func main() async throws {
        let app = NSApplication.shared
        app.setActivationPolicy(.prohibited)
        let evidence = URL(fileURLWithPath: CommandLine.arguments[1])
        let temporary = FileManager.default.temporaryDirectory.appendingPathComponent("svc-project-layout-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: temporary, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: temporary) }
        let cli = temporary.appendingPathComponent("svc")
        let monitor = evidence.appendingPathComponent("live-monitor.json").path.replacingOccurrences(of: "'", with: "'\\''")
        try "#!/bin/sh\nexec /bin/cat '\(monitor)'\n".write(to: cli, atomically: true, encoding: .utf8)
        try FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: cli.path)
        let suite = "svc-project-layout-\(UUID().uuidString)"
        let preferences = UserDefaults(suiteName: suite)!
        defer { preferences.removePersistentDomain(forName: suite) }
        let roots = ["/Volumes/WorkSSD/Development/svc-dev-lab", "/Volumes/WorkSSD/Development/svc-dev-lab-peer"]
        preferences.set(roots, forKey: "projects")
        preferences.set(cli.path, forKey: "cliPath")
        let store = AppStore(preferences: preferences) { _, _, project, _ in
            let name = URL(fileURLWithPath: project).lastPathComponent + "-catalog.json"
            return try Data(contentsOf: evidence.appendingPathComponent(name))
        }
        let section = store.createSection("验收")!
        for root in roots { store.moveProject(root, to: section) }
        await store.refreshAll()
        await store.activity.refresh(store.configuration)
        guard store.activity.snapshot?.projects?.count == 2 else { throw CLIError(message: "未解码两个验收项目") }
        let controller = MainWindowController(store: store, openSettings: {}, closed: {})
        let window = controller.window!
        window.setFrameAutosaveName("")
        var snapshots: [[String: Any]] = []
        for width: CGFloat in [1040, 740] {
            window.setContentSize(NSSize(width: width, height: 780))
            window.contentView?.layoutSubtreeIfNeeded()
            window.displayIfNeeded()
            try await Task.sleep(for: .milliseconds(200))
            if let frame = window.contentView?.superview {
                try render(frame, to: evidence.appendingPathComponent("projects-\(Int(width)).png"))
            }
            snapshots.append([
                "width": width, "windowVisible": window.isVisible,
                "applicationActive": app.isActive,
                "toolbarLabels": window.toolbar?.items.map(\.label) ?? [],
                "projects": store.activity.snapshot?.projects?.count ?? 0,
            ])
        }
        let scope = NSHostingView(rootView: ExecutionListView(store: store, projectPaths: Set([roots[0]])).frame(width: 500).background(Color(nsColor: .windowBackgroundColor)))
        scope.frame = NSRect(x: 0, y: 0, width: 500, height: 600)
        scope.layoutSubtreeIfNeeded()
        scope.setFrameSize(scope.fittingSize)
        try render(scope, to: evidence.appendingPathComponent("project-executions.png"))
        snapshots.append(["projectExecutionHostHasWindow": scope.window != nil,
                          "applicationActive": app.isActive,
                          "selectedProject": roots[0]])
        let data = try JSONSerialization.data(withJSONObject: snapshots, options: [.prettyPrinted, .sortedKeys])
        print(String(decoding: data, as: UTF8.self))
    }

    @MainActor static func render(_ view: NSView, to url: URL) throws {
        view.layoutSubtreeIfNeeded()
        guard let bitmap = view.bitmapImageRepForCachingDisplay(in: view.bounds) else { throw CLIError(message: "无法建立离屏图") }
        view.cacheDisplay(in: view.bounds, to: bitmap)
        guard let png = bitmap.representation(using: .png, properties: [:]) else { throw CLIError(message: "无法编码离屏图") }
        try png.write(to: url)
    }
}
