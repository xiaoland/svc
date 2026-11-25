import AppKit
import SwiftUI

struct ResourceActionButton: View {
    let title: String
    let semanticID: String
    var enabled = true
    var bordered = true
    var symbol: String? = nil
    var accessibilityName: String? = nil
    var destructive = false
    var tint: NSColor? = nil
    var expanded: Bool? = nil
    var accessibilityHelp: String? = nil
    let action: () -> Void

    var body: some View {
        Group {
            if bordered { button.buttonStyle(.bordered) }
            else { button.buttonStyle(.borderless) }
        }
        .controlSize(.small)
        .disabled(!enabled)
        .foregroundStyle(tint.map { Color(nsColor: $0) } ?? (destructive ? .red : .primary))
        .help(accessibilityHelp ?? accessibilityName ?? title)
        .accessibilityIdentifier(semanticID)
        .accessibilityLabel(accessibilityName ?? title)
        .accessibilityValue(expanded.map { $0 ? "已展开" : "已折叠" } ?? "")
        .accessibilityHint(accessibilityHelp ?? "")
    }

    private var button: some View {
        Button(role: destructive ? .destructive : nil, action: action) {
            if let symbol, title.isEmpty {
                Image(systemName: symbol)
                    .frame(minWidth: 22, minHeight: 22)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .contentShape(Rectangle())
            } else if let symbol {
                Label(title, systemImage: symbol)
            } else {
                Text(title)
            }
        }
    }
}
