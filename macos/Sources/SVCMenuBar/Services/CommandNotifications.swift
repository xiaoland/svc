import Foundation
import UserNotifications

struct NotificationPermission: Sendable {
    let authorizationStatus: UNAuthorizationStatus
    let displaysBanners: Bool
}

// Start SDK calls on the main actor and resume with value results.
@MainActor
extension UNUserNotificationCenter {
    func svcPermission() async -> NotificationPermission {
        await withCheckedContinuation { continuation in
            getNotificationSettings { @Sendable settings in
                continuation.resume(returning: NotificationPermission(
                    authorizationStatus: settings.authorizationStatus,
                    displaysBanners: settings.alertSetting == .enabled && settings.alertStyle != .none
                ))
            }
        }
    }

    func svcRequestPermission() async throws -> Bool {
        try await withCheckedThrowingContinuation { continuation in
            requestAuthorization(options: [.alert, .sound]) { @Sendable granted, error in
                if let error { continuation.resume(throwing: error) }
                else { continuation.resume(returning: granted) }
            }
        }
    }

    func svcPost(_ content: UNNotificationContent) async throws {
        let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            add(request) { @Sendable error in
                if let error { continuation.resume(throwing: error) }
                else { continuation.resume() }
            }
        }
    }
}

@MainActor
final class CommandNotifications: NSObject, UNUserNotificationCenterDelegate {
    private let center = UNUserNotificationCenter.current()
    private let openResult: (String, String) -> Void
    private let reportError: (String) -> Void
    private var authorizationRequest: Task<Bool, Error>?

    init(openResult: @escaping (String, String) -> Void, reportError: @escaping (String) -> Void) {
        self.openResult = openResult
        self.reportError = reportError
        super.init()
        center.delegate = self
    }

    func deliver(_ receipt: OperationReceipt, resource: String, action: String) async {
        let content = Self.content(for: receipt, resource: resource, action: action)
        let settings = await center.svcPermission()
        if settings.authorizationStatus == .notDetermined {
            // Permission may wait for the person; it must not keep the command busy.
            Task { await authorizeAndPost(content) }
        } else if settings.authorizationStatus != .denied {
            await post(content)
        }
    }

    private func authorizeAndPost(_ content: UNNotificationContent) async {
        do {
            // Concurrent command results share the system's one permission decision.
            let request = authorizationRequest ?? Task { try await center.svcRequestPermission() }
            authorizationRequest = request
            defer { authorizationRequest = nil }
            guard try await request.value else {
                reportError("执行结果通知尚未允许，可在系统设置的“通知 > SVC”中开启。")
                return
            }
            await post(content)
        } catch {
            reportError("无法取得通知授权：\(error.localizedDescription)")
        }
    }

    private func post(_ content: UNNotificationContent) async {
        do {
            try await center.svcPost(content)
        } catch {
            reportError("无法发送执行结果通知：\(error.localizedDescription)")
        }
    }

    static func content(for receipt: OperationReceipt, resource: String, action: String) -> UNMutableNotificationContent {
        let content = UNMutableNotificationContent()
        let project = URL(fileURLWithPath: receipt.projectPath).lastPathComponent
        let result: String
        switch receipt.result?.status {
        case "completed": result = "执行完成"
        case "ready": result = "已就绪"
        case "accepted": result = "请求已接受"
        case "reused": result = "已复用现有资源"
        case "acknowledged": result = "已确认未知结果"
        case "nothing-to-reconcile": result = "无需恢复确认"
        case "manual": result = "需要人工操作"
        case "busy": result = "资源正忙"
        case "condition-unmet": result = "完成条件未满足"
        case "owner-lost": result = "执行结果未知"
        case "interrupted": result = "执行已中断"
        case "stale": result = "声明已变更"
        case "absent": result = "操作不可用"
        case "failed": result = "执行失败"
        default: result = "未能确认执行结果"
        }
        content.title = result
        content.subtitle = "\(project) · \(resource)"
        content.body = "\(action)\n\(receipt.message.prefix(240))"
        content.sound = .default
        content.threadIdentifier = receipt.projectPath
        content.userInfo = ["projectPath": receipt.projectPath]
        return content
    }

    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter, willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        [.banner, .list, .sound]
    }

    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse
    ) async {
        guard response.actionIdentifier == UNNotificationDefaultActionIdentifier,
              let path = response.notification.request.content.userInfo["projectPath"] as? String else { return }
        let content = response.notification.request.content
        let date = response.notification.date.formatted(date: .abbreviated, time: .shortened)
        let summary = "通知回执（\(date)）\n\(content.subtitle) · \(content.title)\n\(content.body)"
        await MainActor.run { openResult(path, summary) }
    }
}
