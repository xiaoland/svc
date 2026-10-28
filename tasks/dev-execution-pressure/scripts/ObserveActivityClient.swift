import Foundation

/// A Foundation-only observation of the actual App client and store; no UI host.
@main
struct ObserveActivityClient {
    @MainActor static func main() async throws {
        let arguments = CommandLine.arguments
        let configuration = CLIConfiguration(executable: arguments[1], searchPath: ProcessInfo.processInfo.environment["PATH"] ?? "/usr/bin:/bin")
        let store = ActivityStore()
        await store.refresh(configuration)
        guard let snapshot = store.snapshot else {
            throw CLIError(message: store.error ?? "缺少机器快照")
        }
        var result: [String: Any] = [
            "decoded": true,
            "sampleWindowMs": snapshot.pressure.sampleWindowMs,
            "pressure": snapshot.pressure.level,
            "executionCount": snapshot.executions.count,
            "foundationOnly": true
        ]
        if arguments.count > 2 {
            let id = arguments[2]
            guard let execution = snapshot.executions.first(where: { $0.id == id && $0.canTerminate }) else {
                throw CLIError(message: "未找到可控执行")
            }
            store.terminate(execution, force: false, configuration: configuration)
            while store.pending.contains(id) { try await Task.sleep(for: .milliseconds(50)) }
            for _ in 0..<6 {
                await store.refresh(configuration)
                if let final = store.snapshot?.executions.first(where: { $0.id == id }), !final.active {
                    result["terminatedState"] = final.state
                    result["groupState"] = final.groupState
                    result["canTerminateAfterExit"] = final.canTerminate
                    break
                }
                try await Task.sleep(for: .milliseconds(500))
            }
            result["notice"] = store.notice
        }
        let data = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
        print(String(decoding: data, as: UTF8.self))
    }
}
