import AppKit
import Foundation

final class EventLog: @unchecked Sendable {
    private let lock = NSLock()
    private var events: [[String: Any]] = []
    private var notificationCount = 0
    private var notificationKinds: [String: Int] = [:]
    private var pids: Set<pid_t> = []
    private var watched: Set<pid_t> = []
    private var activeObservers: [NSKeyValueObservation] = []
    private var activeApplications: [NSRunningApplication] = []
    func watch(_ app: NSRunningApplication) {
        let pid = app.processIdentifier
        lock.lock()
        let added = watched.insert(pid).inserted
        lock.unlock()
        guard added else { return }
        let observer = app.observe(\.isActive, options: [.initial, .new]) { [weak self] _, change in
            guard let self, let active = change.newValue else { return }
            lock.lock(); defer { lock.unlock() }
            events.append(["kind": "active-state", "pid": pid, "active": active, "time": Date().timeIntervalSince1970])
        }
        lock.lock(); activeObservers.append(observer); activeApplications.append(app); lock.unlock()
    }
    func stop() {
        for observer in activeObservers { observer.invalidate() }
        activeObservers.removeAll()
        activeApplications.removeAll()
    }
    func record(kind: String, pid: pid_t, active: Bool, matches: Bool) {
        lock.lock(); defer { lock.unlock() }
        notificationCount += 1
        notificationKinds[kind, default: 0] += 1
        if matches { events.append(["kind": kind, "pid": pid, "active": active, "time": Date().timeIntervalSince1970]) }
    }
    func processes(_ current: Set<pid_t>) {
        lock.lock(); defer { lock.unlock() }
        for pid in current.subtracting(pids) { events.append(["kind": "appeared", "pid": pid, "time": Date().timeIntervalSince1970]) }
        for pid in pids.subtracting(current) { events.append(["kind": "disappeared", "pid": pid, "time": Date().timeIntervalSince1970]) }
        pids = current
    }
    func snapshot() -> ([[String: Any]], Int, [String: Int]) {
        lock.lock(); defer { lock.unlock() }
        return (events, notificationCount, notificationKinds)
    }
}

@main struct InstallationObservation {
    @MainActor static func main() throws {
        let root = URL(fileURLWithPath: CommandLine.arguments[1])
        NSApplication.shared.setActivationPolicy(.prohibited)
        let workspace = NSWorkspace.shared
        let log = EventLog()
        var tokens: [NSObjectProtocol] = []
        for (name, kind) in [(NSWorkspace.didActivateApplicationNotification, "activate")] {
            tokens.append(workspace.notificationCenter.addObserver(forName: name, object: nil, queue: nil) { event in
                guard let app = event.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication else { return }
                log.record(kind: kind, pid: app.processIdentifier, active: app.isActive, matches: app.bundleIdentifier == "dev.svc.menubar")
            })
        }
        // LSUIElement apps do not emit workspace launch/terminate notifications.
        let lifecycle = workspace.observe(\.runningApplications, options: [.initial, .new]) { workspace, _ in
            let apps = workspace.runningApplications.filter { $0.bundleIdentifier == "dev.svc.menubar" }
            log.processes(Set(apps.map(\.processIdentifier)))
            for app in apps { log.watch(app) }
        }
        try Data().write(to: root.appendingPathComponent("monitor-ready"))
        let deadline = Date().addingTimeInterval(1200)
        var samples = 0
        var activeSamples = 0
        var seenPIDs: Set<pid_t> = []
        while !FileManager.default.fileExists(atPath: root.appendingPathComponent("monitor-stop").path) && Date() < deadline {
            let current = workspace.runningApplications.filter { $0.bundleIdentifier == "dev.svc.menubar" }
            samples += 1
            activeSamples += current.filter(\.isActive).count
            seenPIDs.formUnion(current.map(\.processIdentifier))
            RunLoop.current.run(until: Date().addingTimeInterval(0.02))
        }
        let apps = workspace.runningApplications.filter { $0.bundleIdentifier == "dev.svc.menubar" }
        let (events, notificationCount, notificationKinds) = log.snapshot()
        let report: [String: Any] = ["events": events, "notification_count": notificationCount, "notification_kinds": notificationKinds, "samples": samples, "active_samples": activeSamples, "seen_pids": seenPIDs.sorted(), "activation_events": events.filter { ($0["kind"] as? String) == "activate" }.count, "running": apps.map { ["pid": $0.processIdentifier, "active": $0.isActive, "path": $0.bundleURL?.path ?? "", "accessory": $0.activationPolicy == .accessory] }, "completed": FileManager.default.fileExists(atPath: root.appendingPathComponent("monitor-stop").path)]
        try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]).write(to: root.appendingPathComponent("installation-lifecycle.json"))
        for token in tokens { workspace.notificationCenter.removeObserver(token) }
        lifecycle.invalidate()
        log.stop()
    }
}
