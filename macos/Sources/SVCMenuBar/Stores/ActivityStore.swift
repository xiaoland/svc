import Foundation
import Observation

@MainActor @Observable
final class ActivityStore {
    private(set) var snapshot: ActivitySnapshot?
    private(set) var error: String?
    private(set) var cliUnavailable = false
    private(set) var checkedAt: Date?
    private(set) var refreshing = false
    private(set) var notice: String?
    @ObservationIgnored var projectRoots: [String] = []
    @ObservationIgnored private var generation = UUID()
    @ObservationIgnored private let request: AppStore.Request

    init(request: @escaping AppStore.Request = AppStore.cliRequest) {
        self.request = request
    }

    func invalidate() {
        generation = UUID()
        snapshot = nil
        checkedAt = nil
        error = nil
        cliUnavailable = false
        notice = nil
        refreshing = false
    }

    func refresh(_ configuration: CLIConfiguration) async {
        guard !refreshing else { return }
        let requestGeneration = generation
        refreshing = true
        defer { if generation == requestGeneration { refreshing = false } }
        do {
            let data = try await request(configuration, .monitor, nil, projectRoots.flatMap { ["--project-root", $0] })
            let incoming = try CLIResponse.decode(ActivitySnapshot.self, data: data, command: .monitor)
            guard generation == requestGeneration else { return }
            snapshot = incoming
            checkedAt = Date()
            error = nil
            cliUnavailable = false
        } catch {
            guard generation == requestGeneration else { return }
            self.error = error.localizedDescription
            cliUnavailable = (error as? CLIError)?.reason == .executableMissing
        }
    }

    func report(_ message: String) { notice = message }

    func dismissNotice() { notice = nil }
}
