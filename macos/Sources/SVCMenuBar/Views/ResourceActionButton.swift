import AppKit
import SwiftUI

struct ResourceActionButton: NSViewRepresentable {
    let title: String
    let semanticID: String
    var enabled = true
    var bordered = true
    var symbol: String? = nil
    var accessibilityName: String? = nil
    var destructive = false
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
        button.setAccessibilityLabel(accessibilityName ?? title)
        button.setAccessibilityIdentifier(semanticID)
        button.isEnabled = enabled
        button.isBordered = bordered
        button.contentTintColor = destructive ? .systemRed : .labelColor
        button.setContentCompressionResistancePriority(bordered ? .defaultHigh : .defaultLow, for: .horizontal)
        button.image = symbol.flatMap { NSImage(systemSymbolName: $0, accessibilityDescription: nil) }
        button.imagePosition = .imageLeading
        button.font = bordered ? NSFont.systemFont(ofSize: 12) : NSFont.systemFont(ofSize: 12, weight: .semibold)
        button.toolTip = accessibilityName ?? title
        button.lineBreakMode = .byTruncatingTail
        context.coordinator.action = action
    }
    func sizeThatFits(_ proposal: ProposedViewSize, nsView: NSButton, context: Context) -> CGSize? {
        let natural = nsView.intrinsicContentSize
        return CGSize(width: min(proposal.width ?? natural.width, natural.width), height: max(22, natural.height))
    }
}
