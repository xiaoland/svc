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
                if let result = receipt.result {
                    ForEach(Array(result.steps.enumerated()), id: \.offset) { _, step in Text(step).font(.caption).textSelection(.enabled) }
                    ForEach(result.observations) { item in Text("\(item.label)：\(item.stateLabel)").font(.caption) }
                    if let operation = result.operation { Text("控制者操作：\(operation.id)").font(.caption.monospaced()).textSelection(.enabled) }
                    if let execution = result.execution { Text(execution.executionId).font(.caption2.monospaced()).textSelection(.enabled) }
                }
                HStack {
                    Text("\(receipt.resource) · \(receipt.action) · \(receipt.date.formatted(date: .omitted, time: .standard))")
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
