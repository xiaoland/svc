import AppKit
import SwiftUI

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate, NSPopoverDelegate {
    let store: AppStore

    init(store: AppStore) {
        self.store = store
        super.init()
    }
    private var statusItem: NSStatusItem?
    private let popover = NSPopover()
    private var settingsWindow: NSWindow?

    func applicationDidFinishLaunching(_ notification: Notification) {
        installMenu()
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        item.button?.image = NSImage(systemSymbolName: "server.rack", accessibilityDescription: "SVC 开发资源")
        item.button?.toolTip = "SVC 开发资源"
        item.button?.target = self
        item.button?.action = #selector(togglePanel)
        statusItem = item
        popover.behavior = .transient
        popover.delegate = self
        let controller = NSHostingController(rootView: MenuPanel(store: store, openSettings: { [weak self] in
            self?.showSettings()
        }))
        controller.sizingOptions = [.preferredContentSize]
        popover.contentViewController = controller
        if !ProcessInfo.processInfo.arguments.contains("--background") { showPanel() }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        showPanel()
        return false
    }

    @objc private func togglePanel() {
        if popover.isShown { popover.performClose(nil) } else { showPanel() }
    }

    private func showPanel() {
        guard let button = statusItem?.button else { return }
        NSApp.activate(ignoringOtherApps: true)
        popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
        popover.contentViewController?.view.window?.makeKey()
    }

    func popoverDidShow(_ notification: Notification) { store.panelVisible = true }

    func popoverDidClose(_ notification: Notification) { store.panelVisible = false }

    @objc private func showSettings() {
        popover.performClose(nil)
        if settingsWindow == nil {
            let window = NSWindow(contentViewController: NSHostingController(rootView: SettingsView(store: store)))
            window.title = "SVC 设置"
            window.styleMask = [.titled, .closable]
            window.isReleasedWhenClosed = false
            window.center()
            settingsWindow = window
        }
        NSApp.activate(ignoringOtherApps: true)
        settingsWindow?.makeKeyAndOrderFront(nil)
    }

    private func installMenu() {
        let main = NSMenu()
        let appItem = main.addItem(withTitle: "SVC", action: nil, keyEquivalent: "")
        let appMenu = NSMenu(title: "SVC")
        appItem.submenu = appMenu
        let settings = appMenu.addItem(withTitle: "设置…", action: #selector(showSettings), keyEquivalent: ",")
        settings.target = self
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "退出 SVC", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let edit = NSMenu(title: "编辑")
        main.addItem(withTitle: "编辑", action: nil, keyEquivalent: "").submenu = edit
        for (title, action, key) in [
            ("剪切", #selector(NSText.cut(_:)), "x"),
            ("复制", #selector(NSText.copy(_:)), "c"),
            ("粘贴", #selector(NSText.paste(_:)), "v"),
            ("全选", #selector(NSText.selectAll(_:)), "a")
        ] {
            edit.addItem(withTitle: title, action: action, keyEquivalent: key)
        }
        NSApp.mainMenu = main
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard !store.operations.isEmpty else { return .terminateNow }
        store.waitToQuit { sender.reply(toApplicationShouldTerminate: $0) }
        if sender.isActive { showPanel() }
        return .terminateLater
    }
}

@main
struct SVCMenuBarApp {
    @MainActor static func main() {
        let application = NSApplication.shared
        application.setActivationPolicy(.accessory)
        let delegate = AppDelegate(store: AppStore())
        application.delegate = delegate
        withExtendedLifetime(delegate) { application.run() }
    }
}
