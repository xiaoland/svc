import AppKit
import SwiftUI
import Observation
import Darwin

@MainActor @Observable final class ExpansionState { var expanded = false }
@MainActor final class GeometryTrace {
    var views: [String: NSView] = [:]
    func sample(since start: Double) -> [String: Any] {
        var result: [String: Any] = ["ms": (ProcessInfo.processInfo.systemUptime - start) * 1000]
        for (key, view) in views {
            let frame = view.convert(view.bounds, to: nil)
            result[key] = [frame.minY, frame.height]
        }
        return result
    }
}
struct GeometryMarker: NSViewRepresentable {
    let key: String
    let trace: GeometryTrace
    func makeNSView(context: Context) -> NSView {
        let view = NSView()
        trace.views[key] = view
        return view
    }
    func updateNSView(_ view: NSView, context: Context) {}
}
struct LayoutCase: View {
    let expansion: ExpansionState
    let trace: GeometryTrace
    let immediate: Bool
    let positive: Bool
    var binding: Binding<Bool> {
        let original = Binding(get: { expansion.expanded }, set: { expansion.expanded = $0 })
        return immediate ? original.immediateDisclosure : original
    }
    var body: some View {
        VStack(spacing: 0) {
            Color.gray.frame(height: 40).background(GeometryMarker(key: "above", trace: trace))
            if positive {
                Color.gray.frame(height: expansion.expanded ? 240 : 20)
                    .background(GeometryMarker(key: "group", trace: trace))
            } else {
                DisclosureGroup("本机压力", isExpanded: binding) {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(0..<10) { index in Text("指标 \(index) · 详细读数") }
                    }.frame(maxWidth: .infinity, alignment: .leading).padding(.top, 6)
                }
                .transaction { $0.animation = nil; $0.disablesAnimations = true }
                .padding(10).background(GeometryMarker(key: "group", trace: trace))
            }
            Color.gray.frame(height: 30).background(GeometryMarker(key: "below", trace: trace))
            ScrollView { Text("资源").frame(height: 1000) }
            Color.gray.frame(height: 24).background(GeometryMarker(key: "footer", trace: trace))
        }.frame(width: 420, height: 620)
    }
}
@main struct ObserveDisclosureLayout {
    @MainActor static func main() async throws {
        // This diagnostic owns no external work; a stalled native layout must not leave a host running.
        DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + 15) { _exit(124) }
        let destination = URL(fileURLWithPath: CommandLine.arguments[1])
        try Data("{\"stage\":\"entered main\"}".utf8).write(to: destination)
        let app = NSApplication.shared
        app.setActivationPolicy(.prohibited)
        let host = NSHostingView(rootView: AnyView(EmptyView()))
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 420, height: 620), styleMask: [.borderless], backing: .buffered, defer: false)
        window.isReleasedWhenClosed = false
        window.contentView = host
        defer { window.contentView = nil; window.close() }
        var report: [String: Any] = ["scope": "Native DisclosureGroup driven through its binding; no native input event or production view", "applicationActive": app.isActive]
        for name in ["positive", "stateWrite", "subtreeOnly"] {
            let state = ExpansionState()
            let trace = GeometryTrace()
            let composition = LayoutCase(expansion: state, trace: trace, immediate: name == "stateWrite", positive: name == "positive")
            host.rootView = AnyView(composition.id(name))
            report["stage"] = name
            try JSONSerialization.data(withJSONObject: report, options: [.sortedKeys]).write(to: destination)
            try await Task.sleep(for: .milliseconds(100))
            window.contentView?.layoutSubtreeIfNeeded()
            var directions: [[String: Any]] = []
            // One old-style expansion is enough to reproduce sibling interpolation.
            for target in (name == "subtreeOnly" ? [true] : [true, false]) {
                let start = ProcessInfo.processInfo.systemUptime
                var frames = [trace.sample(since: start)]
                withAnimation(.linear(duration: 0.4)) { composition.binding.wrappedValue = target }
                for _ in 0..<32 {
                    try await Task.sleep(for: .milliseconds(16))
                    window.contentView?.layoutSubtreeIfNeeded()
                    frames.append(trace.sample(since: start))
                }
                directions.append(["expanded": target, "frames": frames])
                report[name] = directions
                try JSONSerialization.data(withJSONObject: report, options: [.sortedKeys]).write(to: destination)
            }
            report[name] = directions
        }
        report["windowVisible"] = window.isVisible
        report["applicationActive"] = app.isActive
        let data = try JSONSerialization.data(withJSONObject: report, options: [.sortedKeys])
        try data.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
        print("captured")
    }
}
