import AppKit
import SwiftUI

struct PanelCard: ViewModifier {
    @Environment(\.colorSchemeContrast) private var contrast

    func body(content: Content) -> some View {
        content
            .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 10))
            .overlay {
                RoundedRectangle(cornerRadius: 10)
                    .strokeBorder(contrast == .increased ? Color.primary : Color(nsColor: .separatorColor), lineWidth: 1)
            }
    }
}
