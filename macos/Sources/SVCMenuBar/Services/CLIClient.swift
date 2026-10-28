import Foundation

struct CLIClient: Sendable {
    let configuration: CLIConfiguration

    func request(_ command: DevCommand, repo: String, arguments: [String] = []) async throws -> Data {
        try await Task.detached(priority: .utility) {
            try run(arguments: ["dev", command.rawValue] + arguments + ["--repo", repo, "--json"], repo: repo)
        }.value
    }

    func requestGlobal(_ command: DevCommand, arguments: [String] = []) async throws -> Data {
        try await Task.detached(priority: .utility) {
            try run(arguments: ["dev", command.rawValue] + arguments + ["--json"], repo: nil)
        }.value
    }

    private func run(arguments: [String], repo: String?) throws -> Data {
        let files = FileManager.default
        guard configuration.executable.hasPrefix("/"),
              files.isExecutableFile(atPath: configuration.executable) else {
            throw CLIError(message: "找不到可执行的 svc。请在设置中选择 CLI。")
        }
        if let repo {
            var isDirectory: ObjCBool = false
            guard files.fileExists(atPath: repo, isDirectory: &isDirectory), isDirectory.boolValue else {
                throw CLIError(message: "项目目录不存在：\(repo)")
            }
        }
        let directory = files.temporaryDirectory.appendingPathComponent("svc-app-\(UUID().uuidString)")
        try files.createDirectory(at: directory, withIntermediateDirectories: true,
                                  attributes: [.posixPermissions: 0o700])
        defer { try? files.removeItem(at: directory) }
        let stdout = directory.appendingPathComponent("stdout")
        let stderr = directory.appendingPathComponent("stderr")
        try Data().write(to: stdout)
        try Data().write(to: stderr)
        let output = try FileHandle(forWritingTo: stdout)
        let errors = try FileHandle(forWritingTo: stderr)
        defer { try? output.close(); try? errors.close() }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: configuration.executable)
        process.arguments = arguments
        process.currentDirectoryURL = URL(fileURLWithPath: repo ?? NSHomeDirectory())
        var environment = ProcessInfo.processInfo.environment
        environment["PATH"] = configuration.searchPath
        process.environment = environment
        process.standardInput = FileHandle.nullDevice
        // Files avoid pipe deadlocks and EOF waits on inherited descriptors of released servers.
        process.standardOutput = output
        process.standardError = errors
        do { try process.run() }
        catch { throw CLIError(message: "无法启动 CLI：\(error.localizedDescription)") }
        process.waitUntilExit()
        let data = try readBounded(stdout)
        if [0, 3, 4, 130].contains(process.terminationStatus), !data.isEmpty {
            return data
        }
        let diagnosticData = try readBounded(stderr)
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        if let failure = try? decoder.decode(CLIFailureResult.self, from: diagnosticData),
           failure.schemaVersion == 1 {
            throw CLIError(message: failure.error.message)
        }
        let diagnostic = String(decoding: diagnosticData, as: UTF8.self)
        throw CLIError(message: diagnostic.isEmpty
                       ? "CLI 已退出（\(process.terminationStatus)），没有返回结果。"
                       : "CLI 错误（\(process.terminationStatus)）：\n\(diagnostic.prefix(4000))")
    }

    private func readBounded(_ url: URL) throws -> Data {
        let file = try FileHandle(forReadingFrom: url)
        defer { try? file.close() }
        let data = try file.read(upToCount: 4 * 1024 * 1024 + 1) ?? Data()
        guard data.count <= 4 * 1024 * 1024 else {
            throw CLIError(message: "CLI 输出超过 4 MiB，无法安全显示。")
        }
        return data
    }
}
