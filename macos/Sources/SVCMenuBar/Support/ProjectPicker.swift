import AppKit

@MainActor
enum ProjectPicker {
    static func present(store: AppStore, sectionID: UUID? = nil, parent: NSWindow? = nil) {
        guard !store.quitPending else { return }
        let panel = NSOpenPanel()
        panel.title = "添加 SVC 项目"
        panel.prompt = "添加项目"
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = true
        let completed: (NSApplication.ModalResponse) -> Void = { response in
            if response == .OK {
                for url in panel.urls { store.addProject(url, sectionID: sectionID) }
            }
        }
        NSApp.activate(ignoringOtherApps: true)
        if let parent { panel.beginSheetModal(for: parent, completionHandler: completed) }
        else { panel.begin(completionHandler: completed) }
    }
}
