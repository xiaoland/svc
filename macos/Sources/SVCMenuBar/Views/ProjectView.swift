import AppKit
import SwiftUI

struct ProjectView: View {
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
                    Menu("移到 Section") {
                        Button("未分组") { store.moveProject(project.path, to: nil) }
                            .disabled(store.organization.assignments[project.path] == nil)
                        ForEach(store.organization.sections) { section in
                            Button(section.name) { store.moveProject(project.path, to: section.id) }
                                .disabled(store.organization.assignments[project.path] == section.id)
                        }
                    }.disabled(!store.canEditSections)
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
                if !snapshot.resources.isEmpty {
                    ForEach(snapshot.resources) { resource in
                        ResourceRow(resource: resource, project: project.path, store: store)
                    }
                } else {
                    Text(snapshot.status == "not-configured" ? "项目尚未声明开发资源" : "配置无效")
                        .foregroundStyle(.secondary)
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
