import Foundation
import Observation

struct ActiveOperation {
    let command: DevCommand
    let projectPath: String
}

struct ProjectState: Identifiable {
    let path: String
    var snapshot: DevCatalog?
    var checkedAt: Date?
    var error: String?
    var id: String { path }
    var name: String { URL(fileURLWithPath: path).lastPathComponent }
}

@MainActor @Observable
final class AppStore {
    let activity = ActivityStore()
    typealias Request = @Sendable (CLIConfiguration, DevCommand, String, [String]) async throws -> Data
    private(set) var projects: [ProjectState]
    private(set) var organization = ProjectOrganization()
    private(set) var sectionStorageError: String?
    private(set) var projectReveal: ProjectReveal?
    private(set) var configuration: CLIConfiguration
    private(set) var operations: [String: ActiveOperation] = [:]
    private(set) var receipts: [String: OperationReceipt] = [:]
    private(set) var refreshes: [String: UUID] = [:]
    private(set) var quitPending = false
    var panelVisible = false
    var notice: String?
    @ObservationIgnored private let preferences: UserDefaults
    @ObservationIgnored private let request: Request
    @ObservationIgnored private var quitCompletion: ((Bool) -> Void)?

    init(preferences: UserDefaults = .standard, request: @escaping Request = { config, command, repo, arguments in
        try await CLIClient(configuration: config).request(command, repo: repo, arguments: arguments)
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
        if let stored = preferences.object(forKey: "projectSections") {
            do {
                guard let data = stored as? Data else { throw CocoaError(.coderReadCorrupt) }
                let decoded = try JSONDecoder().decode(ProjectOrganization.self, from: data)
                guard decoded.isValid else { throw CocoaError(.coderReadCorrupt) }
                organization = decoded
                let known = Set(projects.map(\.path))
                organization.assignments = organization.assignments.filter { known.contains($0.key) }
            } catch {
                sectionStorageError = "无法读取 Section 设置，原设置已保留；项目暂按未分组显示。"
            }
        }
    }

    var resourceCount: Int { projects.flatMap { $0.snapshot?.resources ?? [] }.count }

    func addProject(_ url: URL, sectionID: UUID? = nil) {
        guard !quitPending else { return }
        let path = url.resolvingSymlinksInPath().standardizedFileURL.path
        guard !projects.contains(where: { $0.path == path }) else {
            revealProject(path)
            notice = "项目已存在：\(path)"
            return
        }
        if let sectionID, !organization.sections.contains(where: { $0.id == sectionID }) { return }
        projects.append(ProjectState(path: path))
        persistProjects()
        if let sectionID { moveProject(path, to: sectionID) }
        Task { await refresh(path) }
    }

    func removeProject(_ path: String) {
        guard operations.isEmpty, !quitPending else { return }
        refreshes[path] = nil
        projects.removeAll { $0.path == path }
        persistProjects()
        if sectionStorageError == nil, organization.assignments.removeValue(forKey: path) != nil { persistOrganization() }
    }

    var canEditSections: Bool { !quitPending && sectionStorageError == nil }

    func projects(in sectionID: UUID?) -> [ProjectState] {
        projects.filter { organization.assignments[$0.path] == sectionID }
    }

    @discardableResult func createSection(_ name: String) -> UUID? {
        guard canEditSections, let name = sectionName(name, excluding: nil) else { return nil }
        let section = ProjectSection(id: UUID(), name: name)
        organization.sections.append(section)
        persistOrganization()
        return section.id
    }

    @discardableResult func renameSection(_ id: UUID, to name: String) -> Bool {
        guard canEditSections, let index = organization.sections.firstIndex(where: { $0.id == id }),
              let name = sectionName(name, excluding: id) else { return false }
        organization.sections[index].name = name
        persistOrganization()
        return true
    }

    func moveSection(_ id: UUID, offset: Int) {
        guard canEditSections, offset == -1 || offset == 1,
              let index = organization.sections.firstIndex(where: { $0.id == id }),
              organization.sections.indices.contains(index + offset) else { return }
        organization.sections.swapAt(index, index + offset)
        persistOrganization()
    }

    func deleteSection(_ id: UUID) {
        guard canEditSections else { return }
        organization.sections.removeAll { $0.id == id }
        organization.assignments = organization.assignments.filter { $0.value != id }
        persistOrganization()
    }

    func moveProject(_ path: String, to sectionID: UUID?) {
        guard canEditSections, projects.contains(where: { $0.path == path }),
              sectionID == nil || organization.sections.contains(where: { $0.id == sectionID }) else { return }
        organization.assignments[path] = sectionID
        persistOrganization()
    }

    func toggleSection(_ id: UUID) {
        guard canEditSections, let index = organization.sections.firstIndex(where: { $0.id == id }) else { return }
        organization.sections[index].collapsed.toggle()
        persistOrganization()
    }

    func revealProject(_ path: String) {
        if let id = organization.assignments[path],
           let index = organization.sections.firstIndex(where: { $0.id == id }),
           organization.sections[index].collapsed, canEditSections {
            organization.sections[index].collapsed = false
            persistOrganization()
        }
        projectReveal = ProjectReveal(path: path)
    }

    func sectionActivity(_ id: UUID) -> (running: Bool, attention: Bool) {
        let members = projects(in: id)
        let paths = Set(members.map(\.path))
        let resources = members.flatMap { $0.snapshot?.resources ?? [] }
        let running = operations.values.contains { paths.contains($0.projectPath) } || resources.contains { resource in
            resource.coordination.map { operations[$0.coordinationId] != nil } ?? false
        }
        let attention = members.contains { $0.error != nil }
            || resources.contains { $0.needsReconciliation || $0.error != nil }
            || receipts.values.contains { receipt in
                paths.contains(receipt.projectPath)
                    && (receipt.result.map { ["failed", "condition-unmet", "owner-lost", "stale", "interrupted", "absent"].contains($0.status) } ?? true)
            }
        return (running, attention)
    }

    private func sectionName(_ value: String, excluding id: UUID?) -> String? {
        let name = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !name.isEmpty else { notice = "请输入 Section 名称。"; return nil }
        guard !organization.sections.contains(where: { $0.id != id && $0.name.lowercased() == name.lowercased() }) else {
            notice = "已有同名 Section。"
            return nil
        }
        return name
    }

    private func persistOrganization() {
        do { preferences.set(try JSONEncoder().encode(organization), forKey: "projectSections") }
        catch { sectionStorageError = "无法保存 Section 设置：\(error.localizedDescription)" }
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
        for path in projects.map(\.path) {
            guard !Task.isCancelled, !quitPending else { break }
            await refresh(path)
        }
    }

    func refresh(_ path: String, resource: String? = nil, observation: String? = nil) async {
        guard !quitPending, refreshes[path] == nil,
              projects.contains(where: { $0.path == path }) else { return }
        let generation = UUID()
        refreshes[path] = generation
        do {
            let arguments = (resource.map { [$0] } ?? []) + (observation.map { ["--observation", $0] } ?? [])
            let data = try await request(configuration, .status, path, arguments)
            let snapshot = try CLIResponse.decode(DevCatalog.self, data: data, command: .status)
            guard refreshes[path] == generation,
                  let index = projects.firstIndex(where: { $0.path == path }) else { return }
            let previous = projects[index].snapshot?.resources ?? []
            let merged = snapshot.resources.map { incoming in
                var entry = incoming
                if let old = previous.first(where: { $0.entryId == incoming.entryId && $0.declarationDigest == incoming.declarationDigest }) {
                    let refreshed = Set(incoming.observations.map(\.key))
                    let retained = old.observations.filter { item in
                        !refreshed.contains(item.key) && incoming.facets.contains { $0.key == item.key && (observation != nil || !$0.automatic) }
                    }
                    entry.observations += retained
                }
                return entry
            }
            projects[index].snapshot = DevCatalog(status: snapshot.status, resources:
                resource == nil ? merged : previous.map { old in merged.first(where: { $0.entryId == old.entryId }) ?? old })
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

    func perform(_ action: ResourceAction, resource: DevResource, project: String) {
        guard resource.actions.contains(where: { $0.key == action.key }),
              !resource.needsReconciliation else { return }
        execute(.act, resource: resource, project: project, action: action.key,
                arguments: [resource.resource, action.key, "--expected-digest", resource.declarationDigest])
    }

    func reconcile(_ resource: DevResource, project: String) {
        guard resource.needsReconciliation, let id = resource.execution?.executionId else { return }
        execute(.reconcile, resource: resource, project: project, action: "确认未知结果",
                arguments: [resource.resource, "--execution", id, "--acknowledge-unknown"])
    }

    private func execute(_ command: DevCommand, resource: DevResource, project: String,
                         action: String, arguments: [String]) {
        guard !quitPending, let id = resource.coordination?.coordinationId,
              operations[id] == nil, projects.contains(where: { $0.path == project }) else { return }
        operations[id] = ActiveOperation(command: command, projectPath: project)
        invalidateRefreshes()
        let config = configuration
        Task {
            let receipt: OperationReceipt
            do {
                let data = try await request(config, command, project, arguments)
                let result = try CLIResponse.decode(DevResult.self, data: data, command: command)
                guard result.entryId == resource.entryId,
                      result.resource == resource.resource,
                      result.action == (command == .reconcile ? "reconcile" : action) else {
                    throw CLIError(message: "CLI 返回了其他入口或动作的结果。")
                }
                receipt = OperationReceipt(projectPath: project, entryId: resource.entryId,
                    resource: resource.resource, action: action, message: result.message,
                    date: Date(), logPath: result.execution?.logPath, result: result)
            } catch {
                receipt = OperationReceipt(projectPath: project, entryId: resource.entryId,
                    resource: resource.resource, action: action, message: error.localizedDescription,
                    date: Date(), logPath: nil, result: nil)
            }
            receipts[resource.entryId] = receipt
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
        let visible = Set((project.snapshot?.resources ?? []).map { $0.entryId })
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
