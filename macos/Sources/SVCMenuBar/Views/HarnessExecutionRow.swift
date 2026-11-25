import SwiftUI

struct HarnessExecutionRow: View {
    let execution: HarnessExecution
    let store: AppStore
    @State private var expanded = false
    @State private var confirmingStop = false
    @State private var readingLogs = false
    @State private var logs: ExecutionLogsResponse?
    private var busy: Bool { store.activity.pending.contains(execution.id) }

    var body: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    Image(systemName: execution.scope == "session" ? "person.crop.rectangle" : "terminal")
                        .foregroundStyle(.secondary).accessibilityHidden(true)
                    Text(execution.label).font(.system(size: 13, weight: .semibold))
                        .lineLimit(1).truncationMode(.middle).help(execution.label)
                    Spacer(minLength: 4)
                    if execution.canTerminate {
                        ResourceActionButton(title: "", semanticID: execution.id + "/stop", enabled: !busy,
                            symbol: "stop.fill", accessibilityName: "停止 \(execution.label)",
                            accessibilityHelp: execution.stopDescription) { confirmingStop = true }
                            .frame(width: 28, height: 24)
                    }
                    ResourceActionButton(title: "", semanticID: execution.id + "/details", bordered: false,
                        symbol: expanded ? "chevron.up" : "chevron.down",
                        accessibilityName: "\(expanded ? "收起" : "展开") \(execution.label)", expanded: expanded) { expanded.toggle() }
                        .frame(width: 28, height: 24)
                }
                HStack {
                    Text(execution.stateLabel).foregroundStyle(execution.state == "unknown" ? .orange : Color.primary)
                    Spacer()
                    Text(execution.sourceLabel).foregroundStyle(.secondary)
                }.font(.caption)
                if let usage = execution.usage { ProcessUsageSummary(usage: usage) }
                if confirmingStop {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(execution.stopDescription).font(.caption).fixedSize(horizontal: false, vertical: true)
                        HStack {
                            Spacer()
                            ResourceActionButton(title: "取消", semanticID: execution.id + "/cancel-stop") { confirmingStop = false }
                            ResourceActionButton(title: "停止", semanticID: execution.id + "/confirm-stop", enabled: !busy, destructive: true) {
                                confirmingStop = false
                                store.activity.terminateExternal(execution, configuration: store.configuration)
                            }
                        }
                    }.padding(8)
                }
                if expanded {
                    Divider()
                    if !execution.command.isEmpty {
                        Text(execution.command).font(.caption.monospaced()).textSelection(.enabled)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    Text(execution.cwd).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                    if let usage = execution.usage { ProcessUsageDetails(usage: usage) }
                    Text("来源 ID：\(execution.nativeId)").font(.caption2).foregroundStyle(.secondary).textSelection(.enabled)
                    if !execution.startedAt.isEmpty {
                        Text("开始于 \(execution.startedAt)").font(.caption2).foregroundStyle(.secondary)
                    }
                    if execution.canReadLogs {
                        ResourceActionButton(title: "", semanticID: execution.id + "/logs", enabled: !readingLogs,
                            symbol: "doc.text", accessibilityName: "查看 \(execution.label) 的日志") {
                                readingLogs = true
                                Task {
                                    defer { readingLogs = false }
                                    do {
                                        let data = try await CLIClient(configuration: store.configuration).requestGlobal(.logs, arguments: [execution.id])
                                        let response = try CLIResponse.decode(ExecutionLogsResponse.self, data: data, command: .logs)
                                        guard response.executionId == execution.id else { throw CLIError(message: "日志属于其他执行。") }
                                        logs = response
                                    } catch { store.activity.report(error.localizedDescription) }
                                }
                            }.frame(width: 28, height: 24)
                    }
                    ForEach(execution.issues, id: \.self) { Text($0).font(.caption).foregroundStyle(.orange) }
                }
            }.padding(4)
        }
        .sheet(item: $logs) { response in
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text(execution.label).font(.headline).lineLimit(1)
                    Spacer()
                    Button { logs = nil } label: { Image(systemName: "xmark") }
                        .buttonStyle(.borderless).help("关闭日志").accessibilityLabel("关闭日志")
                }
                if response.truncated { Text("显示最近一段日志").font(.caption).foregroundStyle(.secondary) }
                ScrollView {
                    Text(response.text).font(.system(.body, design: .monospaced)).textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }.padding(20).frame(minWidth: 500, idealWidth: 660, minHeight: 320, idealHeight: 480)
        }
    }
}
