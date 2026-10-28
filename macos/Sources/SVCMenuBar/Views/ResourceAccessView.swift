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
                Button {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(address, forType: .string)
                } label: { Image(systemName: "doc.on.doc").frame(width: 22, height: 22) }
                    .buttonStyle(.borderless).foregroundStyle(.secondary).help("复制访问地址")
                    .accessibilityLabel("复制访问地址").accessibilityValue(address)
            }.font(.caption)
        }
    }
}
