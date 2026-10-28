import AppKit
import SwiftUI

struct MenuPanel: View {
    @Bindable var store: AppStore
    let openSettings: () -> Void
    @State private var editingSection = false
    @State private var sectionID: UUID?
    @State private var sectionName = ""
    @State private var selectedTab = 0
    @FocusState private var focusedPage: Int?

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                Image(systemName: "server.rack").font(.system(size: 19)).foregroundStyle(.tint).accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    Text("SVC Dev").font(.headline)
                    Text(summary)
                        .font(.system(size: 12)).foregroundStyle(.primary)
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
                } label: { Label("添加", systemImage: "plus").frame(height: 26) }
                    .menuStyle(.borderlessButton).fixedSize()
                    .help("添加项目或 Section").accessibilityLabel("添加项目或 Section")
                    .disabled(store.quitPending)
            }
            .buttonStyle(.borderless).padding(.horizontal, 16).padding(.vertical, 12)
            Divider()
            HostPressureView(activity: store.activity)
            HStack(spacing: 6) {
                pageButton("资源", tab: 0, shortcut: "1")
                pageButton("执行", tab: 1, shortcut: "2")
            }.padding(.horizontal, 12).padding(.bottom, 10)
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
                    Image(systemName: "folder.badge.plus").font(.system(size: 36)).foregroundStyle(.primary)
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
                    Text("操作结束后退出").font(.system(size: 12))
                    Spacer()
                    Button("取消退出") { store.cancelQuit() }
                }.padding(12)
            }
            if let notice = store.notice {
                HStack(alignment: .top) {
                    Text(notice).font(.system(size: 12)).lineLimit(3).help(notice).textSelection(.enabled)
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
                if let time = selectedTab == 0 ? store.projects.compactMap(\.checkedAt).max() : store.activity.checkedAt {
                    Text("更新于 \(time.formatted(date: .omitted, time: .shortened))")
                        .font(.system(size: 12)).foregroundStyle(.primary)
                }
                Spacer()
                Button("退出 SVC") { NSApp.terminate(nil) }
                    .keyboardShortcut("q").disabled(store.quitPending)
            }.buttonStyle(.borderless).font(.system(size: 12)).padding(.horizontal, 16).padding(.vertical, 10)
        }
        .frame(width: 420)
        .background(Color(nsColor: .windowBackgroundColor))
        .task(id: store.panelVisible) {
            guard store.panelVisible else { return }
            while !Task.isCancelled && store.panelVisible {
                await store.activity.refresh(store.configuration)
                do { try await Task.sleep(for: .seconds(5)) } catch { break }
            }
        }
        .task(id: "\(store.panelVisible)-\(selectedTab)") {
            guard store.panelVisible, selectedTab == 0 else { return }
            while !Task.isCancelled && store.panelVisible && selectedTab == 0 {
                await store.refreshAll()
                do { try await Task.sleep(for: .seconds(5)) } catch { break }
            }
        }
        .onChange(of: selectedTab) { _, _ in
            Task { await store.activity.refresh(store.configuration) }
        }
    }

    private func pageButton(_ title: String, tab: Int, shortcut: KeyEquivalent) -> some View {
        let selected = selectedTab == tab
        return Button { selectedTab = tab } label: {
            HStack(spacing: 5) {
                Text(title).font(.system(size: 13, weight: selected ? .semibold : .regular))
                if selected { Image(systemName: "checkmark").accessibilityHidden(true) }
            }.frame(maxWidth: .infinity, minHeight: 30)
                .foregroundStyle(.primary)
                .background(selected ? Color(nsColor: .controlBackgroundColor) : .clear, in: RoundedRectangle(cornerRadius: 6))
                .overlay {
                    RoundedRectangle(cornerRadius: 6)
                        .strokeBorder(selected ? Color.primary : Color(nsColor: .separatorColor), lineWidth: selected ? 1.5 : 1)
                }
        }.buttonStyle(.plain)
            .focused($focusedPage, equals: tab)
            .overlay {
                if focusedPage == tab {
                    RoundedRectangle(cornerRadius: 8).strokeBorder(Color.accentColor, lineWidth: 3).padding(-3)
                }
            }
            .accessibilityLabel("\(title)页面")
            .accessibilityValue(selected ? "已选择" : "未选择")
            .accessibilityAddTraits(selected ? [.isSelected] : [])
            .accessibilityIdentifier("panel/page/\(tab)")
            .keyboardShortcut(shortcut, modifiers: .command)
    }

    private func refreshPanel() async {
        guard !store.quitPending else { return }
        await store.activity.refresh(store.configuration)
        if selectedTab == 0 && store.panelVisible { await store.refreshAll() }
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
                    Text("未分组").font(.system(size: 12, weight: .semibold)).foregroundStyle(.primary)
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
        let panel = NSOpenPanel()
        panel.title = "添加 SVC 项目"
        panel.prompt = "添加项目"
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = true
        NSApp.activate(ignoringOtherApps: true)
        panel.begin { response in
            if response == .OK { for url in panel.urls { store.addProject(url, sectionID: sectionID) } }
        }
    }
}
