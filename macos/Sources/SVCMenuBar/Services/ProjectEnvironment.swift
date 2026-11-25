import Darwin
import Foundation

/// One environment per project and explicit refresh generation, including failed preparation.
/// Periodic observation reuses it; shell startup code never runs on the main actor.
actor ProjectEnvironment {
    static let shared = ProjectEnvironment()
    private struct Key: Hashable {
        let directory: String
        let revision: Int
    }
    private var newestRevision = 0
    private var preparations: [Key: Task<[String: String], Error>] = [:]

    func resolve(_ configuration: CLIConfiguration, directory: String) async throws -> [String: String] {
        if configuration.environmentMode == .fixedPath {
            var environment = ProcessInfo.processInfo.environment
            environment["PATH"] = configuration.searchPath
            return environment
        }
        let key = Key(directory: directory, revision: configuration.environmentRevision)
        if let task = preparations[key] { return try await task.value }
        if key.revision > newestRevision {
            preparations = preparations.filter { $0.key.revision >= key.revision }
            newestRevision = key.revision
        }
        let task = Task.detached(priority: .utility) { try Self.prepare(directory: directory) }
        preparations[key] = task
        return try await task.value
    }

    private nonisolated static func loginShell() -> String? {
        var record = passwd()
        var result: UnsafeMutablePointer<passwd>?
        var buffer = [CChar](repeating: 0, count: 16384)
        return buffer.withUnsafeMutableBufferPointer { storage in
            guard getpwuid_r(getuid(), &record, storage.baseAddress!, storage.count, &result) == 0,
                  result != nil, let shell = record.pw_shell else { return nil }
            return String(cString: shell)
        }
    }

    nonisolated static func cancelPreparationsForTermination() {
        EnvironmentPreparationProcess.cancelForTermination()
    }

    nonisolated static func prepare(directory: String, shell: String? = nil,
                                    inherited: [String: String] = ProcessInfo.processInfo.environment,
                                    timeout: TimeInterval = 5) throws -> [String: String] {
        let selectedShell = shell ?? loginShell() ?? inherited["SHELL"] ?? "/bin/zsh"
        let name = URL(fileURLWithPath: selectedShell).lastPathComponent
        guard selectedShell.hasPrefix("/"), ["zsh", "bash"].contains(name),
              FileManager.default.isExecutableFile(atPath: selectedShell) else {
            throw CLIError(message: "项目环境准备失败：登录 shell 不受支持。请选择 zsh／bash，或在设置中使用自定义 PATH。")
        }
        let files = FileManager.default
        let temporary = files.temporaryDirectory.appendingPathComponent("svc-environment-\(UUID())")
        try files.createDirectory(at: temporary, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        defer { try? files.removeItem(at: temporary) }
        let environmentFile = temporary.appendingPathComponent("environment")
        let diagnostic = temporary.appendingPathComponent("startup")
        for file in [environmentFile, diagnostic] {
            guard files.createFile(atPath: file.path, contents: Data(), attributes: [.posixPermissions: 0o600]) else {
                throw CLIError(message: "无法创建私有环境准备通道。")
            }
        }
        let hooks: String
        if name == "zsh" {
            hooks = """
            if (( $+functions[precmd] )); then precmd || exit $?; fi
            if (( ${+precmd_functions} )); then
                for svc_hook in "${precmd_functions[@]}"; do
                    [[ -z "$svc_hook" ]] && continue
                    "$svc_hook" || exit $?
                done
            fi
            """
        } else {
            hooks = """
            for svc_hook in "${PROMPT_COMMAND[@]-}"; do
                [[ -z "$svc_hook" ]] && continue
                eval "$svc_hook" || exit $?
            done
            """
        }
        let script = """
        builtin cd -- "$1" || exit $?
        \(hooks)
        /usr/bin/env -0 > "$2"
        """
        let status = try EnvironmentPreparationProcess.run(
            executable: selectedShell,
            arguments: ["-l", "-i", "-c", script, "svc-environment", directory, environmentFile.path],
            environment: inherited, home: NSHomeDirectory(), diagnostic: diagnostic,
            environmentFile: environmentFile, timeout: timeout)
        guard status == 0 else {
            // Startup output can contain credentials. Do not copy it into UI errors or telemetry.
            throw CLIError(message: "项目环境准备失败（\(name)，退出 \(status)）。请在正常终端检查启动文件和项目目录钩子，再刷新重试；尚未执行项目命令。")
        }
        let values = try files.attributesOfItem(atPath: environmentFile.path)
        guard values[.type] as? FileAttributeType == .typeRegular,
              let size = values[.size] as? Int, size > 0, size <= 2 * 1024 * 1024 else {
            throw CLIError(message: "项目环境准备未返回有效环境；尚未执行项目命令。请检查 shell 启动配置后刷新。")
        }
        let data = try Data(contentsOf: environmentFile)
        guard data.last == 0 else { throw CLIError(message: "项目环境数据不完整，无法启动项目命令。") }
        var result: [String: String] = [:]
        for pair in data.split(separator: 0) {
            guard let separator = pair.firstIndex(of: 61),
                  let key = String(data: pair[..<separator], encoding: .utf8), !key.isEmpty,
                  let value = String(data: pair[pair.index(after: separator)...], encoding: .utf8) else {
                throw CLIError(message: "项目环境包含无效编码，无法启动项目命令。")
            }
            result[key] = value
        }
        guard result["PATH"]?.isEmpty == false else { throw CLIError(message: "项目环境没有有效 PATH，无法启动项目命令。") }
        return result
    }
}

/// Own a process group so a blocked startup hook cannot leave a child behind on timeout.
private final class PreparationGroups: @unchecked Sendable {
    private let lock = NSLock()
    private var pids: Set<pid_t> = []
    private var terminating = false

    func register(_ pid: pid_t) {
        lock.lock(); defer { lock.unlock() }
        pids.insert(pid)
        if terminating { kill(-pid, SIGKILL) }
    }
    func remove(_ pid: pid_t) {
        lock.lock(); defer { lock.unlock() }
        pids.remove(pid)
    }
    func poll(_ pid: pid_t, status: inout Int32) -> pid_t {
        lock.lock(); defer { lock.unlock() }
        let result = waitpid(pid, &status, WNOHANG)
        if result == pid { pids.remove(pid) }
        return result
    }
    func stop(_ pid: pid_t) {
        lock.lock(); defer { lock.unlock() }
        if pids.contains(pid) { kill(-pid, SIGKILL) }
    }
    func terminate() {
        lock.lock(); defer { lock.unlock() }
        terminating = true
        for pid in pids { kill(-pid, SIGKILL) }
    }
}

private enum EnvironmentPreparationProcess {
    private static let groups = PreparationGroups()
    static func cancelForTermination() { groups.terminate() }

    static func run(executable: String, arguments: [String], environment: [String: String], home: String,
                    diagnostic: URL, environmentFile: URL, timeout: TimeInterval) throws -> Int32 {
        var attributes: posix_spawnattr_t?
        var actions: posix_spawn_file_actions_t?
        guard posix_spawnattr_init(&attributes) == 0 else { throw CLIError(message: "无法初始化环境准备进程。") }
        defer { posix_spawnattr_destroy(&attributes) }
        guard posix_spawn_file_actions_init(&actions) == 0 else { throw CLIError(message: "无法初始化环境准备通道。") }
        defer { posix_spawn_file_actions_destroy(&actions) }
        let flags = Int16(POSIX_SPAWN_SETPGROUP | POSIX_SPAWN_CLOEXEC_DEFAULT)
        guard posix_spawnattr_setflags(&attributes, flags) == 0,
              posix_spawnattr_setpgroup(&attributes, 0) == 0,
              posix_spawn_file_actions_addchdir_np(&actions, home) == 0,
              posix_spawn_file_actions_addopen(&actions, STDIN_FILENO, "/dev/null", O_RDONLY, 0) == 0,
              posix_spawn_file_actions_addopen(&actions, STDOUT_FILENO, diagnostic.path, O_WRONLY, 0o600) == 0,
              posix_spawn_file_actions_adddup2(&actions, STDOUT_FILENO, STDERR_FILENO) == 0 else {
            throw CLIError(message: "无法配置环境准备进程。")
        }
        let argv = ([executable] + arguments).map { strdup($0) } + [nil]
        let envp = environment.map { strdup("\($0.key)=\($0.value)") } + [nil]
        defer { for item in argv + envp { free(item) } }
        var pid: pid_t = 0
        let launched = argv.withUnsafeBufferPointer { arguments in
            envp.withUnsafeBufferPointer { environment in
                posix_spawn(&pid, executable, &actions, &attributes,
                            UnsafeMutablePointer(mutating: arguments.baseAddress!),
                            UnsafeMutablePointer(mutating: environment.baseAddress!))
            }
        }
        guard launched == 0 else { throw CLIError(message: "无法启动项目环境准备进程（错误 \(launched)）。") }
        groups.register(pid)
        defer { groups.remove(pid) }
        let deadline = ProcessInfo.processInfo.systemUptime + timeout
        var status: Int32 = 0
        while true {
            let waited = groups.poll(pid, status: &status)
            if waited == pid { return (status & 0x7f) == 0 ? (status >> 8) & 0xff : 128 + (status & 0x7f) }
            if waited == -1 && errno != EINTR { throw CLIError(message: "无法等待环境准备结果。") }
            let oversized = [diagnostic, environmentFile].contains {
                ((try? FileManager.default.attributesOfItem(atPath: $0.path)[.size] as? Int) ?? 0) > 2 * 1024 * 1024
            }
            if oversized || ProcessInfo.processInfo.systemUptime >= deadline {
                groups.stop(pid)
                while waitpid(pid, &status, 0) == -1 && errno == EINTR {}
                throw CLIError(message: oversized
                    ? "项目环境准备输出超过上限，已停止；尚未执行项目命令。"
                    : "项目环境准备超时，已停止本次准备进程组；尚未执行项目命令。请检查启动文件和项目目录钩子后刷新重试。")
            }
            Thread.sleep(forTimeInterval: 0.025)
        }
    }
}
