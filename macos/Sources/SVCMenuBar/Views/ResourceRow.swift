import AppKit
import SwiftUI

struct ResourceRow: View {
    let resource: DevResource
    let project: String
    let store: AppStore
    @State private var expanded = false
    @State private var confirmRecovery = false
    private var busy: Bool { resource.coordination.map { store.operations[$0.coordinationId] != nil } ?? false }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top) {
                if busy { ProgressView().controlSize(.small) }
                VStack(alignment: .leading, spacing: 3) {
                    Text(resource.label).font(.headline).fixedSize(horizontal: false, vertical: true)
                    Text(resource.scopeLabel).font(.caption).foregroundStyle(.secondary)
                }
                Spacer(minLength: 4)
                Button { expanded.toggle() } label: {
                    Image(systemName: expanded ? "chevron.up" : "chevron.down")
                }.buttonStyle(.borderless).accessibilityLabel("\(resource.label) 详情")
            }
            ForEach(resource.observations) { item in
                HStack(alignment: .top) {
                    Image(systemName: item.symbol).foregroundStyle(item.state == "satisfied" && !item.isStale ? .green : .secondary)
                    Text(item.label)
                    Spacer(minLength: 6)
                    VStack(alignment: .trailing, spacing: 2) {
                        Text(item.stateLabel)
                        if let value = item.value, !value.text.isEmpty {
                            Text(value.text).multilineTextAlignment(.trailing)
                        }
                    }
                }.font(.caption)
                if expanded {
                    if let message = item.error?.message ?? item.message { Text(message).font(.caption).textSelection(.enabled) }
                    Text(item.source.replacingOccurrences(of: "\0", with: " ")).font(.caption.monospaced()).textSelection(.enabled)
                    Text("检查：\(item.checkedAt)").font(.caption2).foregroundStyle(.secondary)
                    if let time = item.dataAt { Text("数据：\(time)").font(.caption2).foregroundStyle(.secondary) }
                    if let instance = item.instance { Text("实例：\(instance)").font(.caption.monospaced()).textSelection(.enabled) }
                }
            }
            ForEach(resource.facets.filter { !$0.automatic }) { facet in
                ResourceActionButton(title: "检查\(facet.label)", semanticID: resource.entryId + "/observe/" + facet.key,
                    enabled: !store.quitPending && store.refreshes[project] == nil) {
                        Task { await store.refresh(project, resource: resource.resource, observation: facet.key) }
                    }.fixedSize()
            }
            if let error = resource.error { Text(error.message).font(.caption).foregroundStyle(.orange).textSelection(.enabled) }
            if resource.needsReconciliation {
                Text("前次操作结果未知").font(.callout).foregroundStyle(.orange)
                ResourceActionButton(title: "核对并恢复…", semanticID: resource.entryId + "/reconcile",
                    enabled: !busy && !store.quitPending) { confirmRecovery = true }
                    .fixedSize()
                    .confirmationDialog("确认原操作结果未知，重新操作可能重复？", isPresented: $confirmRecovery) {
                        Button("已核对控制者，解除阻断") { store.reconcile(resource, project: project) }
                        Button("取消", role: .cancel) {}
                    } message: {
                        Text("只解除 SVC 的阻断，不终止旧进程、不重试，也不将原结果改为成功。")
                    }
            }
            ForEach(resource.actions) { action in
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        ResourceActionButton(title: action.intent, semanticID: resource.entryId + "/" + action.key,
                            enabled: !busy && !store.quitPending && resource.coordination != nil && !resource.needsReconciliation) {
                                if action.kind == "manual" { expanded = true }
                                store.perform(action, resource: resource, project: project)
                            }.fixedSize()
                        Spacer(minLength: 4)
                        Text(action.effectLabel).font(.caption)
                            .foregroundStyle(action.dataEffect == "delete" ? .red : .secondary)
                    }
                    Text(action.effectScope).font(.caption).foregroundStyle(.secondary)
                    if expanded {
                        if !action.traits.isEmpty { Text(action.traitLabels).font(.caption) }
                        if action.kind == "manual" && store.receipts[resource.entryId]?.result?.action != action.key {
                            ForEach(Array(action.steps.enumerated()), id: \.offset) { _, step in Text(step).font(.caption) }
                        }
                        if action.interruption == "wait" { Text("开始后等待实际结束").font(.caption).foregroundStyle(.secondary) }
                        if action.completion == "submitted" { Text("提交后由控制者继续处理").font(.caption).foregroundStyle(.secondary) }
                    }
                }
            }
            if let receipt = store.receipts[resource.entryId] {
                ReceiptView(receipt: receipt, expanded: expanded, store: store)
            }
            if expanded {
                if let controller = resource.controller { Text(controller).font(.caption).textSelection(.enabled) }
                if let owner = resource.coordination, owner.ownerRepo != resource.source || owner.ownerResource != resource.resource {
                    Text("共享：\(owner.ownerRepo) · \(owner.ownerResource)").font(.caption).textSelection(.enabled)
                }
                ForEach(resource.relations, id: \.self) { Text($0).font(.caption).foregroundStyle(.secondary) }
                ForEach(Array(resource.access.enumerated()), id: \.offset) { _, address in
                    HStack {
                        if let url = URL(string: address), ["http", "https"].contains(url.scheme?.lowercased() ?? "") {
                            Button(address) {
                                if !NSWorkspace.shared.open(url) { store.notice = "无法打开：\(address)" }
                            }.buttonStyle(.link).lineLimit(2)
                        } else { Text(address).font(.caption.monospaced()).textSelection(.enabled) }
                        Spacer()
                        Button {
                            NSPasteboard.general.clearContents()
                            NSPasteboard.general.setString(address, forType: .string)
                        } label: { Image(systemName: "doc.on.doc") }.buttonStyle(.borderless).accessibilityLabel("复制访问地址")
                    }
                }
            }
        }
        .padding(12)
        .background(.quaternary.opacity(0.45), in: RoundedRectangle(cornerRadius: 10))
    }
}
