import AppKit
import Foundation

@MainActor final class EventLog { var events: [[String: Any]] = [] }

@main struct InstallationObservation {
    @MainActor static func main() throws {
        let root = URL(fileURLWithPath: CommandLine.arguments[1])
        let workspace = NSWorkspace.shared
        let log = EventLog()
        var tokens: [NSObjectProtocol] = []
        for (name, kind) in [(NSWorkspace.didActivateApplicationNotification, "activate"), (NSWorkspace.didLaunchApplicationNotification, "launch"), (NSWorkspace.didTerminateApplicationNotification, "terminate")] {
            tokens.append(workspace.notificationCenter.addObserver(forName: name, object: nil, queue: .main) { event in
                guard let app = event.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication, app.bundleIdentifier == "dev.svc.menubar" else { return }
                let pid = app.processIdentifier
                let active = app.isActive
                MainActor.assumeIsolated {
                    log.events.append(["kind": kind, "pid": pid, "active": active, "time": Date().timeIntervalSince1970])
                }
            })
        }
        try Data().write(to: root.appendingPathComponent("monitor-ready"))
        let deadline = Date().addingTimeInterval(1200)
        while !FileManager.default.fileExists(atPath: root.appendingPathComponent("monitor-stop").path) && Date() < deadline {
            RunLoop.current.run(until: Date().addingTimeInterval(0.1))
        }
        let apps = workspace.runningApplications.filter { $0.bundleIdentifier == "dev.svc.menubar" }
        let report: [String: Any] = ["events": log.events, "activation_events": log.events.filter { ($0["kind"] as? String) == "activate" }.count, "running": apps.map { ["pid": $0.processIdentifier, "active": $0.isActive, "path": $0.bundleURL?.path ?? "", "accessory": $0.activationPolicy == .accessory] }, "completed": FileManager.default.fileExists(atPath: root.appendingPathComponent("monitor-stop").path)]
        try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]).write(to: root.appendingPathComponent("installation-lifecycle.json"))
        for token in tokens { workspace.notificationCenter.removeObserver(token) }
    }
}
