import AppKit
import SwiftUI

struct DiagnosticView: View {
    let title: String
    let message: String
    let semanticID: String
    var context: String? = nil
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Image(systemName: "exclamationmark.circle.fill").foregroundStyle(.orange).accessibilityHidden(true)
                Text(title).fontWeight(.medium)
                Spacer(minLength: 4)
                ResourceActionButton(title: "", semanticID: semanticID + "/details",
                                     bordered: false, symbol: expanded ? "chevron.up" : "chevron.down",
                                     accessibilityName: "\(expanded ? "收起" : "展开") \(context ?? title) 的诊断", expanded: expanded) {
                    expanded.toggle()
                }.frame(width: 28, height: 24)
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
                    .font(.callout).foregroundStyle(.primary).lineLimit(2).textSelection(.enabled)
            }
        }
        .padding(10)
    }
}
