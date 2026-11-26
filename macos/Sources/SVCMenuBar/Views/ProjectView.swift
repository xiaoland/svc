import AppKit
import SwiftUI

struct ProjectView: View {
    let project: ProjectState
    let store: AppStore
    var showsProjectMenu = true

    private var expansion: Binding<Bool> {
        Binding(get: { !store.collapsedProjects.contains(project.path) },
                set: { store.setProjectExpanded(project.path, $0) }).immediateDisclosure
    }

    var body: some View {
        DisclosureGroup(isExpanded: expansion) {
            VStack(alignment: .leading, spacing: 4) {
                if let error = store.projectDiagnostic(project) {
                    DiagnosticView(title: "无法读取项目", message: error, semanticID: "project/\(project.path)/error", context: project.name)
                } else if let snapshot = project.snapshot {
                    if !snapshot.resources.isEmpty {
                        ForEach(snapshot.resources) { resource in
                            if resource.id != snapshot.resources.first?.id { Divider() }
                            ResourceRow(resource: resource, project: project.path, store: store)
                        }
                    } else {
                        Text(snapshot.status == "not-configured" ? "项目尚未声明开发资源" : "配置无效")
                            .font(.caption).foregroundStyle(.secondary).padding(.vertical, 6)
                    }
                } else if project.error == nil && !store.missingSharedCLI {
                    Text("正在读取资源…").font(.caption).foregroundStyle(.secondary).padding(.vertical, 6)
                }
                ForEach(Array(store.unavailableReceipts(for: project).enumerated()), id: \.offset) { _, receipt in
                    ReceiptView(receipt: receipt, expanded: true, store: store)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        } label: {
            HStack(spacing: 8) {
                Text(project.name).font(.system(size: 13, weight: .semibold)).lineLimit(1).help(project.path)
                    .accessibilityAddTraits(.isHeader)
                Spacer(minLength: 8)
                let activity = store.projectActivity(project.path)
                if activity.running {
                    Image(systemName: "hourglass").font(.caption).accessibilityLabel("执行中")
                        .help("项目内有操作正在执行")
                }
                if activity.attention {
                    Image(systemName: "exclamationmark.circle.fill").font(.caption).foregroundStyle(.orange)
                        .accessibilityLabel("需处理").help("项目内有错误或待确认的操作")
                }
                if project.checkedAt == nil && store.refreshes[project.path] != nil { ProgressView().controlSize(.mini) }
                ProjectUsageView(project: project.path, activity: store.activity).fixedSize()
                if showsProjectMenu {
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
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityIdentifier("project/\(project.path)/details")
        .transaction { transaction in
            transaction.animation = nil
            transaction.disablesAnimations = true
        }
    }
}
