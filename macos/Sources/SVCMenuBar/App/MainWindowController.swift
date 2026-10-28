import AppKit
import SwiftUI

@MainActor
final class MainWindowController: NSWindowController, NSWindowDelegate, NSToolbarDelegate, NSToolbarItemValidation {
    private let store: AppStore
    private let openSettings: () -> Void
    private let closed: () -> Void
    private var showsResources = true
    private var presented = false
    private static let refreshID = NSToolbarItem.Identifier("svc.refresh")
    private static let settingsID = NSToolbarItem.Identifier("svc.settings")

    init(store: AppStore, openSettings: @escaping () -> Void, closed: @escaping () -> Void) {
        self.store = store
        self.openSettings = openSettings
        self.closed = closed
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1040, height: 720),
                              styleMask: [.titled, .closable, .miniaturizable, .resizable],
                              backing: .buffered, defer: false)
        window.title = "SVC Dev"
        window.identifier = NSUserInterfaceItemIdentifier("svc.main")
        window.isReleasedWhenClosed = false
        window.contentMinSize = NSSize(width: 740, height: 480)
        window.center()
        window.setFrameAutosaveName("SVCMainWindow")
        super.init(window: window)
        window.delegate = self
        window.contentViewController = NSHostingController(rootView: MainWindowView(
            store: store,
            addProject: { [weak window] sectionID in
                ProjectPicker.present(store: store, sectionID: sectionID, parent: window)
            },
            resourcePageChanged: { [weak self] value in
                self?.showsResources = value
                self?.updateObservationDemand()
            }
        ))
        let toolbar = NSToolbar(identifier: "SVCMainToolbar")
        toolbar.delegate = self
        toolbar.displayMode = .iconOnly
        window.toolbar = toolbar
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    func present() {
        presented = true
        if window?.isMiniaturized == true { window?.deminiaturize(nil) }
        showWindow(nil)
        window?.makeKeyAndOrderFront(nil)
        updateObservationDemand()
    }

    func updateObservationDemand() {
        let visible = presented && (window.map { $0.isVisible && !$0.isMiniaturized && $0.occlusionState.contains(.visible) } ?? false)
        store.setObservationDemand(.mainWindow, resources: visible && !NSApp.isHidden ? showsResources : nil)
    }

    func windowDidChangeOcclusionState(_ notification: Notification) { updateObservationDemand() }
    func windowDidMiniaturize(_ notification: Notification) { updateObservationDemand() }
    func windowDidDeminiaturize(_ notification: Notification) { updateObservationDemand() }
    func windowWillClose(_ notification: Notification) {
        presented = false
        store.setObservationDemand(.mainWindow, resources: nil)
        closed()
    }

    func toolbarDefaultItemIdentifiers(_ toolbar: NSToolbar) -> [NSToolbarItem.Identifier] {
        [.flexibleSpace, Self.refreshID, Self.settingsID]
    }

    func toolbarAllowedItemIdentifiers(_ toolbar: NSToolbar) -> [NSToolbarItem.Identifier] {
        toolbarDefaultItemIdentifiers(toolbar)
    }

    func toolbar(_ toolbar: NSToolbar, itemForItemIdentifier id: NSToolbarItem.Identifier,
                 willBeInsertedIntoToolbar flag: Bool) -> NSToolbarItem? {
        guard id == Self.refreshID || id == Self.settingsID else { return nil }
        let item = NSToolbarItem(itemIdentifier: id)
        let refresh = id == Self.refreshID
        item.label = refresh ? "刷新" : "设置"
        item.toolTip = refresh ? "刷新机器与当前页面（⌘R）" : "设置（⌘,）"
        item.image = NSImage(systemSymbolName: refresh ? "arrow.clockwise" : "gearshape", accessibilityDescription: item.label)
        item.target = self
        item.action = refresh ? #selector(refreshCurrentPage) : #selector(showSettings)
        return item
    }

    func validateToolbarItem(_ item: NSToolbarItem) -> Bool {
        item.itemIdentifier != Self.refreshID || (!store.quitPending && !store.activity.refreshing && store.refreshes.isEmpty)
    }

    @objc func refreshCurrentPage() {
        guard !store.quitPending else { return }
        Task {
            await store.activity.refresh(store.configuration)
            if showsResources { await store.refreshAll() }
        }
    }

    @objc private func showSettings() { openSettings() }
}
