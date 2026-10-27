import AppKit
import SwiftUI

struct ResourceActionButton: NSViewRepresentable {
    let title: String
    let semanticID: String
    var enabled = true
    let action: () -> Void

    final class Coordinator: NSObject {
        var action: () -> Void
        init(action: @escaping () -> Void) { self.action = action }
        @objc func invokeAction(_ sender: NSButton) { action() }
    }
    func makeCoordinator() -> Coordinator { Coordinator(action: action) }
    func makeNSView(context: Context) -> NSButton {
        let button = NSButton(title: title, target: context.coordinator,
                              action: #selector(Coordinator.invokeAction(_:)))
        button.bezelStyle = .rounded
        button.controlSize = .small
        button.setContentHuggingPriority(.required, for: .horizontal)
        return button
    }
    func updateNSView(_ button: NSButton, context: Context) {
        button.title = title
        button.setAccessibilityLabel(title)
        button.setAccessibilityIdentifier(semanticID)
        button.isEnabled = enabled
        context.coordinator.action = action
    }
}
