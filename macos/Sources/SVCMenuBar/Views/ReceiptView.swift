import AppKit
import SwiftUI

struct ReceiptView: View {
    let receipt: OperationReceipt
    let expanded: Bool
    let store: AppStore

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(receipt.message).font(.caption).foregroundStyle(.secondary)
                .lineLimit(expanded ? nil : 2).textSelection(.enabled)
            if expanded {
                HStack {
                    Text("\(receipt.target) · \(receipt.command.title) · \(receipt.date.formatted(date: .omitted, time: .standard))")
                        .font(.caption2).foregroundStyle(.tertiary)
                    Spacer()
                    if let path = receipt.logPath {
                        Button("查看操作日志") {
                            guard FileManager.default.fileExists(atPath: path) else {
                                store.notice = "此操作的日志文件已不存在。"; return
                            }
                            if !NSWorkspace.shared.open(URL(fileURLWithPath: path)) {
                                store.notice = "无法打开日志：\(path)"
                            }
                        }.font(.caption)
                    }
                }
            }
        }
    }
}
