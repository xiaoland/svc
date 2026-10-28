import AppKit
import SwiftUI

struct ReceiptView: View {
    let receipt: OperationReceipt
    let expanded: Bool
    let store: AppStore

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .top, spacing: 6) {
                Image(systemName: symbol).foregroundStyle(needsAttention ? .orange : .secondary).accessibilityHidden(true)
                Text(receipt.message).lineLimit(expanded ? nil : 2).textSelection(.enabled)
            }.font(.system(size: 12)).foregroundStyle(.primary)
            if expanded {
                if let result = receipt.result {
                    ForEach(Array(result.steps.enumerated()), id: \.offset) { _, step in Text(step).font(.system(size: 12)).textSelection(.enabled) }
                    ForEach(result.observations) { item in Text("\(item.label)：\(item.stateLabel)").font(.system(size: 12)) }
                    if let operation = result.operation { Text("控制者操作：\(operation.id)").font(.system(size: 12, design: .monospaced)).textSelection(.enabled) }
                    if let execution = result.execution { Text(execution.executionId).font(.system(size: 12, design: .monospaced)).textSelection(.enabled) }
                }
                HStack {
                    Text("\(receipt.resource) · \(receipt.action) · \(receipt.date.formatted(date: .omitted, time: .standard))")
                        .font(.system(size: 12)).foregroundStyle(.primary)
                    Spacer()
                    if let path = receipt.logPath {
                        Button("查看操作日志") {
                            guard FileManager.default.fileExists(atPath: path) else {
                                store.notice = "此操作的日志文件已不存在。"; return
                            }
                            if !NSWorkspace.shared.open(URL(fileURLWithPath: path)) {
                                store.notice = "无法打开日志：\(path)"
                            }
                        }.font(.system(size: 12))
                    }
                }
            }
        }
    }

    private var needsAttention: Bool {
        guard let status = receipt.result?.status else { return true }
        return ["failed", "condition-unmet", "owner-lost", "stale", "interrupted", "absent"].contains(status)
    }

    private var symbol: String {
        if needsAttention { return "exclamationmark.circle.fill" }
        return receipt.result?.status == "completed" ? "checkmark.circle" : "info.circle"
    }
}
