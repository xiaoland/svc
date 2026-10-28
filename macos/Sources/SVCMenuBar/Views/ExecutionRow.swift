import AppKit
import SwiftUI

struct ExecutionRow: View {
    let execution: ExecutionActivity
    let store: AppStore
    @State private var expanded = false
    @State private var confirmingForce = false

    var body: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Image(systemName: execution.state == "owner-lost" ? "exclamationmark.triangle" : "terminal")
                        .foregroundStyle(execution.active ? Color.accentColor : .secondary)
                        .accessibilityHidden(true)
                    Text(execution.label).font(.system(size: 13, weight: .semibold))
                        .lineLimit(1).truncationMode(.middle).help(execution.label)
                    Spacer(minLength: 4)
                    if execution.canTerminate {
                        ResourceActionButton(title: "终止", semanticID: "execution/\(execution.id)/terminate",
                            enabled: !busy && execution.terminationRequested == nil, symbol: "stop.fill",
                            accessibilityName: "终止 \(execution.label)", accessibilityHelp: "请求结束本次受管进程组") {
                                store.activity.terminate(execution, force: false, configuration: store.configuration)
                            }.fixedSize()
                    }
                    ResourceActionButton(title: "详情", semanticID: "execution/\(execution.id)/details", bordered: false,
                        symbol: expanded ? "chevron.up" : "chevron.down",
                        accessibilityName: "\(expanded ? "收起" : "展开") \(execution.label) 的执行详情", expanded: expanded) { expanded.toggle() }.fixedSize()
                }
                HStack {
                    Text(execution.stateLabel).foregroundStyle(execution.state == "owner-lost" ? .orange : Color.primary)
                    Spacer(minLength: 4)
                }.font(.caption)
                if let usage = execution.usage {
                    ProcessUsageSummary(usage: usage)
                }
                if confirmingForce {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("强制终止“\(execution.label)”的受管进程组？未完成的写入或产物可能需要人工处理。")
                            .font(.caption).foregroundStyle(.primary).fixedSize(horizontal: false, vertical: true)
                        HStack {
                            Spacer()
                            ResourceActionButton(title: "取消", semanticID: "execution/\(execution.id)/cancel-force") { confirmingForce = false }
                            ResourceActionButton(title: "强制终止", semanticID: "execution/\(execution.id)/confirm-force", enabled: !busy && execution.canTerminate,
                                destructive: true) {
                                    confirmingForce = false
                                    store.activity.terminate(execution, force: true, configuration: store.configuration)
                                }
                        }
                    }.padding(10).background(.red.opacity(0.06), in: RoundedRectangle(cornerRadius: 6))
                }
                if expanded {
                    Divider()
                    Text(execution.projectName).font(.caption).foregroundStyle(.secondary)
                    Text(execution.cwd).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                    Text("来源：\(execution.source)").font(.caption).foregroundStyle(.secondary)
                    if let usage = execution.usage { ProcessUsageDetails(usage: usage) }
                    if execution.canTerminate {
                        ResourceActionButton(title: "强制终止…", semanticID: "execution/\(execution.id)/force",
                            enabled: !busy && execution.terminationRequested != "kill", accessibilityName: "强制终止 \(execution.label)…",
                            destructive: true, accessibilityHelp: "先确认，再对本次进程组发送强制终止请求") {
                                confirmingForce = true
                            }.fixedSize()
                    } else if execution.currentlyObserved {
                        Text("当前执行未提供可验证的终止通道").font(.caption).foregroundStyle(.secondary)
                    }
                    Text(execution.argv.map(shellQuoted).joined(separator: " "))
                        .font(.caption.monospaced()).textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
                    ForEach(execution.issues, id: \.self) { Text($0).font(.caption).foregroundStyle(.orange) }
                    Text("开始于 \(execution.startedAt)\nID \(execution.id)")
                        .font(.caption2).foregroundStyle(.secondary).textSelection(.enabled)
                    HStack {
                        ForEach(Array(execution.logs.enumerated()), id: \.offset) { index, path in
                            Button(execution.logs.count == 1 ? "打开日志" : (index == 0 ? "标准输出" : "错误输出")) {
                                NSWorkspace.shared.open(URL(fileURLWithPath: path))
                            }
                        }
                        Spacer()
                        Button("复制 ID") {
                            NSPasteboard.general.clearContents()
                            NSPasteboard.general.setString(execution.id, forType: .string)
                        }
                    }.buttonStyle(.borderless).font(.caption)
                    if execution.operation == "managed" {
                        Text("终止范围限于本次进程组；脱离该组的进程与远端工作需另行检查。")
                            .font(.caption2).foregroundStyle(.secondary)
                    }
                }
            }.padding(4)
        }
    }

    private var busy: Bool { store.activity.pending.contains(execution.id) }

    private func shellQuoted(_ value: String) -> String {
        "'" + value.replacingOccurrences(of: "'", with: "'\\''") + "'"
    }
}
