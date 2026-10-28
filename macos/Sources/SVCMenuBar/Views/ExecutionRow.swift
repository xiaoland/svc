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
                    Image(systemName: execution.state == "owner-lost" ? "exclamationmark.triangle" : (execution.active ? "terminal" : "checkmark.circle"))
                        .foregroundStyle(execution.active ? Color.accentColor : .secondary)
                        .accessibilityHidden(true)
                    Text(execution.label).font(.system(size: 13, weight: .semibold))
                        .lineLimit(1).truncationMode(.middle).help(execution.label)
                    Spacer(minLength: 4)
                    ResourceActionButton(title: "", semanticID: "execution/\(execution.id)/details",
                        symbol: expanded ? "chevron.up" : "chevron.down",
                        accessibilityName: "\(expanded ? "收起" : "展开") \(execution.label) 的执行详情", expanded: expanded) { expanded.toggle() }
                }
                HStack {
                    Text(execution.stateLabel).foregroundStyle(execution.state == "owner-lost" ? .orange : Color.primary)
                    Spacer(minLength: 4)
                    Text(execution.source).foregroundStyle(.secondary).lineLimit(1)
                }.font(.caption)
                Text(execution.projectName).font(.caption).foregroundStyle(.secondary)
                    .help(execution.projectPath ?? "启动时没有登记项目归属。")
                Text(execution.cwd).font(.caption).foregroundStyle(.secondary)
                    .lineLimit(1).truncationMode(.middle).help(execution.cwd)
                if let usage = execution.usage {
                    ProcessUsageView(usage: usage)
                }
                if execution.canTerminate {
                    HStack(spacing: 8) {
                        Text("受管进程组").font(.caption2).foregroundStyle(.secondary)
                        Spacer()
                        ResourceActionButton(title: "终止", semanticID: "execution/\(execution.id)/terminate",
                            enabled: !busy && execution.terminationRequested == nil, symbol: "stop.fill",
                            accessibilityName: "终止 \(execution.label)", accessibilityHelp: "请求结束本次受管进程组") {
                                store.activity.terminate(execution, force: false, configuration: store.configuration)
                            }
                        ResourceActionButton(title: "强制终止…", semanticID: "execution/\(execution.id)/force",
                            enabled: !busy && execution.terminationRequested != "kill", accessibilityName: "强制终止 \(execution.label)…",
                            destructive: true, accessibilityHelp: "先确认，再对本次进程组发送强制终止请求") {
                                confirmingForce = true
                            }
                    }
                } else if execution.currentlyObserved {
                    Text("当前执行未提供可验证的终止通道").font(.caption2).foregroundStyle(.secondary)
                }
                if confirmingForce {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("强制终止“\(execution.label)”的受管进程组？未完成的写入或产物可能需要人工处理。")
                            .font(.caption).foregroundStyle(.primary)
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
                    if let usage = execution.usage {
                        Text("页面读入 \(activityPageRate(usage.pageinsPerSecond))")
                            .font(.caption).foregroundStyle(.secondary)
                            .help("包含文件页读入，不能解释为此项目的 swap 换入。")
                    }
                    Text(execution.argv.map(shellQuoted).joined(separator: " "))
                        .font(.caption.monospaced()).textSelection(.enabled)
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
