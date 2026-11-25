import AppKit
import SwiftUI
import UserNotifications

struct NotificationSettingsView: View {
    @State private var settings: NotificationPermission?
    @State private var working = false
    @State private var message: String?

    var body: some View {
        Section("通知") {
            Text(status)
            HStack {
                if settings?.authorizationStatus == .notDetermined {
                    Button("允许通知") { Task { await requestPermission() } }
                        .disabled(working)
                }
                Button("打开系统通知设置", action: openSystemSettings)
                    .accessibilityIdentifier("settings/notifications/open-settings")
                Button("发送测试通知") { Task { await sendTest() } }
                    .disabled(working || !canSend)
                    .accessibilityIdentifier("settings/notifications/test")
            }
            if let message {
                Text(message).font(.caption).foregroundStyle(.secondary)
            } else if settings?.authorizationStatus == .denied {
                Text("请在系统设置中开启 SVC 的“允许通知”。")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .task { await refresh() }
        .onReceive(NotificationCenter.default.publisher(for: NSApplication.didBecomeActiveNotification)) { _ in
            Task { await refresh() }
        }
        .onReceive(NotificationCenter.default.publisher(for: NSWindow.didBecomeKeyNotification)) { _ in
            Task { await refresh() }
        }
    }

    private var canSend: Bool {
        settings?.authorizationStatus == .authorized || settings?.authorizationStatus == .provisional
    }

    private var status: String {
        guard let settings else { return "正在读取通知权限…" }
        switch settings.authorizationStatus {
        case .notDetermined: return "尚未请求通知权限"
        case .denied: return "系统通知未开启"
        case .authorized:
            return settings.displaysBanners
                ? "系统通知已允许" : "已允许通知，当前不显示横幅"
        case .provisional: return "已允许静默通知"
        default: return "无法确认通知权限"
        }
    }

    private func refresh() async {
        settings = await NotificationPermission.read(from: .current())
    }

    private func requestPermission() async {
        working = true
        defer { working = false }
        do { _ = try await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) }
        catch { message = "无法请求通知授权：\(error.localizedDescription)" }
        await refresh()
    }

    private func sendTest() async {
        working = true
        defer { working = false }
        await refresh()
        guard canSend else { message = "请先在系统设置中允许 SVC 通知。"; return }
        let content = UNMutableNotificationContent()
        content.title = "SVC 测试通知"
        content.body = "指令返回后，会通过系统通知显示执行结果。"
        content.sound = .default
        do {
            try await UNUserNotificationCenter.current().add(
                UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil))
            message = "已提交测试通知，请查看系统横幅或通知中心。"
        } catch { message = "无法发送测试通知：\(error.localizedDescription)" }
    }

    private func openSystemSettings() {
        let url = URL(string: "x-apple.systempreferences:com.apple.Notifications-Settings.extension?id=dev.svc.menubar")!
        if !NSWorkspace.shared.open(url) { message = "请打开系统设置 → 通知 → SVC。" }
    }
}
