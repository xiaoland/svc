import SwiftUI

struct ProjectSectionView: View {
    let section: ProjectSection
    let store: AppStore
    let addProject: () -> Void
    let rename: () -> Void

    var body: some View {
        let members = store.projects(in: section.id)
        let activity = store.sectionActivity(section.id)
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 8) {
                ResourceActionButton(title: section.name, semanticID: "section/\(section.id)/toggle",
                                     enabled: store.canEditSections, bordered: false,
                                     symbol: section.collapsed ? "chevron.right" : "chevron.down") {
                    store.toggleSection(section.id)
                }.frame(maxWidth: .infinity, alignment: .leading).help(section.name)
                Text("\(members.count)").font(.caption).foregroundStyle(.secondary).fixedSize()
                if activity.running {
                    Label("执行中", systemImage: "hourglass").font(.caption).fixedSize()
                }
                if activity.attention {
                    Label("需处理", systemImage: "exclamationmark.circle").font(.caption).foregroundStyle(.orange).fixedSize()
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
                } label: { Image(systemName: "ellipsis") }
                .menuStyle(.borderlessButton).menuIndicator(.hidden).fixedSize()
                .disabled(!store.canEditSections).accessibilityLabel("\(section.name) Section 操作")
            }
            if !section.collapsed {
                if members.isEmpty {
                    Button("添加项目…", action: addProject).buttonStyle(.borderless)
                } else {
                    ForEach(members) { project in
                        ProjectView(project: project, store: store).id(project.path)
                    }
                }
            }
        }
        .padding(.leading, 10)
        .overlay(alignment: .leading) { Rectangle().fill(.quaternary).frame(width: 2) }
    }
}
