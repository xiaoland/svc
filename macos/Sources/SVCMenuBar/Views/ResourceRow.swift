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
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                if busy { ProgressView().controlSize(.mini) }
                Text(resource.label).font(.system(size: 13, weight: .medium))
                    .lineLimit(2).help(resource.label).accessibilityAddTraits(.isHeader)
                Text(resource.scopeLabel).font(.caption).foregroundStyle(.secondary).fixedSize()
                Spacer(minLength: 4)
                ResourceActionButton(title: "", semanticID: resource.entryId + "/details", bordered: false,
                                     symbol: expanded ? "chevron.up" : "chevron.down",
                                     accessibilityName: "\(expanded ? "收起" : "展开") \(resource.label) 详情", expanded: expanded) { expanded.toggle() }
                    .frame(width: 28, height: 28)
            }
            ForEach(resource.observations) { item in
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Image(systemName: item.symbol)
                        .foregroundStyle(item.state == "satisfied" && !item.isStale ? .green : .secondary)
                        .accessibilityHidden(true)
                    Text(item.label).foregroundStyle(.secondary)
                    Spacer(minLength: 6)
                    Text(item.stateLabel)
                    if let value = item.value, !value.text.isEmpty {
                        Text(value.text).foregroundStyle(.secondary).lineLimit(expanded ? nil : 1)
                            .truncationMode(.middle).help(value.text)
                    }
                }.font(.caption)
                if expanded { observationDetails(item) }
            }
            if !resource.access.isEmpty { ResourceAccessView(addresses: resource.access, store: store) }
            ForEach(resource.facets.filter { !$0.automatic }) { facet in
                ResourceActionButton(title: "检查\(facet.label)", semanticID: resource.entryId + "/observe/" + facet.key,
                    enabled: !store.quitPending && store.refreshes[project] == nil) {
                        Task { await store.refresh(project, resource: resource.resource, observation: facet.key) }
                    }.fixedSize()
            }
            if let error = resource.error {
                DiagnosticView(title: "资源需要处理", message: error.message, semanticID: resource.entryId + "/error", context: resource.label)
            }
            if resource.needsReconciliation { recovery }
            ForEach(resource.actions) { action in
                VStack(alignment: .leading, spacing: 5) {
                    HStack(spacing: 10) {
                        ResourceActionButton(title: action.intent, semanticID: resource.entryId + "/" + action.key,
                            enabled: !busy && !store.quitPending && resource.coordination != nil && !resource.needsReconciliation,
                            accessibilityName: "\(resource.label)：\(action.intent)",
                            accessibilityHelp: "\(action.effectScope)；\(action.effectLabel)") {
                                if action.kind == "manual" { expanded = true }
                                store.perform(action, resource: resource, project: project)
                            }.frame(maxWidth: 160, alignment: .leading)
                        Spacer(minLength: 0)
                        VStack(alignment: .trailing, spacing: 2) {
                            Text(action.effectScope).lineLimit(1).truncationMode(.middle)
                            Text(action.effectLabel)
                                .foregroundStyle(action.dataEffect == "delete" ? .red : .primary)
                        }.font(.caption).foregroundStyle(.secondary)
                            .help("\(action.effectScope) · \(action.effectLabel)")
                    }
                    if expanded {
                        Text(action.effectScope).font(.caption).textSelection(.enabled)
                        if !action.traits.isEmpty { Text(action.traitLabels).font(.caption).foregroundStyle(.secondary) }
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
            }
        }.padding(.vertical, 2)
    }

    private func observationDetails(_ item: ResourceObservation) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            if let message = item.error?.message ?? item.message { Text(message).textSelection(.enabled) }
            Text(item.source.replacingOccurrences(of: "\0", with: " ")).font(.caption.monospaced()).textSelection(.enabled)
            Text("检查：\(item.checkedAt)")
            if let time = item.dataAt { Text("数据：\(time)") }
            if let instance = item.instance { Text("实例：\(instance)").textSelection(.enabled) }
        }.font(.caption2).foregroundStyle(.secondary).padding(.leading, 18)
    }

    private var recovery: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label("前次操作结果未知", systemImage: "exclamationmark.circle.fill")
                .font(.caption).foregroundStyle(.orange)
            ResourceActionButton(title: "核对并恢复…", semanticID: resource.entryId + "/reconcile",
                enabled: !busy && !store.quitPending) { confirmRecovery = true }
                .fixedSize()
                .confirmationDialog("确认原操作结果未知，重新操作可能重复？", isPresented: $confirmRecovery) {
                    Button("已核对控制者，解除阻断") { store.reconcile(resource, project: project) }
                    Button("取消", role: .cancel) {}
                } message: {
                    Text("只解除 SVC 的阻断，不终止旧进程、不重试，也不将原结果改为成功。")
                }
        }.padding(.vertical, 4)
    }
}
