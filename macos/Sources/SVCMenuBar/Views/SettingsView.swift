import AppKit
import SwiftUI

struct SettingsView: View {
    let store: AppStore
    @State private var cliPath = ""
    @State private var searchPath = ""
    @State private var saved = false
    @State private var environmentMode = ExecutionEnvironmentMode.projectShell
    var body: some View {
        VStack(spacing: 0) {
            Form {
                NotificationSettingsView()
                Section("SVC CLI") {
                    HStack {
                        TextField("自动查找 svc（也可填写绝对路径）", text: $cliPath).textFieldStyle(.roundedBorder)
                        Button(action: chooseCLI) { Image(systemName: "folder").frame(width: 26, height: 26) }
                            .buttonStyle(.borderless)
                            .help("选择 svc 可执行文件").accessibilityLabel("选择 svc 可执行文件")
                    }
                    if store.configuration.executable.isEmpty && store.configuration.environmentMode == .projectShell {
                        Text("自动使用项目终端环境中的 svc").font(.caption).foregroundStyle(.secondary)
                    } else if let executable = store.configuration.resolvedExecutable {
                        Text(executable).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                    } else {
                        Label("未找到 SVC CLI", systemImage: "exclamationmark.triangle")
                            .foregroundStyle(.orange)
                    }
                    CLIInstallLinks()
                    Button("使用系统 CLI 并重新检测") {
                        cliPath = ""
                        store.setConfiguration(.init(executable: "", searchPath: searchPath, environmentMode: environmentMode))
                        saved = true
                    }
                    .disabled(!canSave)
                    Picker("执行环境", selection: $environmentMode) {
                        Text("项目终端环境").tag(ExecutionEnvironmentMode.projectShell)
                        Text("自定义 PATH").tag(ExecutionEnvironmentMode.fixedPath)
                    }
                    if environmentMode == .fixedPath {
                        TextField("命令搜索路径 PATH", text: $searchPath, axis: .vertical).lineLimit(3...5)
                    }
                    Text(environmentMode == .projectShell
                         ? "首次使用项目时读取登录 shell 配置并进入项目目录，复用本次运行的环境。支持 zsh、bash；启动脚本和项目目录钩子可能执行代码。刷新会重新准备，项目显式环境配置仍优先。"
                         : "保留已有 PATH 配置；项目命令使用此 PATH，其他环境继承 App。")
                        .font(.caption).foregroundStyle(.secondary)
                }
                IntegrationSettingsView(store: store)
            }.formStyle(.grouped)
            Divider()
            HStack {
                Text("版本 \(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "—")（\(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "—")）").font(.caption).foregroundStyle(.secondary)
                Spacer()
                if saved { Label("已保存", systemImage: "checkmark.circle").foregroundStyle(.green) }
                Button("保存并刷新") {
                    store.setConfiguration(CLIConfiguration(
                        executable: cliPath.trimmingCharacters(in: .whitespacesAndNewlines),
                        searchPath: searchPath.trimmingCharacters(in: .whitespacesAndNewlines),
                        environmentMode: environmentMode
                    ))
                    saved = true
                }
                .buttonStyle(.borderedProminent).keyboardShortcut(.defaultAction)
                .disabled(!canSave)
            }.padding(12)
        }.frame(width: 560, height: 640)
        .onAppear {
            cliPath = store.configuration.executable
            searchPath = store.configuration.searchPath
            environmentMode = store.configuration.environmentMode
        }
        .onChange(of: cliPath) { saved = false }
        .onChange(of: searchPath) { saved = false }
        .onChange(of: environmentMode) { saved = false }
    }

    private var canSave: Bool {
        let hasPath = !searchPath.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        return (environmentMode == .projectShell || hasPath) && store.operations.isEmpty && !store.quitPending
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
