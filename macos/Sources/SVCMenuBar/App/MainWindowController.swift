import AppKit
import SwiftUI

@MainActor
final class MainWindowController: NSWindowController, NSWindowDelegate {
    private let store: AppStore
    private let closed: () -> Void
    private var showsResources = true
    private var presented = false

    init(store: AppStore, openSettings: @escaping () -> Void, closed: @escaping () -> Void) {
        self.store = store
        self.closed = closed
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1040, height: 720),
                              styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                              backing: .buffered, defer: false)
        window.title = "SVC Dev"
        window.toolbarStyle = .unified
        window.identifier = NSUserInterfaceItemIdentifier("svc.main")
        window.isReleasedWhenClosed = false
        window.contentMinSize = NSSize(width: 740, height: 480)
        window.center()
        window.setFrameUsingName("SVCMainWindow")
        let initialFrame = window.frame
        super.init(window: window)
        window.delegate = self
        let content = NSHostingController(rootView: MainWindowView(
            store: store,
            refresh: { [weak self] in self?.refreshCurrentPage() },
            openSettings: openSettings,
            addProject: { [weak window] sectionID in
                ProjectPicker.present(store: store, sectionID: sectionID, parent: window)
            },
            resourcePageChanged: { [weak self] value in
                self?.showsResources = value
                self?.updateObservationDemand()
            }
        ))
        content.sizingOptions = [.minSize]
        // SwiftUI owns every toolbar item, while AppKit retains the fixed title.
        // Mixing a manual NSToolbar with this bridge causes it to be replaced.
        content.sceneBridgingOptions = [.toolbars]
        window.contentViewController = content
        window.setFrame(initialFrame, display: false)
        window.setFrameAutosaveName("SVCMainWindow")
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

    @objc func refreshCurrentPage() {
        guard !store.quitPending else { return }
        Task {
            await store.activity.refresh(store.configuration)
            if showsResources { await store.refreshAll() }
        }
    }
}
