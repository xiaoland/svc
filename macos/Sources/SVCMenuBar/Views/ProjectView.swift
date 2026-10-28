import AppKit
import SwiftUI

struct ProjectView: View {
    let project: ProjectState
    let store: AppStore
    var body: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    Image(systemName: "folder").font(.system(size: 13)).accessibilityHidden(true)
                    Text(project.name).font(.system(size: 13, weight: .semibold)).lineLimit(1).help(project.path)
                        .accessibilityAddTraits(.isHeader)
                    Spacer()
                    if project.checkedAt == nil && store.refreshes[project.path] != nil { ProgressView().controlSize(.mini) }
                    Menu {
                        Text(project.path)
                        Button("在 Finder 中显示") { NSWorkspace.shared.selectFile(nil, inFileViewerRootedAtPath: project.path) }
                        Button("复制项目路径") {
                            NSPasteboard.general.clearContents()
                            NSPasteboard.general.setString(project.path, forType: .string)
                        }
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
                    } label: { Image(systemName: "ellipsis").frame(width: 24, height: 22) }
                    .menuStyle(.borderlessButton).menuIndicator(.hidden).fixedSize().help("\(project.name) 项目操作").accessibilityLabel("\(project.name) 项目操作")
                }
                ProjectUsageView(project: project.path, activity: store.activity)
                if let error = project.error {
                    DiagnosticView(title: "无法读取项目", message: error, semanticID: "project/\(project.path)/error", context: project.name)
                } else if let snapshot = project.snapshot {
                    if !snapshot.resources.isEmpty {
                        ForEach(snapshot.resources) { resource in
                            Divider().padding(.vertical, 2)
                            ResourceRow(resource: resource, project: project.path, store: store)
                        }
                    } else {
                        Text(snapshot.status == "not-configured" ? "项目尚未声明开发资源" : "配置无效")
                            .font(.caption).foregroundStyle(.secondary).padding(.vertical, 6)
                    }
                } else {
                    Text("正在读取资源…").font(.caption).foregroundStyle(.secondary).padding(.vertical, 6)
                }
                ForEach(Array(store.unavailableReceipts(for: project).enumerated()), id: \.offset) { _, receipt in
                    ReceiptView(receipt: receipt, expanded: true, store: store)
                }
            }
            .padding(4)
        }
    }
}
