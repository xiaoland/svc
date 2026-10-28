import SwiftUI

struct IntegrationSettingsView: View {
    let store: AppStore
    @State private var socketPath = ""
    @State private var configuring = false

    var body: some View {
        Section("执行来源") {
            ForEach(Array((store.activity.snapshot?.integrations ?? []).enumerated()), id: \.offset) { _, source in
                HStack {
                    Text(source.name)
                    Spacer()
                    Text(source.stateLabel).foregroundStyle(.secondary).help(source.message)
                    if source.provider == "pi" {
                        Button("接入") { setup("pi") }.disabled(configuring)
                    }
                }
                if source.provider == "codex" && source.state != "connected" {
                    HStack {
                        TextField("共享控制 socket 的绝对路径", text: $socketPath).textFieldStyle(.roundedBorder)
                        Button("连接") { setup("codex", arguments: ["--socket", socketPath]) }
                            .disabled(configuring || !socketPath.hasPrefix("/"))
                    }
                }
            }
            if store.activity.snapshot == nil {
                ProgressView().controlSize(.small)
            }
            if let notice = store.activity.notice {
                Text(notice).font(.caption).textSelection(.enabled)
            }
        }
        .task { await store.activity.refresh(store.configuration) }
    }

    private func setup(_ provider: String, arguments: [String] = []) {
        configuring = true
        Task {
            defer { configuring = false }
            do {
                let data = try await CLIClient(configuration: store.configuration).requestGlobal(.integrate, arguments: [provider] + arguments)
                let result = try CLIResponse.decode(IntegrationSetupResponse.self, data: data, command: .integrate)
                guard result.provider == provider else { throw CLIError(message: "CLI 返回了其他来源的配置结果。") }
                store.activity.report(result.message)
            } catch { store.activity.report(error.localizedDescription) }
            await store.activity.refresh(store.configuration)
        }
    }
}
