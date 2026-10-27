import AppKit
import SwiftUI

struct MenuPanel: View {
    @Bindable var store: AppStore
    let openSettings: () -> Void
    @State private var editingSection = false
    @State private var sectionID: UUID?
    @State private var sectionName = ""

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                Image(systemName: "server.rack").font(.title2).foregroundStyle(.tint)
                VStack(alignment: .leading, spacing: 2) {
                    Text("开发资源").font(.headline)
                    Text("\(store.resourceCount) 个资源")
                        .font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Button { Task { await store.refreshAll() } } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .help("刷新资源状态").accessibilityLabel("刷新资源状态")
                .keyboardShortcut("r").disabled(store.quitPending || !store.refreshes.isEmpty)
                Menu {
                    Button("添加项目…") { addProject() }.keyboardShortcut("o")
                    Button("新建 Section…") { editSection(nil) }.disabled(!store.canEditSections)
                } label: { Image(systemName: "plus") }
                    .menuStyle(.borderlessButton).menuIndicator(.hidden).fixedSize()
                    .help("添加项目或 Section").accessibilityLabel("添加项目或 Section")
                    .disabled(store.quitPending)
            }
            .buttonStyle(.borderless).padding(18)
            Divider()
            if editingSection {
                SectionNameEditor(sectionID: sectionID, name: sectionName, store: store) { editingSection = false }
                    .id(sectionID)
                Divider()
            }
            if let error = store.sectionStorageError {
                Text(error).font(.caption).foregroundStyle(.orange).padding(12)
            }
            if store.projects.isEmpty && store.organization.sections.isEmpty {
                VStack(spacing: 16) {
                    Image(systemName: "folder.badge.plus").font(.system(size: 36)).foregroundStyle(.secondary)
                    Text("添加开发项目").font(.headline)
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
            ForEach(store.organization.sections) { section in
                ProjectSectionView(section: section, store: store,
                                   addProject: { addProject(sectionID: section.id) },
                                   rename: { editSection(section) })
            }
            let ungrouped = store.projects(in: nil)
            if !ungrouped.isEmpty {
                if !store.organization.sections.isEmpty {
                    Text("未分组").font(.headline).foregroundStyle(.secondary)
                }
                ForEach(ungrouped) { project in
                    ProjectView(project: project, store: store).id(project.path)
                }
            }
        }.padding(16)
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
