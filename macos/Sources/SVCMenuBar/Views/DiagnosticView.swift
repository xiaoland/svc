import AppKit
import SwiftUI

struct DiagnosticView: View {
    let title: String
    let message: String
    let semanticID: String
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Image(systemName: "exclamationmark.circle.fill").foregroundStyle(.orange)
                Text(title).fontWeight(.medium)
                Spacer(minLength: 4)
                ResourceActionButton(title: expanded ? "收起" : "详情", semanticID: semanticID + "/details",
                                     bordered: false, symbol: expanded ? "chevron.up" : "chevron.down") {
                    expanded.toggle()
                }.fixedSize()
            }.font(.caption)
            if expanded {
                ScrollView {
                    Text(message).font(.caption).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading)
                }.frame(maxHeight: 150)
                Button("复制诊断") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(message, forType: .string)
                }.buttonStyle(.borderless).font(.caption)
            } else {
                Text(message.split(whereSeparator: { $0 == "。" || $0 == "\n" }).first.map(String.init) ?? message)
                    .font(.caption).foregroundStyle(.secondary).lineLimit(2).textSelection(.enabled)
            }
        }
        .padding(10)
        .background(.orange.opacity(0.06), in: RoundedRectangle(cornerRadius: 7))
    }
}
