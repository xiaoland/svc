import AppKit
import SwiftUI

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate, NSPopoverDelegate, NSWindowDelegate, NSMenuItemValidation {
    let store: AppStore

    init(store: AppStore) {
        self.store = store
        super.init()
    }
    private var statusItem: NSStatusItem?
    private let popover = NSPopover()
    private var settingsWindow: NSWindow?
    private var mainWindow: MainWindowController?
    private var mainWindowOpen = false
    private var settingsWindowOpen = false
    private var panelShowsResources = true

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
        }, openMainWindow: { [weak self] in
            self?.showMainWindow()
        }, resourcePageChanged: { [weak self] value in
            self?.panelShowsResources = value
            self?.updatePanelObservation()
        }))
        controller.sizingOptions = [.preferredContentSize]
        popover.contentViewController = controller
        if !ProcessInfo.processInfo.arguments.contains("--background") { showMainWindow() }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        showMainWindow()
        return false
    }

    @objc private func showMainWindow() {
        popover.performClose(nil)
        if mainWindow == nil {
            mainWindow = MainWindowController(store: store, openSettings: { [weak self] in
                self?.showSettings()
            }, closed: { [weak self] in
                self?.mainWindowOpen = false
                self?.updateActivationPolicy()
            })
        }
        mainWindowOpen = true
        updateActivationPolicy()
        NSApp.activate(ignoringOtherApps: true)
        mainWindow?.present()
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

    func popoverDidShow(_ notification: Notification) { updatePanelObservation() }

    func popoverDidClose(_ notification: Notification) {
        store.setObservationDemand(.panel, resources: nil)
    }

    private func updatePanelObservation() {
        store.setObservationDemand(.panel, resources: popover.isShown && !NSApp.isHidden ? panelShowsResources : nil)
    }

    func applicationDidHide(_ notification: Notification) {
        updatePanelObservation()
        mainWindow?.updateObservationDemand()
    }

    func applicationDidUnhide(_ notification: Notification) {
        updatePanelObservation()
        mainWindow?.updateObservationDemand()
    }

    private func updateActivationPolicy() {
        NSApp.setActivationPolicy(mainWindowOpen || settingsWindowOpen ? .regular : .accessory)
    }

    @objc private func showSettings() {
        popover.performClose(nil)
        if settingsWindow == nil {
            let window = NSWindow(contentViewController: NSHostingController(rootView: SettingsView(store: store)))
            window.title = "SVC 设置"
            window.styleMask = [.titled, .closable]
            window.isReleasedWhenClosed = false
            window.delegate = self
            window.center()
            settingsWindow = window
        }
        settingsWindowOpen = true
        updateActivationPolicy()
        NSApp.activate(ignoringOtherApps: true)
        settingsWindow?.makeKeyAndOrderFront(nil)
    }

    func windowWillClose(_ notification: Notification) {
        settingsWindowOpen = false
        updateActivationPolicy()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    @objc private func addProject() {
        ProjectPicker.present(store: store, parent: mainWindow?.window?.isKeyWindow == true ? mainWindow?.window : nil)
    }

    @objc private func refreshCurrentPage() {
        if mainWindow?.window?.isKeyWindow == true {
            mainWindow?.refreshCurrentPage()
        } else {
            Task {
                await store.activity.refresh(store.configuration)
                if panelShowsResources { await store.refreshAll() }
            }
        }
    }

    func validateMenuItem(_ item: NSMenuItem) -> Bool {
        if item.action == #selector(addProject) { return !store.quitPending }
        if item.action == #selector(refreshCurrentPage) {
            return !store.quitPending && !store.activity.refreshing && store.refreshes.isEmpty
        }
        return true
    }

    private func installMenu() {
        let main = NSMenu()
        let appItem = main.addItem(withTitle: "SVC", action: nil, keyEquivalent: "")
        let appMenu = NSMenu(title: "SVC")
        appItem.submenu = appMenu
        let mainWindow = appMenu.addItem(withTitle: "打开主窗口", action: #selector(showMainWindow), keyEquivalent: "0")
        mainWindow.target = self
        let settings = appMenu.addItem(withTitle: "设置…", action: #selector(showSettings), keyEquivalent: ",")
        settings.target = self
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "隐藏 SVC", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        let hideOthers = appMenu.addItem(withTitle: "隐藏其他", action: #selector(NSApplication.hideOtherApplications(_:)), keyEquivalent: "h")
        hideOthers.keyEquivalentModifierMask = [.command, .option]
        appMenu.addItem(withTitle: "显示全部", action: #selector(NSApplication.unhideAllApplications(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "退出 SVC", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let file = NSMenu(title: "文件")
        main.addItem(withTitle: "文件", action: nil, keyEquivalent: "").submenu = file
        let add = file.addItem(withTitle: "添加项目…", action: #selector(addProject), keyEquivalent: "o")
        add.target = self
        let refresh = file.addItem(withTitle: "刷新", action: #selector(refreshCurrentPage), keyEquivalent: "r")
        refresh.target = self
        file.addItem(.separator())
        file.addItem(withTitle: "关闭窗口", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
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
        let windows = NSMenu(title: "窗口")
        main.addItem(withTitle: "窗口", action: nil, keyEquivalent: "").submenu = windows
        windows.addItem(withTitle: "最小化", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        windows.addItem(withTitle: "缩放", action: #selector(NSWindow.performZoom(_:)), keyEquivalent: "")
        windows.addItem(.separator())
        windows.addItem(withTitle: "全部前置", action: #selector(NSApplication.arrangeInFront(_:)), keyEquivalent: "")
        NSApp.windowsMenu = windows
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
