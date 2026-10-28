import AppKit
import SwiftUI

struct MenuPanel: View {
    @Bindable var store: AppStore
    let openSettings: () -> Void
    var openMainWindow: () -> Void = {}
    var resourcePageChanged: (Bool) -> Void = { _ in }
    @State private var editingSection = false
    @State private var sectionID: UUID?
    @State private var sectionName = ""
    @State private var selectedTab = 0

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                Image(systemName: "server.rack").font(.system(size: 19)).foregroundStyle(.tint).accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    Text("SVC Dev").font(.headline)
                    Text(summary)
                        .font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Button { Task { await refreshPanel() } } label: {
                    Image(systemName: "arrow.clockwise").frame(width: 26, height: 26)
                }
                .help("刷新机器与当前页面").accessibilityLabel("刷新机器与当前页面")
                .keyboardShortcut("r").disabled(store.quitPending || store.activity.refreshing || !store.refreshes.isEmpty)
                Menu {
                    Button("添加项目…") { addProject() }.keyboardShortcut("o")
                    Button("新建 Section…") { editSection(nil) }.disabled(!store.canEditSections)
                } label: { Image(systemName: "plus").frame(width: 26, height: 26) }
                    .menuStyle(.borderlessButton).menuIndicator(.hidden).fixedSize()
                    .help("添加项目或 Section").accessibilityLabel("添加项目或 Section")
                    .disabled(store.quitPending)
            }
            .buttonStyle(.borderless).padding(.horizontal, 16).padding(.vertical, 12)
            Divider()
            HostPressureView(activity: store.activity)
            Picker("页面", selection: $selectedTab) {
                Text("资源").tag(0)
                Text("执行").tag(1)
            }.pickerStyle(.segmented).labelsHidden()
                .accessibilityIdentifier("panel/pages")
                .padding(.horizontal, 12).padding(.bottom, 10)
            Divider()
            if selectedTab == 1 {
                ScrollView { ExecutionListView(store: store) }.frame(height: 340)
            } else {
            if editingSection {
                SectionNameEditor(sectionID: sectionID, name: sectionName, store: store) { editingSection = false }
                    .id(sectionID)
                Divider()
            }
            if let error = store.sectionStorageError {
                DiagnosticView(title: "无法读取分组", message: error, semanticID: "sections/error").padding(12)
            }
            if store.projects.isEmpty && store.organization.sections.isEmpty {
                VStack(spacing: 16) {
                    Image(systemName: "folder.badge.plus").font(.system(size: 36)).foregroundStyle(.secondary)
                    Text("添加第一个项目").font(.headline)
                    Button("选择项目文件夹…") { addProject() }.buttonStyle(.borderedProminent)
                }.frame(maxWidth: .infinity).padding(.vertical, 42)
            } else {
                ScrollViewReader { proxy in
                    ViewThatFits(in: .vertical) {
                        projectList.fixedSize(horizontal: false, vertical: true)
                        ScrollView { projectList }
                    }.frame(maxHeight: 480)
                        .onChange(of: store.projectReveal) { _, reveal in
                            if let reveal { proxy.scrollTo(reveal.path, anchor: .top) }
                        }
                }
            }
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
                    Text(notice).font(.caption).lineLimit(3).help(notice).textSelection(.enabled)
                    Spacer()
                    Button { store.notice = nil } label: { Image(systemName: "xmark") }
                        .buttonStyle(.borderless).help("关闭提示").accessibilityLabel("关闭提示")
                }.padding(12)
            }
            Divider()
            HStack {
                Button(action: openMainWindow) {
                    Image(systemName: "macwindow")
                }.help("打开主窗口").accessibilityLabel("打开主窗口")
                Button {
                    NSApp.activate(ignoringOtherApps: true)
                    openSettings()
                } label: { Image(systemName: "gearshape") }
                .help("设置").accessibilityLabel("设置")
                .keyboardShortcut(",")
                Spacer()
                if let time = selectedTab == 0 ? store.projects.compactMap(\.checkedAt).max() : store.activity.checkedAt {
                    Text("更新于 \(time.formatted(date: .omitted, time: .shortened))")
                        .font(.caption2).foregroundStyle(.secondary)
                }
                Spacer()
                Button("退出 SVC") { NSApp.terminate(nil) }
                    .keyboardShortcut("q").disabled(store.quitPending)
            }.buttonStyle(.borderless).font(.caption).padding(.horizontal, 16).padding(.vertical, 10)
        }
        .frame(width: 420)
        .background(Color(nsColor: .windowBackgroundColor))
        .onChange(of: selectedTab) { _, _ in
            resourcePageChanged(selectedTab == 0)
        }
    }

    private func refreshPanel() async {
        guard !store.quitPending else { return }
        await store.activity.refresh(store.configuration)
        if selectedTab == 0 { await store.refreshAll() }
    }

    private var projectList: some View {
        VStack(alignment: .leading, spacing: 12) {
            ForEach(store.organization.sections) { section in
                ProjectSectionView(section: section, store: store,
                                   addProject: { addProject(sectionID: section.id) },
                                   rename: { editSection(section) })
            }
            let ungrouped = store.projects(in: nil)
            if !ungrouped.isEmpty {
                if !store.organization.sections.isEmpty {
                    Text("未分组").font(.system(size: 12, weight: .semibold)).foregroundStyle(.secondary)
                        .padding(.top, 4).padding(.leading, 4)
                }
                ForEach(ungrouped) { project in
                    ProjectView(project: project, store: store).id(project.path)
                }
            }
        }.padding(12)
    }

    private var summary: String {
        let projects = "\(store.projects.count) 个项目"
        let complete = store.projects.allSatisfy { $0.snapshot != nil && $0.error == nil }
        if complete && !store.projects.isEmpty { return "\(projects) · \(store.resourceCount) 个资源" }
        if store.resourceCount > 0 { return "\(projects) · 已读取 \(store.resourceCount) 个资源" }
        return projects
    }

    private func editSection(_ section: ProjectSection?) {
        sectionID = section?.id
        sectionName = section?.name ?? ""
        editingSection = true
    }

    private func addProject(sectionID: UUID? = nil) {
        ProjectPicker.present(store: store, sectionID: sectionID)
    }
}
