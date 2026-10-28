import Foundation

actor RequestLog {
    var requests: [String] = []
    var inFlight = 0
    var maximumInFlight = 0

    func observe(_ path: String) async -> Data {
        requests.append(path)
        inFlight += 1
        maximumInFlight = max(maximumInFlight, inFlight)
        // Like CLIClient, an already-started observation finishes independently
        // of cancellation of the UI's scheduling task.
        await Task.detached { try? await Task.sleep(for: .milliseconds(350)) }.value
        inFlight -= 1
        return Data(#"{"schema_version":4,"command":"dev status","status":"ok","resources":[]}"#.utf8)
    }

    func summary() -> [String: Int] {
        ["requests": requests.count, "maximumInFlight": maximumInFlight, "inFlight": inFlight]
    }
}

@main
struct ObserveRefresh {
    @MainActor static func main() async throws {
        let files = FileManager.default
        let root = files.temporaryDirectory.appendingPathComponent("svc-refresh-\(UUID().uuidString)")
        try files.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? files.removeItem(at: root) }
        let events = root.appendingPathComponent("monitor-events")
        let cli = root.appendingPathComponent("svc")
        let payload = #"{"schema_version":1,"command":"dev monitor","pressure":{"sampled_at":"2026-10-28T00:00:00Z","sample_window_ms":250,"cpu_percent":0,"logical_cpus":1,"memory_total_bytes":1000,"memory_available_bytes":900,"memory_pressure":"normal","level":"normal","recommendation":"","issues":[]},"executions":[],"issues":[]}"#
        let script = """
        #!/bin/sh
        printf 'start\\n' >> '\(events.path)'
        /bin/sleep 0.35
        printf '%s\\n' '\(payload)'
        printf 'end\\n' >> '\(events.path)'
        """
        try script.write(to: cli, atomically: true, encoding: .utf8)
        try files.setAttributes([.posixPermissions: 0o700], ofItemAtPath: cli.path)
        let suite = "svc-refresh-\(UUID().uuidString)"
        let preferences = UserDefaults(suiteName: suite)!
        defer { preferences.removePersistentDomain(forName: suite) }
        preferences.set(["/fixture/one", "/fixture/two"], forKey: "projects")
        preferences.set(cli.path, forKey: "cliPath")
        let requests = RequestLog()
        let store = AppStore(preferences: preferences) { _, _, path, _ in await requests.observe(path) }
        var phases: [[String: Any]] = []

        func capture(_ name: String) async throws {
            let log = (try? String(contentsOf: events, encoding: .utf8)) ?? ""
            var active = 0
            var maximum = 0
            for event in log.split(separator: "\n") {
                active += event == "start" ? 1 : -1
                maximum = max(maximum, active)
            }
            var phase: [String: Any] = await requests.summary()
            phase["phase"] = name
            phase["monitorRequests"] = log.split(separator: "\n").filter { $0 == "start" }.count
            phase["maximumMonitorInFlight"] = maximum
            phase["monitorDecoded"] = store.activity.snapshot != nil
            phases.append(phase)
        }

        store.setObservationDemand(.panel, resources: true)
        store.setObservationDemand(.mainWindow, resources: true)
        try await Task.sleep(for: .seconds(1))
        try await capture("both-visible-initial")
        try await Task.sleep(for: .seconds(6))
        try await capture("both-visible-next-cycle")
        store.setObservationDemand(.panel, resources: nil)
        try await Task.sleep(for: .seconds(6))
        try await capture("main-only-still-refreshes")
        store.setObservationDemand(.mainWindow, resources: false)
        try await Task.sleep(for: .seconds(6))
        try await capture("execution-only-no-project-refresh")
        store.setObservationDemand(.mainWindow, resources: nil)
        try await Task.sleep(for: .seconds(6))
        try await capture("all-hidden-no-new-requests")
        store.setObservationDemand(.panel, resources: true)
        try await Task.sleep(for: .milliseconds(20))
        store.setObservationDemand(.panel, resources: nil)
        store.setObservationDemand(.mainWindow, resources: true)
        try await Task.sleep(for: .seconds(1))
        try await capture("rapid-hide-show-no-overlap")
        store.setObservationDemand(.mainWindow, resources: nil)
        try await Task.sleep(for: .seconds(1))
        try await capture("finished-no-in-flight-projects")
        let data = try JSONSerialization.data(withJSONObject: phases, options: [.prettyPrinted, .sortedKeys])
        print(String(decoding: data, as: UTF8.self))
    }
}
