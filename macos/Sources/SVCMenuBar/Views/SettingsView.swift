import AppKit
import SwiftUI

struct SettingsView: View {
    let store: AppStore
    @State private var cliPath = ""
    @State private var searchPath = ""
    @State private var saved = false
    var body: some View {
        Form {
            Section("SVC") {
                Text("版本 \(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "—")（\(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "—")）")
            }
            Section("SVC CLI") {
                HStack {
                    TextField("自动查找 svc（也可填写绝对路径）", text: $cliPath).textFieldStyle(.roundedBorder)
                    Button(action: chooseCLI) { Image(systemName: "folder").frame(width: 26, height: 26) }
                        .buttonStyle(.borderless)
                        .help("选择 svc 可执行文件").accessibilityLabel("选择 svc 可执行文件")
                }
                if let executable = store.configuration.resolvedExecutable {
                    Text(executable).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                } else {
                    Label("未找到 SVC CLI", systemImage: "exclamationmark.triangle")
                        .foregroundStyle(.orange)
                }
                CLIInstallLinks()
                Button("使用系统 CLI 并重新检测") {
                    cliPath = ""
                    store.setConfiguration(.init(executable: "", searchPath: searchPath))
                    saved = true
                }
                .disabled(searchPath.isEmpty || !store.operations.isEmpty || store.quitPending)
                TextField("命令搜索路径 PATH", text: $searchPath, axis: .vertical).lineLimit(3...5)
                Text("项目命令使用此 PATH；需要的环境变量由项目配置声明。")
                    .font(.caption).foregroundStyle(.secondary)
            }
            HStack {
                if saved { Label("已保存", systemImage: "checkmark.circle").foregroundStyle(.green) }
                Spacer()
                Button("保存并刷新") {
                    store.setConfiguration(CLIConfiguration(
                        executable: cliPath.trimmingCharacters(in: .whitespacesAndNewlines),
                        searchPath: searchPath.trimmingCharacters(in: .whitespacesAndNewlines)
                    ))
                    saved = true
                }
                .buttonStyle(.borderedProminent).keyboardShortcut(.defaultAction)
                .disabled(searchPath.isEmpty || !store.operations.isEmpty || store.quitPending)
            }
        }
        .formStyle(.grouped).frame(width: 560)
        .onAppear {
            cliPath = store.configuration.executable
            searchPath = store.configuration.searchPath
        }
        .onChange(of: cliPath) { saved = false }
        .onChange(of: searchPath) { saved = false }
    }

    private func chooseCLI() {
        let panel = NSOpenPanel()
        panel.title = "选择 svc 可执行文件"
        panel.prompt = "选择"
        panel.canChooseDirectories = false
        panel.showsHiddenFiles = true
        panel.begin { response in
            if response == .OK, let url = panel.url { cliPath = url.path }
        }
    }
}
