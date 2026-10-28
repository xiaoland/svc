import SwiftUI

struct ProjectSectionView: View {
    let section: ProjectSection
    let store: AppStore
    let addProject: () -> Void
    let rename: () -> Void

    var body: some View {
        let members = store.projects(in: section.id)
        let activity = store.sectionActivity(section.id)
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                ResourceActionButton(title: section.name, semanticID: "section/\(section.id)/toggle",
                                     enabled: store.canEditSections, bordered: false,
                                     symbol: section.collapsed ? "chevron.right" : "chevron.down",
                                     accessibilityName: "\(section.collapsed ? "展开" : "收起") \(section.name) Section",
                                     expanded: !section.collapsed) {
                    store.toggleSection(section.id)
                }.frame(maxWidth: .infinity, alignment: .leading).help(section.name)
                Text("\(members.count) 个项目").font(.caption2).foregroundStyle(.secondary).fixedSize()
                if activity.running {
                    Image(systemName: "hourglass").font(.caption).help("组内有操作正在执行").accessibilityLabel("执行中")
                }
                if activity.attention {
                    Image(systemName: "exclamationmark.circle.fill").font(.caption).foregroundStyle(.orange)
                        .help("组内有错误或待确认的操作").accessibilityLabel("需处理")
                }
                Menu {
                    Button("添加项目…", action: addProject)
                    Button("重命名…", action: rename)
                    Button("上移") { store.moveSection(section.id, offset: -1) }
                        .disabled(store.organization.sections.first?.id == section.id)
                    Button("下移") { store.moveSection(section.id, offset: 1) }
                        .disabled(store.organization.sections.last?.id == section.id)
                    Divider()
                    Button("删除 Section", role: .destructive) { store.deleteSection(section.id) }
                } label: { Image(systemName: "ellipsis").frame(width: 24, height: 24) }
                .menuStyle(.borderlessButton).menuIndicator(.hidden).fixedSize()
                .disabled(!store.canEditSections).accessibilityLabel("\(section.name) Section 操作")
            }
            if !section.collapsed {
                if members.isEmpty {
                    Button(action: addProject) { Image(systemName: "plus").frame(width: 26, height: 26) }
                        .buttonStyle(.borderless).font(.caption).padding(.leading, 20).padding(.vertical, 6)
                        .help("添加项目").accessibilityLabel("添加项目到 \(section.name)")
                } else {
                    ForEach(members) { project in
                        ProjectView(project: project, store: store).id(project.path)
                    }
                }
            }
        }
    }
}
