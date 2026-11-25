import AppKit
import SwiftUI

struct ResourceAccessView: View {
    let addresses: [String]
    let store: AppStore

    var body: some View {
        ForEach(Array(addresses.enumerated()), id: \.offset) { _, address in
            HStack(spacing: 6) {
                if let url = URL(string: address), ["http", "https"].contains(url.scheme?.lowercased() ?? "") {
                    Button {
                        if !NSWorkspace.shared.open(url) { store.notice = "无法打开：\(address)" }
                    } label: {
                        Label(address.components(separatedBy: "://").dropFirst().joined(separator: "://"),
                              systemImage: "arrow.up.right")
                            .lineLimit(1).truncationMode(.middle)
                    }.buttonStyle(.link).help(address)
                        .accessibilityLabel("打开访问地址").accessibilityValue(address)
                } else {
                    Text(address).lineLimit(1).truncationMode(.middle).textSelection(.enabled).help(address)
                }
                Spacer(minLength: 4)
                ResourceActionButton(title: "", semanticID: "access/\(address)/copy", bordered: false,
                    symbol: "doc.on.doc", accessibilityName: "复制访问地址", tint: .secondaryLabelColor,
                    accessibilityHelp: address) {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(address, forType: .string)
                    }.frame(width: 28, height: 24).accessibilityValue(address)
            }.font(.caption)
        }
    }
}
