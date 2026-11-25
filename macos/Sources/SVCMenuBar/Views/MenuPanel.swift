import AppKit
import SwiftUI

struct MenuPanel: View {
    @Bindable var store: AppStore
    var openMainWindow: () -> Void = {}
    var resourcePageChanged: (Bool) -> Void = { _ in }
    @State private var selectedTab = 0

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                Button(action: openMainWindow) {
                    HStack(spacing: 10) {
                        Image(systemName: "server.rack").font(.system(size: 19)).foregroundStyle(.tint)
                        VStack(alignment: .leading, spacing: 2) {
                            Text("SVC Dev").font(.headline)
                            Text(summary).font(.caption).foregroundStyle(.secondary)
                        }
                    }.contentShape(Rectangle())
                }
                .help("打开主窗口").accessibilityLabel("打开主窗口")
                .accessibilityValue(summary).accessibilityIdentifier("panel/open-main-window")
                .keyboardShortcut("0")
                Spacer()
                if let time = lastUpdated {
                    Text(time.formatted(date: .omitted, time: .shortened))
                        .font(.caption2).monospacedDigit().foregroundStyle(.secondary)
                        .help("上次更新：\(time.formatted(date: .abbreviated, time: .standard))")
                        .accessibilityLabel("上次更新")
                        .accessibilityValue(time.formatted(date: .omitted, time: .shortened))
                        .accessibilityIdentifier("panel/last-updated")
                }
                Button { Task { await refreshPanel() } } label: {
                    Image(systemName: "arrow.clockwise").frame(width: 26, height: 26)
                }
                .help("刷新机器与当前页面").accessibilityLabel("刷新机器与当前页面")
                .keyboardShortcut("r").disabled(store.quitPending || store.activity.refreshing || !store.refreshes.isEmpty)
            }
            .buttonStyle(.borderless).padding(.horizontal, 16).padding(.vertical, 12)
            Divider()
            if store.activity.cliUnavailable || (store.configuration.environmentMode == .fixedPath && store.configuration.resolvedExecutable == nil) {
                HStack {
                    Label("需要配置 SVC CLI", systemImage: "exclamationmark.circle")
                    Spacer()
                    Button("打开主窗口", action: openMainWindow)
                }.font(.caption).padding(12)
                Divider()
            }
            HostPressureView(activity: store.activity)
            Picker("页面", selection: $selectedTab) {
                Text("资源").tag(0)
                Text("执行").tag(1)
            }.pickerStyle(.segmented).labelsHidden()
                .accessibilityIdentifier("panel/pages")
                .padding(.horizontal, 12).padding(.bottom, 10)
            Divider()
            if selectedTab == 1 {
                ScrollView { ExecutionListView(store: store, currentOnly: true) }.frame(height: 340)
            } else {
                if let error = store.sectionStorageError {
                    DiagnosticView(title: "无法读取分组", message: error, semanticID: "sections/error").padding(12)
                }
                if store.projects.isEmpty {
                    VStack(spacing: 16) {
                        Image(systemName: "folder").font(.system(size: 36)).foregroundStyle(.secondary)
                        Text("尚无项目").font(.headline)
                        Button("在主窗口管理项目", action: openMainWindow).buttonStyle(.borderedProminent)
                    }.frame(maxWidth: .infinity).padding(.vertical, 42)
                } else {
                    ScrollViewReader { proxy in
                        ScrollView { projectList }
                            .frame(height: 480)
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
        }
        .frame(width: 420)
        .background(Color(nsColor: .windowBackgroundColor))
        .onChange(of: selectedTab) { _, _ in
            resourcePageChanged(selectedTab == 0)
        }
    }

    private func refreshPanel() async {
        guard !store.quitPending else { return }
        store.reloadExecutionEnvironments()
        await store.activity.refresh(store.configuration)
        if selectedTab == 0 { await store.refreshAll() }
    }

    private var lastUpdated: Date? {
        selectedTab == 0 ? store.projects.compactMap(\.checkedAt).max() : store.activity.checkedAt
    }

    private var projectList: some View {
        VStack(alignment: .leading, spacing: 12) {
            ForEach(store.organization.sections.filter { !store.projects(in: $0.id).isEmpty }) { section in
                ProjectSectionView(section: section, store: store)
            }
            let ungrouped = store.projects(in: nil)
            if !ungrouped.isEmpty {
                ForEach(ungrouped) { project in
                    ProjectView(project: project, store: store, showsProjectMenu: false).id(project.path)
                }
            }
        }.frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 16).padding(.vertical, 12)
    }

    private var summary: String {
        let projects = "\(store.projects.count) 个项目"
        let complete = store.projects.allSatisfy { $0.snapshot != nil && $0.error == nil }
        if complete && !store.projects.isEmpty { return "\(projects) · \(store.resourceCount) 个资源" }
        if store.resourceCount > 0 { return "\(projects) · 已读取 \(store.resourceCount) 个资源" }
        return projects
    }
}
