import SwiftUI

struct CLIInstallLinks: View {
    var body: some View {
        HStack {
            Link("GitHub Releases", destination: URL(string: "https://github.com/xiaoland/svc/releases/latest")!)
            Link("PyPI", destination: URL(string: "https://pypi.org/project/sustainable-vibe-coding/")!)
        }
    }
}

struct CLISetupView: View {
    let openSettings: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("请先安装 SVC CLI", systemImage: "terminal")
                .font(.headline)
            CLIInstallLinks()
            Button("选择 CLI 或重新检测…", action: openSettings)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .accessibilityIdentifier("cli/setup")
    }
}
