import AppKit
import SwiftUI

@main struct InspectHarness {
    @MainActor static func main() async throws {
        let app = NSApplication.shared
        app.setActivationPolicy(.prohibited)
        if CommandLine.arguments[1] == "--live" {
            let configuration = CLIConfiguration(executable: CommandLine.arguments[2], searchPath: CLIConfiguration.defaultSearchPath)
            let client = CLIClient(configuration: configuration)
            let data = try await client.requestGlobal(.monitor, arguments: ["--project-root", "/Volumes/WorkSSD/Development/svc-dev-lab"])
            let snapshot = try CLIResponse.decode(ActivitySnapshot.self, data: data, command: .monitor)
            guard let item = snapshot.externalExecutions?.first(where: { $0.provider == "pi" && $0.canTerminate }) else { throw CLIError(message: "客户端未读到原生 Pi 执行") }
            let logData = try await client.requestGlobal(.logs, arguments: [item.id])
            let logs = try CLIResponse.decode(ExecutionLogsResponse.self, data: logData, command: .logs)
            guard logs.executionId == item.id, logs.text.contains("SVC native Pi acceptance") else { throw CLIError(message: "原生日志身份或内容不符") }
            let stopped = try await client.requestGlobal(.terminate, arguments: [item.id, "--by", "human"])
            let receipt = try CLIResponse.decode(TerminationReceipt.self, data: stopped, command: .terminate)
            guard receipt.executionId == item.id, receipt.status == "requested" else { throw CLIError(message: "原生停止回执不符") }
            print("{\"nativeClientMonitor\":true,\"nativeClientLogs\":true,\"nativeClientStop\":true,\"applicationActive\":false}")
            return
        }
        let evidence = URL(fileURLWithPath: CommandLine.arguments[1])
        let temporary = FileManager.default.temporaryDirectory.appendingPathComponent("svc-harness-ui-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: temporary, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: temporary) }
        let cli = temporary.appendingPathComponent("svc")
        let recorded = evidence.appendingPathComponent("owned-pi-monitor.json").path.replacingOccurrences(of: "'", with: "'\\''")
        try "#!/bin/sh\nexec /bin/cat '\(recorded)'\n".write(to: cli, atomically: true, encoding: .utf8)
        try FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: cli.path)
        let suite = "svc-harness-ui-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        defaults.set(cli.path, forKey: "cliPath")
        defaults.set(["/Volumes/WorkSSD/Development/svc-dev-lab"], forKey: "projects")
        let store = AppStore(preferences: defaults)
        await store.activity.refresh(store.configuration)
        guard let snapshot = store.activity.snapshot, let execution = snapshot.externalExecutions?.first(where: { $0.provider == "pi" }), execution.canTerminate else { throw CLIError(message: "未解码真实 Pi 运行快照") }
        var report: [String: Any] = ["recordedNativeSnapshot": true, "schema": 3, "project": execution.projectPath ?? "", "usageAvailable": execution.usage != nil]
        for dark in [false, true] {
            let row = NSHostingView(rootView: HarnessExecutionRow(execution: execution, store: store).padding(12).background(Color(nsColor: .windowBackgroundColor)))
            row.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)
            try await capture(row, width: 420, to: evidence.appendingPathComponent(dark ? "native-row-dark.png" : "native-row.png"))
            let stop = buttons(row).first { $0.accessibilityIdentifier() == execution.id + "/stop" }
            guard let stop else { throw CLIError(message: "未提供原生停止控件") }
            report["stopLabel"] = stop.accessibilityLabel()
            stop.performClick(nil)
            try await capture(row, width: 420, to: evidence.appendingPathComponent(dark ? "native-confirm-dark.png" : "native-confirm.png"))
            guard buttons(row).contains(where: { $0.accessibilityIdentifier() == execution.id + "/confirm-stop" }) else { throw CLIError(message: "缺少范围确认") }
            report["stopRequiresConfirmation"] = true
            try press(execution.id + "/cancel-stop", in: row)
            try press(execution.id + "/details", in: row)
            try await capture(row, width: 420, to: evidence.appendingPathComponent(dark ? "native-details-dark.png" : "native-details.png"))
            report["logsActionAvailable"] = buttons(row).contains { $0.accessibilityIdentifier() == execution.id + "/logs" }
            report["rowHasWindow"] = row.window != nil
        }
        for width: CGFloat in [420, 740] {
            let list = NSHostingView(rootView: ExecutionListView(store: store).background(Color(nsColor: .windowBackgroundColor)))
            try await capture(list, width: width, to: evidence.appendingPathComponent("native-list-\(Int(width)).png"))
        }
        let settings = NSHostingView(rootView: SettingsView(store: store))
        try await capture(settings, width: 560, to: evidence.appendingPathComponent("native-settings.png"))
        report["applicationActive"] = app.isActive
        report["controlRequestsSent"] = 0
        let data = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
        try data.write(to: evidence.appendingPathComponent("native-ui.json"))
        print(String(decoding: data, as: UTF8.self))
    }
    @MainActor static func buttons(_ view: NSView) -> [NSButton] { ([view] + view.subviews.flatMap { descendants($0) }).compactMap { $0 as? NSButton } }
    @MainActor static func descendants(_ view: NSView) -> [NSView] { [view] + view.subviews.flatMap { descendants($0) } }
    @MainActor static func press(_ id: String, in view: NSView) throws {
        guard let button = buttons(view).first(where: { $0.accessibilityIdentifier() == id }) else { throw CLIError(message: "未找到 \(id)") }
        button.performClick(nil)
    }
    @MainActor static func capture<V>(_ view: NSHostingView<V>, width: CGFloat, to url: URL) async throws where V: View {
        view.frame = NSRect(x: 0, y: 0, width: width, height: 1000)
        view.layoutSubtreeIfNeeded()
        try await Task.sleep(for: .milliseconds(100))
        view.setFrameSize(NSSize(width: width, height: view.fittingSize.height))
        view.layoutSubtreeIfNeeded()
        guard let bitmap = view.bitmapImageRepForCachingDisplay(in: view.bounds) else { throw CLIError(message: "无法建立离屏图") }
        view.cacheDisplay(in: view.bounds, to: bitmap)
        guard let png = bitmap.representation(using: .png, properties: [:]) else { throw CLIError(message: "无法编码 PNG") }
        try png.write(to: url)
    }
}
