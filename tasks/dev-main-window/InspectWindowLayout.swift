import AppKit
import SwiftUI

/// One bounded, offscreen inspection of the actual product controller.
/// No application event loop, visible window, UI input or project probes.
@main
struct InspectWindowLayout {
    @MainActor static func main() throws {
        let app = NSApplication.shared
        app.setActivationPolicy(.prohibited)
        let suite = "svc-window-layout-\(UUID().uuidString)"
        let preferences = UserDefaults(suiteName: suite)!
        defer { preferences.removePersistentDomain(forName: suite) }
        let store = AppStore(preferences: preferences)
        let savedFrame = UserDefaults.standard.object(forKey: "NSWindow Frame SVCMainWindow")
        let controller = MainWindowController(store: store, openSettings: {}, closed: {})
        let window = controller.window!
        defer {
            window.setFrameAutosaveName("")
            if let savedFrame { UserDefaults.standard.set(savedFrame, forKey: "NSWindow Frame SVCMainWindow") }
            else { UserDefaults.standard.removeObject(forKey: "NSWindow Frame SVCMainWindow") }
        }
        var snapshots: [[String: Any]] = []
        for width: CGFloat in [1040, 740] {
            window.setContentSize(NSSize(width: width, height: 720))
            window.contentView?.layoutSubtreeIfNeeded()
            window.displayIfNeeded()
            RunLoop.current.run(until: Date(timeIntervalSinceNow: 0.2))
            let items = window.toolbar?.items ?? []
            snapshots.append([
                "contentWidth": window.contentView?.bounds.width ?? 0,
                "contentHeight": window.contentView?.bounds.height ?? 0,
                "toolbarStyle": window.toolbarStyle.rawValue,
                "fullSizeContentView": window.styleMask.contains(.fullSizeContentView),
                "windowVisible": window.isVisible,
                "applicationActive": app.isActive,
                "toolbarItems": items.map { ["identifier": $0.itemIdentifier.rawValue, "label": $0.label] },
                "hostType": String(describing: type(of: window.contentViewController!))
            ])
            if CommandLine.arguments.count > 1, let frame = window.contentView?.superview {
                frame.layoutSubtreeIfNeeded()
                if let bitmap = frame.bitmapImageRepForCachingDisplay(in: frame.bounds) {
                    frame.cacheDisplay(in: frame.bounds, to: bitmap)
                    if let png = bitmap.representation(using: .png, properties: [:]) {
                        let destination = URL(fileURLWithPath: CommandLine.arguments[1])
                            .appendingPathComponent("main-\(Int(width)).png")
                        try png.write(to: destination)
                    }
                }
            }
        }
        let data = try JSONSerialization.data(withJSONObject: snapshots, options: [.prettyPrinted, .sortedKeys])
        print(String(decoding: data, as: UTF8.self))
    }
}
