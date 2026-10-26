import Foundation
import Observation

struct ProjectState: Identifiable {
    let path: String
    var snapshot: DevStatus?
    var checkedAt: Date?
    var error: String?
    var id: String { path }
    var name: String { URL(fileURLWithPath: path).lastPathComponent }
}

@MainActor @Observable
final class AppStore {
    typealias Request = @Sendable (CLIConfiguration, DevCommand, String, String?) async throws -> Data
    private(set) var projects: [ProjectState]
    private(set) var configuration: CLIConfiguration
    private(set) var operations: [String: DevCommand] = [:]
    private(set) var receipts: [String: OperationReceipt] = [:]
    private(set) var refreshes: [String: UUID] = [:]
    private(set) var quitPending = false
    var panelVisible = false
    var notice: String?
    @ObservationIgnored private let preferences: UserDefaults
    @ObservationIgnored private let request: Request
    @ObservationIgnored private var quitCompletion: ((Bool) -> Void)?

    init(preferences: UserDefaults = .standard, request: @escaping Request = { config, command, repo, target in
        try await CLIClient(configuration: config).request(command, repo: repo, target: target)
    }) {
        self.preferences = preferences
        self.request = request
        projects = (preferences.stringArray(forKey: "projects") ?? []).map { ProjectState(path: $0) }
        let defaultCLI = Bundle.main.object(forInfoDictionaryKey: "SVCDefaultCLIPath") as? String ?? ""
        let defaultPath = Bundle.main.object(forInfoDictionaryKey: "SVCDefaultSearchPath") as? String
            ?? "\(NSHomeDirectory())/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        configuration = CLIConfiguration(
            executable: preferences.string(forKey: "cliPath") ?? defaultCLI,
            searchPath: preferences.string(forKey: "searchPath") ?? defaultPath
        )
    }

    var readyCount: Int {
        projects.flatMap { $0.snapshot?.targets ?? [] }.filter { $0.health == .ready }.count
    }
    var targetCount: Int { projects.flatMap { $0.snapshot?.targets ?? [] }.count }

    func addProject(_ url: URL) {
        guard !quitPending else { return }
        let path = url.resolvingSymlinksInPath().standardizedFileURL.path
        guard !projects.contains(where: { $0.path == path }) else { return }
        projects.append(ProjectState(path: path))
        persistProjects()
        Task { await refresh(path) }
    }

    func removeProject(_ path: String) {
        guard operations.isEmpty, !quitPending else { return }
        refreshes[path] = nil
        projects.removeAll { $0.path == path }
        persistProjects()
    }

    func setConfiguration(_ value: CLIConfiguration) {
        guard operations.isEmpty, !quitPending else { return }
        configuration = value
        preferences.set(value.executable, forKey: "cliPath")
        preferences.set(value.searchPath, forKey: "searchPath")
        refreshes.removeAll()
        for index in projects.indices {
            projects[index].snapshot = nil
            projects[index].checkedAt = nil
            projects[index].error = nil
        }
        Task { await refreshAll() }
    }

    func refreshAll() async {
        guard !quitPending else { return }
        await withTaskGroup(of: Void.self) { group in
            for path in projects.map(\.path) {
                group.addTask { await self.refresh(path) }
            }
        }
    }

    func refresh(_ path: String) async {
        guard !quitPending, refreshes[path] == nil,
              projects.contains(where: { $0.path == path }) else { return }
        let generation = UUID()
        refreshes[path] = generation
        do {
            let data = try await request(configuration, .status, path, nil)
            let snapshot = try CLIResponse.decode(DevStatus.self, data: data, command: .status)
            guard refreshes[path] == generation,
                  let index = projects.firstIndex(where: { $0.path == path }) else { return }
            projects[index].snapshot = snapshot
            projects[index].error = nil
            projects[index].checkedAt = Date()
        } catch {
            guard refreshes[path] == generation,
                  let index = projects.firstIndex(where: { $0.path == path }) else { return }
            projects[index].snapshot = nil
            projects[index].checkedAt = Date()
            projects[index].error = error.localizedDescription
        }
        if refreshes[path] == generation { refreshes[path] = nil }
    }

    func perform(_ command: DevCommand, target: DevTarget, project: String) {
        guard !quitPending, let id = target.capability?.capabilityId, operations[id] == nil,
              projects.contains(where: { $0.path == project }),
              (command == .ensure && target.canStart) || (command == .stop && target.canStop) else { return }
        operations[id] = command
        invalidateRefreshes()
        let config = configuration
        Task {
            let receipt: OperationReceipt
            do {
                let data = try await request(config, command, project, target.target)
                let result = try CLIResponse.decode(DevResult.self, data: data, command: command)
                receipt = OperationReceipt(
                    projectPath: project, target: target.target, command: command,
                    message: result.message(for: command) + (result.probeError.map { "\n\($0.message)" } ?? ""),
                    date: Date(), logPath: result.attempt?.logs.merged.path
                )
            } catch {
                receipt = OperationReceipt(projectPath: project, target: target.target,
                                           command: command, message: error.localizedDescription,
                                           date: Date(), logPath: nil)
            }
            receipts[id] = receipt
            operations[id] = nil
            invalidateRefreshes()
            if quitPending && operations.isEmpty {
                quitCompletion?(true)
                quitCompletion = nil
            } else {
                await refreshAll()
            }
        }
    }

    func unavailableReceipts(for project: ProjectState) -> [OperationReceipt] {
        let visible = Set((project.snapshot?.targets ?? []).compactMap { $0.capability?.capabilityId })
        return receipts.filter { $0.value.projectPath == project.path && !visible.contains($0.key) }
            .map(\.value).sorted { $0.date > $1.date }
    }

    func waitToQuit(completion: @escaping (Bool) -> Void) {
        quitPending = true
        quitCompletion = completion
        invalidateRefreshes()
    }

    func cancelQuit() {
        quitPending = false
        quitCompletion?(false)
        quitCompletion = nil
        Task { await refreshAll() }
    }

    private func invalidateRefreshes() {
        // Responses started before a mutation must never overwrite its newer observation.
        refreshes.removeAll()
    }

    private func persistProjects() { preferences.set(projects.map(\.path), forKey: "projects") }
}
