import Foundation

@main
struct ObserveClient {
    @MainActor static func main() async throws {
        let arguments = CommandLine.arguments
        let configuration = CLIConfiguration(executable: arguments[1], searchPath: ProcessInfo.processInfo.environment["PATH"] ?? "/usr/bin:/bin")
        let fixture = URL(fileURLWithPath: arguments[2])
        let replay = try CLIResponse.decode(ActivitySnapshot.self, data: Data(contentsOf: fixture), command: .monitor)
        var result: [String: Any] = [
            "decodedProjects": replay.projects?.map { $0.projectPath ?? "unassigned" } ?? [],
            "decodedResources": replay.resources?.count ?? 0,
            "decodedExecutions": replay.executions.count,
            "footprints": replay.projects?.compactMap { $0.usage?.memoryFootprintBytes } ?? [],
            "writeRates": replay.projects?.compactMap { $0.usage?.diskWriteBytesPerSecond } ?? [],
            "foundationOnly": true,
        ]
        result["swapUsed"] = replay.pressure.swapUsedBytes
        let activity = ActivityStore()
        await activity.refresh(configuration)
        guard activity.snapshot != nil else { throw CLIError(message: activity.error ?? "缺少实际 CLI 快照") }
        result["actualMonitorDecoded"] = true
        if arguments.count > 3 && arguments[3] == "--register" {
            let preferences = UserDefaults(suiteName: "dev.svc.menubar")!
            let beforePaths = preferences.stringArray(forKey: "projects") ?? []
            let beforeCLI = preferences.string(forKey: "cliPath")
            let beforePATH = preferences.string(forKey: "searchPath")
            let store = AppStore(preferences: preferences) { _, command, repo, args in
                try await CLIClient(configuration: configuration).request(command, repo: repo, arguments: args)
            }
            let beforeSections = store.organization.sections.map { ($0.id, $0.name, $0.collapsed) }
            let beforeAssignments = store.organization.assignments
            let sectionID = store.organization.sections.first { $0.name == "验收" }?.id ?? store.createSection("验收")
            guard let sectionID else { throw CLIError(message: "无法创建验收 Section") }
            let projects = ["/Volumes/WorkSSD/Development/svc-dev-lab", "/Volumes/WorkSSD/Development/svc-dev-lab-peer"]
            for path in projects {
                store.addProject(URL(fileURLWithPath: path), sectionID: sectionID)
                for _ in 0..<50 {
                    if store.projects.first(where: { $0.path == path })?.checkedAt != nil { break }
                    try await Task.sleep(for: .milliseconds(100))
                }
            }
            preferences.synchronize()
            result["registeredProjects"] = projects.filter { path in store.projects.contains { $0.path == path } }
            result["section"] = sectionID.uuidString
            result["originalProjectsPreserved"] = beforePaths.allSatisfy { path in store.projects.contains { $0.path == path } }
            result["originalSectionsPreserved"] = beforeSections.allSatisfy { old in
                store.organization.sections.contains { $0.id == old.0 && $0.name == old.1 && $0.collapsed == old.2 }
            }
            result["originalAssignmentsPreserved"] = beforeAssignments.allSatisfy { store.organization.assignments[$0.key] == $0.value }
            result["cliPreferencesPreserved"] = beforeCLI == preferences.string(forKey: "cliPath") && beforePATH == preferences.string(forKey: "searchPath")
        } else if arguments.count > 4 && arguments[3] == "--terminate" {
            let id = arguments[4]
            let roots = Set(["/Volumes/WorkSSD/Development/svc-dev-lab", "/Volumes/WorkSSD/Development/svc-dev-lab-peer"])
            guard let execution = activity.snapshot?.executions.first(where: { $0.id == id && $0.canTerminate }),
                  execution.projectPath.map({ roots.contains($0) }) == true else {
                throw CLIError(message: "只能终止本轮验收项目的已知执行")
            }
            activity.terminate(execution, force: false, configuration: configuration)
            for _ in 0..<10 {
                try await Task.sleep(for: .milliseconds(250))
                await activity.refresh(configuration)
                if let final = activity.snapshot?.executions.first(where: { $0.id == id }), !final.active {
                    result["terminatedState"] = final.state
                    result["groupState"] = final.groupState
                    result["projectAfterTermination"] = final.projectPath
                    result["canTerminateAfterExit"] = final.canTerminate
                    break
                }
            }
        }
        let data = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
        print(String(decoding: data, as: UTF8.self))
    }
}
