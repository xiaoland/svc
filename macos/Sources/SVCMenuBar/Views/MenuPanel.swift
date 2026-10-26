import AppKit
import SwiftUI

struct MenuPanel: View {
    @Bindable var store: AppStore
    let openSettings: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                Image(systemName: "server.rack").font(.title2).foregroundStyle(.tint)
                VStack(alignment: .leading, spacing: 2) {
                    Text("开发服务器").font(.headline)
                    Text("\(store.readyCount) / \(store.targetCount) 就绪")
                        .font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Button { Task { await store.refreshAll() } } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .help("刷新服务状态").accessibilityLabel("刷新服务状态")
                .keyboardShortcut("r").disabled(store.quitPending || !store.refreshes.isEmpty)
                Button(action: addProject) { Image(systemName: "plus") }
                    .help("添加项目").accessibilityLabel("添加项目").keyboardShortcut("o")
                    .disabled(store.quitPending)
            }
            .buttonStyle(.borderless).padding(18)
            Divider()
            if store.projects.isEmpty {
                VStack(spacing: 16) {
                    Image(systemName: "folder.badge.plus").font(.system(size: 36)).foregroundStyle(.secondary)
                    Text("添加开发项目").font(.headline)
                    Button("选择项目文件夹…", action: addProject).buttonStyle(.borderedProminent)
                }.frame(maxWidth: .infinity).padding(.vertical, 42)
            } else {
                ViewThatFits(in: .vertical) {
                    projectList.fixedSize(horizontal: false, vertical: true)
                    ScrollView { projectList }
                }.frame(maxHeight: 480)
            }
            if store.quitPending {
                HStack {
                    ProgressView().controlSize(.small)
                    Text("操作结束后退出").font(.caption)
                    Spacer()
                    Button("取消退出") { store.cancelQuit() }
                }.padding(12)
            }
            if let notice = store.notice {
                HStack(alignment: .top) {
                    Text(notice).font(.caption).textSelection(.enabled)
                    Spacer()
                    Button { store.notice = nil } label: { Image(systemName: "xmark") }
                        .buttonStyle(.borderless).accessibilityLabel("关闭提示")
                }.padding(12)
            }
            Divider()
            HStack {
                Button {
                    NSApp.activate(ignoringOtherApps: true)
                    openSettings()
                } label: { Label("设置", systemImage: "gearshape") }
                .keyboardShortcut(",")
                Spacer()
                Button("退出 SVC") { NSApp.terminate(nil) }
                    .keyboardShortcut("q").disabled(store.quitPending)
            }.buttonStyle(.borderless).font(.callout).padding(14)
        }
        .frame(width: 420)
        .task(id: store.panelVisible) {
            guard store.panelVisible else { return }
            while !Task.isCancelled && store.panelVisible {
                await store.refreshAll()
                do { try await Task.sleep(for: .seconds(5)) } catch { break }
            }
        }
    }

    private var projectList: some View {
        VStack(alignment: .leading, spacing: 20) {
            ForEach(store.projects) { project in
                ProjectSection(project: project, store: store)
            }
        }.padding(16)
    }

    private func addProject() {
        let panel = NSOpenPanel()
        panel.title = "添加 SVC 项目"
        panel.prompt = "添加项目"
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = true
        NSApp.activate(ignoringOtherApps: true)
        panel.begin { response in
            if response == .OK { for url in panel.urls { store.addProject(url) } }
        }
    }
}

private struct ProjectSection: View {
    let project: ProjectState
    let store: AppStore
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Image(systemName: "folder").foregroundStyle(.secondary)
                Text(project.name).font(.headline).lineLimit(1).help(project.path)
                Spacer()
                if store.refreshes[project.path] != nil { ProgressView().controlSize(.mini) }
                Menu {
                    Text(project.path)
                    Button("在 Finder 中显示") { NSWorkspace.shared.selectFile(nil, inFileViewerRootedAtPath: project.path) }
                    Button("移除项目", role: .destructive) { store.removeProject(project.path) }
                        .disabled(!store.operations.isEmpty || store.quitPending)
                } label: { Image(systemName: "ellipsis") }
                .menuStyle(.borderlessButton).menuIndicator(.hidden).fixedSize().accessibilityLabel("\(project.name) 项目操作")
            }
            // Show the path to distinguish worktrees with identical directory names.
            Text(project.path).font(.caption).foregroundStyle(.secondary).lineLimit(1).truncationMode(.middle)
            if let error = project.error {
                Label("状态未知", systemImage: "exclamationmark.triangle").foregroundStyle(.orange)
                Text(error).font(.caption).textSelection(.enabled)
            } else if let snapshot = project.snapshot {
                if let targets = snapshot.targets, !targets.isEmpty {
                    ForEach(targets) { target in
                        TargetRow(target: target, project: project.path, store: store)
                    }
                } else {
                    Text(snapshot.status == "not-configured" ? "项目尚未声明开发服务" : "配置无效")
                        .foregroundStyle(.secondary)
                    if let reason = snapshot.reason { Text(reason).font(.caption).textSelection(.enabled) }
                }
            } else {
                Text("正在检查…").foregroundStyle(.secondary)
            }
            ForEach(Array(store.unavailableReceipts(for: project).enumerated()), id: \.offset) { _, receipt in
                ReceiptView(receipt: receipt, expanded: true, store: store)
            }
            if let time = project.checkedAt {
                Text("检查于 \(time.formatted(date: .omitted, time: .standard))")
                    .font(.caption2).foregroundStyle(.tertiary)
            }
        }
    }
}
