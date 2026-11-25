import SwiftUI

struct ProjectSectionView: View {
    let section: ProjectSection
    let store: AppStore

    private var collapsed: Bool {
        store.organization.sections.first { $0.id == section.id }?.collapsed ?? section.collapsed
    }

    private var expansion: Binding<Bool> {
        Binding(get: { !collapsed }, set: { value in
            if value == collapsed { store.toggleSection(section.id) }
        }).immediateDisclosure
    }

    var body: some View {
        let members = store.projects(in: section.id)
        let activity = store.sectionActivity(section.id)
        DisclosureGroup(isExpanded: expansion) {
            VStack(alignment: .leading, spacing: 12) {
                ForEach(members) { project in
                    ProjectView(project: project, store: store, showsProjectMenu: false).id(project.path)
                }
            }.frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, 8)
        } label: {
            HStack(spacing: 8) {
                Text(section.name).font(.system(size: 13)).help(section.name)
                    .accessibilityAddTraits(.isHeader)
                Spacer(minLength: 8)
                if activity.running {
                    Image(systemName: "hourglass").font(.caption).help("组内有操作正在执行").accessibilityLabel("执行中")
                }
                if activity.attention {
                    Image(systemName: "exclamationmark.circle.fill").font(.caption).foregroundStyle(.orange)
                        .help("组内有错误或待确认的操作").accessibilityLabel("需处理")
                }
            }.frame(minHeight: 22)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityIdentifier("section/\(section.id)/toggle")
        .transaction { transaction in
            transaction.animation = nil
            transaction.disablesAnimations = true
        }
    }
}
