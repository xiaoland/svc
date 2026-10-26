import AppKit
import SwiftUI

struct TargetRow: View {
    let target: DevTarget
    let project: String
    let store: AppStore
    @State private var expanded = false
    private var capabilityId: String { target.capability?.capabilityId ?? "" }
    private var operation: DevCommand? { store.operations[capabilityId] }
    private var receipt: OperationReceipt? { store.receipts[capabilityId] }
    private var healthColor: Color {
        switch target.health {
        case .ready: .green
        case .unhealthy: .orange
        case .unknown: .secondary
        case .notReady: .secondary
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                if operation != nil { ProgressView().controlSize(.small) }
                else { Image(systemName: target.health.symbol).foregroundStyle(healthColor) }
                VStack(alignment: .leading, spacing: 3) {
                    Text(target.target.count > 30 ? String(target.target.prefix(27)) + "…" : target.target)
                        .font(.system(.body, design: .monospaced).weight(.medium)).lineLimit(1)
                    Text(operation.map { "\($0.title)中…" } ?? target.health.rawValue)
                        .font(.caption).foregroundStyle(.secondary)
                }
                Spacer(minLength: 4)
                if target.capability?.scope != "worktree", target.capability != nil {
                    Text(target.scopeLabel).font(.caption2).foregroundStyle(.secondary)
                }
                if target.canStart {
                    Button("启动") { store.perform(.ensure, target: target, project: project) }
                        .disabled(operation != nil || store.quitPending)
                } else if target.health == .notReady && target.provision?.kind == "manual" {
                    Text("手动启动").font(.caption).foregroundStyle(.secondary)
                }
                if target.canStop {
                    Button("停止") { store.perform(.stop, target: target, project: project) }
                        .disabled(operation != nil || store.quitPending)
                }
                Button { expanded.toggle() } label: {
                    Image(systemName: expanded ? "chevron.up" : "chevron.down")
                }.buttonStyle(.borderless).accessibilityLabel("\(target.target) 详情")
            }
            .controlSize(.small)
            if let receipt {
                ReceiptView(receipt: receipt, expanded: expanded, store: store)
            }
            if expanded {
                VStack(alignment: .leading, spacing: 8) {
                    Text(target.target).font(.caption.monospaced()).textSelection(.enabled)
                    if let error = target.error { Text(error.message).font(.caption).textSelection(.enabled) }
                    if let probe = target.probe {
                        Text("\(target.scopeLabel) · \(probe.reason)").font(.caption).foregroundStyle(.secondary)
                    }
                    if target.stop?.kind == "manual" {
                        Text("此服务需要手动停止").font(.caption).foregroundStyle(.secondary)
                    } else if target.stop?.kind == "absent" {
                        Text("项目未声明停止操作").font(.caption).foregroundStyle(.secondary)
                    }
                    ForEach(Array((target.access ?? []).enumerated()), id: \.offset) { _, address in
                        HStack {
                            if let url = URL(string: address), ["http", "https"].contains(url.scheme?.lowercased() ?? "") {
                                Button { open(url) } label: {
                                    Label(address, systemImage: "arrow.up.right.square").lineLimit(1)
                                }.buttonStyle(.link).help(address)
                            } else {
                                Text(address).font(.caption.monospaced()).lineLimit(1).help(address)
                            }
                            Spacer()
                            Button {
                                NSPasteboard.general.clearContents()
                                NSPasteboard.general.setString(address, forType: .string)
                            } label: { Image(systemName: "doc.on.doc") }
                            .buttonStyle(.borderless).accessibilityLabel("复制访问地址")
                        }
                    }

                }
            }
        }
        .padding(12)
        .background(.quaternary.opacity(0.45), in: RoundedRectangle(cornerRadius: 10))
    }

    private func open(_ url: URL) {
        if !NSWorkspace.shared.open(url) { store.notice = "无法打开：\(url.absoluteString)" }
    }
}
