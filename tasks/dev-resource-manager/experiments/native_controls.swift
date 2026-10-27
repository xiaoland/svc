// Preparation probe: semantic SwiftUI controls, actual accessory policy, external activation observer.
import AppKit
import SwiftUI
import Foundation
import ApplicationServices

let probeBundleID = "dev.svc.preparation.native-controls"

@MainActor
struct ProbeActionButton: NSViewRepresentable {
    let title: String
    let semanticID: String
    let action: () -> Void
    final class Coordinator: NSObject {
        var action: () -> Void
        init(action: @escaping () -> Void) { self.action = action }
        @objc func invokeAction(_ sender: NSButton) { action() }
    }
    func makeCoordinator() -> Coordinator { Coordinator(action: action) }
    func makeNSView(context: Context) -> NSButton {
        let button = NSButton(title: title, target: context.coordinator, action: #selector(Coordinator.invokeAction(_:)))
        button.bezelStyle = .rounded
        return button
    }
    func updateNSView(_ button: NSButton, context: Context) {
        button.title = title
        button.setAccessibilityIdentifier(semanticID)
        context.coordinator.action = action
    }
}

struct ProbeActions: View {
    let entry: String
    let perform: (String) -> Void
    var body: some View {
        VStack {
            ProbeActionButton(title: "另一个入口的安装", semanticID: "other/install") { perform("other/install") }
            ProbeActionButton(title: "选定资源的安装", semanticID: entry + "/install") { perform(entry + "/install") }
            ProbeActionButton(title: "选定资源的销毁", semanticID: entry + "/destroy") { perform(entry + "/destroy") }
        }.padding()
    }
}

@MainActor
func descendants(_ view: NSView) -> [NSView] { [view] + view.subviews.flatMap(descendants) }

@MainActor
func accessibilityElements(_ object: Any, depth: Int = 0) -> [Any] {
    guard depth < 20 else { return [] }
    let full = object as? any NSAccessibilityProtocol
    let children: [Any] = full?.accessibilityChildrenInNavigationOrder() ?? full?.accessibilityChildren() ?? []
    return [object] + children.flatMap { accessibilityElements($0, depth: depth + 1) }
}

@MainActor
func identifier(_ object: Any) -> String {
    if let element = object as? any NSAccessibilityElementProtocol {
        return element.accessibilityIdentifier?() ?? ""
    }
    return (object as? any NSAccessibilityProtocol)?.accessibilityIdentifier() ?? ""
}

@MainActor
func press(_ object: Any) -> Bool {
    if let button = object as? any NSAccessibilityButton { return button.accessibilityPerformPress() }
    return (object as? any NSAccessibilityProtocol)?.accessibilityPerformPress() ?? false
}

@MainActor
final class ProbeDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow?
    var effects: [String] = []
    var activations = 0
    var keyWindows = 0
    var tokens: [NSObjectProtocol] = []
    let destination: String

    init(destination: String) { self.destination = destination }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let nc = NotificationCenter.default
        tokens.append(nc.addObserver(forName: NSApplication.didBecomeActiveNotification, object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.activations += 1 }
        })
        tokens.append(nc.addObserver(forName: NSWindow.didBecomeKeyNotification, object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.keyWindows += 1 }
        })
        let host = NSHostingView(rootView: ProbeActions(entry: "entry-a") { self.effects.append($0) })
        let panel = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 420, height: 160),
                             styleMask: [.borderless], backing: .buffered, defer: false)
        panel.isReleasedWhenClosed = false
        panel.contentView = host
        panel.alphaValue = 0
        panel.ignoresMouseEvents = true
        panel.orderBack(nil)
        window = panel
        host.layoutSubtreeIfNeeded()
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            let buttons = descendants(host).compactMap { $0 as? NSButton }
            var seen = Set<ObjectIdentifier>()
            let elements = ([panel] + descendants(host)).flatMap { accessibilityElements($0) }
                .filter { seen.insert(ObjectIdentifier($0 as AnyObject)).inserted }
            let matches = buttons.filter { $0.accessibilityIdentifier() == "entry-a/install" }
            let pressed = matches.count == 1
            if pressed { matches[0].performClick(nil) }
            if pressed { FileManager.default.createFile(atPath: self.destination + ".pressed", contents: nil) }
            host.rootView = ProbeActions(entry: "entry-b") { self.effects.append($0) }
            host.layoutSubtreeIfNeeded()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                let rebound = descendants(host).compactMap { $0 as? NSButton }
                    .filter { $0.accessibilityIdentifier() == "entry-b/install" }
                if rebound.count == 1 { rebound[0].performClick(nil) }
            }
            try! String(ProcessInfo.processInfo.processIdentifier).write(toFile: self.destination + ".ready", atomically: true, encoding: .utf8)
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                let report: [String: Any] = [
                    "policy": NSApp.activationPolicy() == .accessory ? "accessory" : "other",
                    "matching_controls": matches.count,
                    "pressed": pressed,
                    "accessibility_identifiers": elements.map { identifier($0) },
                    "button_identifiers": buttons.map { $0.accessibilityIdentifier() },
                    "button_titles": buttons.map { $0.title },
                    "effects": self.effects,
                    "active": NSApp.isActive,
                    "activation_events": self.activations,
                    "key_window_events": self.keyWindows,
                    "key_window": panel.isKeyWindow,
                    "window_intersects_screen": NSScreen.screens.contains { $0.frame.intersects(panel.frame) },
                    "limit": "isolated NSButton bridge inside SwiftUI; rebinding tested, not the candidate resource panel"
                ]
                let data = try! JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
                try! data.write(to: URL(fileURLWithPath: self.destination))
                panel.close()
                NSApp.terminate(nil)
            }
        }
    }
}

@MainActor
func monitor(bundle: String, destination: String) throws {
    var activated = 0
    var axMatches = 0
    var axPressed = false
    var axIdentifiers: [String] = []
    var axChecked = false
    let workspace = NSWorkspace.shared
    let token = workspace.notificationCenter.addObserver(forName: NSWorkspace.didActivateApplicationNotification, object: nil, queue: .main) { event in
        let observed = event.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication
        let isProbe = observed?.bundleIdentifier == probeBundleID
        MainActor.assumeIsolated {
            if isProbe { activated += 1 }
        }
    }
    defer { workspace.notificationCenter.removeObserver(token) }
    let launcher = Process()
    launcher.executableURL = URL(fileURLWithPath: "/usr/bin/open")
    launcher.arguments = ["-g", "-n", "-W", bundle, "--args", destination]
    try launcher.run()
    let deadline = Date().addingTimeInterval(20)
    while launcher.isRunning && Date() < deadline {
        RunLoop.current.run(until: Date().addingTimeInterval(0.05))
        if !axChecked, !FileManager.default.fileExists(atPath: destination + ".pressed"), AXIsProcessTrusted(), let pidText = try? String(contentsOfFile: destination + ".ready", encoding: .utf8), let pid = Int32(pidText) {
            axChecked = true
            var visited = Set<CFHashCode>()
            func walk(_ element: AXUIElement, depth: Int = 0) -> [AXUIElement] {
                guard depth < 25, visited.count < 500, visited.insert(CFHash(element)).inserted else { return [] }
                var childValue: CFTypeRef?
                AXUIElementCopyAttributeValue(element, kAXChildrenAttribute as CFString, &childValue)
                return [element] + ((childValue as? [AXUIElement]) ?? []).flatMap { walk($0, depth: depth + 1) }
            }
            let all = walk(AXUIElementCreateApplication(pid))
            let matching = all.filter { element in
                var value: CFTypeRef?
                AXUIElementCopyAttributeValue(element, "AXIdentifier" as CFString, &value)
                let name = value as? String ?? ""
                axIdentifiers.append(name)
                return name == "entry-a/install"
            }
            axMatches = matching.count
            if matching.count == 1 { axPressed = AXUIElementPerformAction(matching[0], kAXPressAction as CFString) == .success }
        }
    }
    if launcher.isRunning { launcher.terminate(); throw NSError(domain: "probe-timeout", code: 1) }
    RunLoop.current.run(until: Date().addingTimeInterval(0.1))
    var result = try JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: destination))) as! [String: Any]
    result["external_activation_events"] = activated
    result["external_ax_trusted"] = AXIsProcessTrusted()
    result["external_ax_matching_controls"] = axMatches
    result["external_ax_pressed"] = axPressed
    result["external_ax_identifiers"] = axIdentifiers
    result["launcher_exit_code"] = launcher.terminationStatus
    let data = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data("\n".utf8))
    let passed = activated == 0 && launcher.terminationStatus == 0
        && (result["matching_controls"] as? Int == 1 || (axMatches == 1 && axPressed))
        && result["effects"] as? [String] == ["entry-a/install", "entry-b/install"]
        && result["active"] as? Bool == false && result["key_window"] as? Bool == false
        && result["activation_events"] as? Int == 0 && result["key_window_events"] as? Int == 0
    if !passed { exit(1) }
}

if CommandLine.arguments[1] == "--monitor" {
    try monitor(bundle: CommandLine.arguments[2], destination: CommandLine.arguments[3])
} else {
    let app = NSApplication.shared
    app.setActivationPolicy(.accessory)
    let delegate = ProbeDelegate(destination: CommandLine.arguments[1])
    app.delegate = delegate
    app.run()
}
