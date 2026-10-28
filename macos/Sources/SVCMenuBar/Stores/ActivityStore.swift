import Foundation
import Observation

@MainActor @Observable
final class ActivityStore {
    private(set) var snapshot: ActivitySnapshot?
    private(set) var error: String?
    private(set) var checkedAt: Date?
    private(set) var refreshing = false
    private(set) var pending: Set<String> = []
    private(set) var notice: String?
    @ObservationIgnored var projectRoots: [String] = []
    @ObservationIgnored private var generation = UUID()
    @ObservationIgnored private var selectedConfiguration: CLIConfiguration?

    func refresh(_ configuration: CLIConfiguration) async {
        if selectedConfiguration != configuration {
            generation = UUID()
            selectedConfiguration = configuration
            snapshot = nil
            checkedAt = nil
            error = nil
            refreshing = false
        }
        guard !refreshing else { return }
        let requestGeneration = generation
        refreshing = true
        defer { if generation == requestGeneration { refreshing = false } }
        do {
            let data = try await CLIClient(configuration: configuration).requestGlobal(.monitor, arguments: projectRoots.flatMap { ["--project-root", $0] })
            let incoming = try CLIResponse.decode(ActivitySnapshot.self, data: data, command: .monitor)
            guard generation == requestGeneration else { return }
            snapshot = incoming
            checkedAt = Date()
            error = nil
        } catch {
            guard generation == requestGeneration else { return }
            self.error = error.localizedDescription
        }
    }

    func terminate(_ execution: ExecutionActivity, force: Bool, configuration: CLIConfiguration) {
        guard execution.canTerminate, !pending.contains(execution.id) else { return }
        pending.insert(execution.id)
        Task {
            defer { pending.remove(execution.id) }
            do {
                let arguments = [execution.id, "--by", "human"] + (force ? ["--force"] : [])
                let data = try await CLIClient(configuration: configuration).requestGlobal(.terminate, arguments: arguments)
                let receipt = try CLIResponse.decode(TerminationReceipt.self, data: data, command: .terminate)
                guard receipt.executionId == execution.id else {
                    throw CLIError(message: "CLI 返回了其他执行的终止回执。")
                }
                notice = receipt.message
            } catch {
                notice = error.localizedDescription
            }
            await refresh(configuration)
        }
    }

    func terminateExternal(_ execution: HarnessExecution, configuration: CLIConfiguration) {
        guard execution.canTerminate, !pending.contains(execution.id) else { return }
        pending.insert(execution.id)
        Task {
            defer { pending.remove(execution.id) }
            do {
                let data = try await CLIClient(configuration: configuration).requestGlobal(.terminate,
                    arguments: [execution.id, "--by", "human"])
                let receipt = try CLIResponse.decode(TerminationReceipt.self, data: data, command: .terminate)
                guard receipt.executionId == execution.id else { throw CLIError(message: "停止回执属于其他执行。") }
                notice = receipt.message
            } catch { notice = error.localizedDescription }
            await refresh(configuration)
        }
    }

    func report(_ message: String) { notice = message }

    func dismissNotice() { notice = nil }
}
