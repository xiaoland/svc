import SwiftUI

enum MainWindowSelection: Hashable {
    case projects, section(UUID), project(String), executions
}

struct MainWindowView: View {
    @Bindable var store: AppStore
    let refresh: () -> Void
    let openSettings: () -> Void
    let addProject: (UUID?) -> Void
    let resourcePageChanged: (Bool) -> Void
    @State private var selection: MainWindowSelection? = .projects
    @State private var editingSection = false
    @State private var editingSectionID: UUID?
    @State private var sectionName = ""
    @State private var showingExecutions = false

    var body: some View {
        NavigationSplitView {
            VStack(spacing: 0) {
                List(selection: $selection) {
                    Label("全部项目", systemImage: "server.rack")
                        .tag(MainWindowSelection.projects)
                    Label("执行", systemImage: "terminal")
                        .tag(MainWindowSelection.executions)
                    ForEach(store.organization.sections) { section in
                        DisclosureGroup(isExpanded: Binding(
                            get: { !section.collapsed },
                            set: { if $0 == section.collapsed { store.toggleSection(section.id) } }
                        )) {
                            ForEach(store.projects(in: section.id)) { project in
                                projectLink(project)
                            }
                        } label: {
                            HStack {
                                Label(section.name, systemImage: "folder")
                                Spacer()
                                let activity = store.sectionActivity(section.id)
                                if activity.running {
                                    Image(systemName: "hourglass").accessibilityLabel("执行中")
                                } else if activity.attention {
                                    Image(systemName: "exclamationmark.circle.fill")
                                        .foregroundStyle(.orange).accessibilityLabel("需处理")
                                }
                            }
                        }
                        .tag(MainWindowSelection.section(section.id))
                        .contextMenu { sectionMenu(section) }
                    }
                    let ungrouped = store.projects(in: nil)
                    if !ungrouped.isEmpty {
                        Section("未分组") {
                            ForEach(ungrouped) { project in projectLink(project) }
                        }
                    }
                }
                .listStyle(.sidebar)
                .accessibilityIdentifier("main/navigation")
                Divider()
                HStack {
                    Menu {
                        Button("添加项目…") { addProject(selectedSectionID) }
                        Button("新建 Section…") { editSection(nil) }
                            .disabled(!store.canEditSections)
                    } label: { Image(systemName: "plus").frame(width: 26, height: 26) }
                        .menuStyle(.borderlessButton).menuIndicator(.hidden).fixedSize()
                        .help("添加项目或 Section").accessibilityLabel("添加项目或 Section")
                        .disabled(store.quitPending)
                    Spacer()
                }.padding(12)
            }
            .navigationSplitViewColumnWidth(min: 190, ideal: 230, max: 320)
        } detail: {
            VStack(spacing: 0) {
                HostPressureView(activity: store.activity)
                Divider()
                if selection == .executions {
                    ScrollView { ExecutionListView(store: store) }
                        .accessibilityIdentifier("main/executions")
                } else {
                    resourceContent
                }
                statusFooter
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .toolbar {
            ToolbarItemGroup(placement: .primaryAction) {
                Button(action: refresh) { Label("刷新", systemImage: "arrow.clockwise") }
                    .help("刷新机器与当前页面（⌘R）")
                    .disabled(store.quitPending || store.activity.refreshing || !store.refreshes.isEmpty)
                Button(action: openSettings) { Label("设置", systemImage: "gearshape") }
                    .help("设置（⌘,）")
            }
        }
        .sheet(isPresented: $editingSection) {
            SectionNameEditor(sectionID: editingSectionID, name: sectionName, store: store) {
                editingSection = false
            }.frame(width: 360)
        }
        .onChange(of: selection) { _, _ in resourcePageChanged(needsResourceObservation) }
        .onChange(of: showingExecutions) { _, _ in resourcePageChanged(needsResourceObservation) }
        .onChange(of: store.organization.sections.map(\.id)) { _, _ in validateSelection() }
        .onChange(of: store.projects.map(\.path)) { _, _ in validateSelection() }
    }

    private var resourceContent: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Text(selectionTitle).font(.title2).fontWeight(.semibold)
                        .accessibilityAddTraits(.isHeader)
                    Spacer()
                    if selectedProjects.count > 1 {
                        Text("\(selectedProjects.count) 个项目").foregroundStyle(.secondary)
                    }
                }
                if let error = store.sectionStorageError {
                    DiagnosticView(title: "无法读取分组", message: error, semanticID: "main/sections/error")
                }
                Picker("项目内容", selection: $showingExecutions) {
                    Text("资源").tag(false)
                    Text("执行").tag(true)
                }.pickerStyle(.segmented).labelsHidden()
                    .accessibilityIdentifier("main/project-pages")
                if showingExecutions {
                    ForEach(selectedProjects) { project in
                        GroupBox(project.name) { ProjectUsageView(project: project.path, activity: store.activity).padding(4) }
                    }
                    ExecutionListView(store: store, projectPaths: Set(selectedProjects.map(\.path)))
                } else if selectedProjects.isEmpty {
                    ContentUnavailableView {
                        Label("尚无项目", systemImage: "folder")
                    } actions: {
                        Button("添加项目…") { addProject(selectedSectionID) }
                            .disabled(store.quitPending)
                    }.frame(maxWidth: .infinity).padding(.vertical, 48)
                } else {
                    ForEach(selectedProjects) { project in
                        ProjectView(project: project, store: store)
                    }
                }
            }.padding(20).frame(maxWidth: 1000, alignment: .leading)
                .frame(maxWidth: .infinity, alignment: .topLeading)
        }.accessibilityIdentifier("main/resources")
    }

    private var needsResourceObservation: Bool {
        selection != .executions && !showingExecutions
    }

    @ViewBuilder private var statusFooter: some View {
        if store.quitPending {
            Divider()
            HStack {
                ProgressView().controlSize(.small)
                Text("操作结束后退出")
                Spacer()
                Button("取消退出") { store.cancelQuit() }
            }.padding(12)
        }
        if let notice = store.notice {
            Divider()
            HStack(alignment: .top) {
                Text(notice).textSelection(.enabled)
                Spacer()
                Button { store.notice = nil } label: { Image(systemName: "xmark") }
                    .buttonStyle(.borderless).accessibilityLabel("关闭提示")
            }.font(.caption).padding(12)
        }
    }

    private func projectLink(_ project: ProjectState) -> some View {
        Label(project.name, systemImage: "folder")
            .tag(MainWindowSelection.project(project.path)).help(project.path)
            .accessibilityLabel("\(project.name)，\(project.path)")
    }

    @ViewBuilder private func sectionMenu(_ section: ProjectSection) -> some View {
        Button("添加项目…") { addProject(section.id) }.disabled(store.quitPending)
        Button("重命名…") { editSection(section) }.disabled(!store.canEditSections)
        Button("上移") { store.moveSection(section.id, offset: -1) }
            .disabled(!store.canEditSections || store.organization.sections.first?.id == section.id)
        Button("下移") { store.moveSection(section.id, offset: 1) }
            .disabled(!store.canEditSections || store.organization.sections.last?.id == section.id)
        Divider()
        Button("删除 Section", role: .destructive) { store.deleteSection(section.id) }
            .disabled(!store.canEditSections)
    }

    private var selectedSectionID: UUID? {
        if case .section(let id) = selection { return id }
        return nil
    }

    private var selectedProjects: [ProjectState] {
        switch selection {
        case .section(let id): store.projects(in: id)
        case .project(let path): store.projects.filter { $0.path == path }
        default: store.projects
        }
    }

    private var selectionTitle: String {
        switch selection {
        case .section(let id): store.organization.sections.first { $0.id == id }?.name ?? "全部项目"
        case .project(let path): URL(fileURLWithPath: path).lastPathComponent
        default: "全部项目"
        }
    }

    private func editSection(_ section: ProjectSection?) {
        editingSectionID = section?.id
        sectionName = section?.name ?? ""
        editingSection = true
    }

    private func validateSelection() {
        switch selection {
        case .section(let id) where !store.organization.sections.contains(where: { $0.id == id }):
            selection = .projects
        case .project(let path) where !store.projects.contains(where: { $0.path == path }):
            selection = .projects
        default: break
        }
    }
}
