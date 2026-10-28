# SVC macOS 开发预览安装

这个发布提供 macOS 14+、Apple Silicon（arm64）的 SVC App，以及同一 commit 的配套 CLI wheel。App 是 ad-hoc 签名、尚未公证的开发预览，不能当作 Developer ID 签名发行版；默认 Gatekeeper 可能阻止运行。没有提供关闭 Gatekeeper 或移除隔离标记的安装脚本。需要受信任正式分发时，应等待 Developer ID 签名与公证的版本。

先验证下载文件：

```sh
shasum -a 256 -c SHA256SUMS
```

App 使用用户安装的 SVC CLI，不内嵌 CLI，也不会自动安装 Python、创建独立环境或更改版本。CLI 需要 Python 3.11+，可通过 [GitHub latest release](https://github.com/xiaoland/svc/releases/latest) 或 [PyPI](https://pypi.org/project/sustainable-vibe-coding/) 获取，使用 mise、pipx、uv 或 pip 按自己的环境管理方式安装。发布附件中的 wheel 是可独立安装的 CLI 包。

安装 App ZIP 后，App 默认从 PATH 查找 svc，支持 mise shims、用户 .local/bin 和 Homebrew；也可在设置中选择已安装 svc 的绝对路径。未找到时会显示安装入口和重新检测操作。CLI 必须满足 release.json 记录的协议；公开 PyPI 包可能落后于开发预览，此时需要用户自行安装相应 wheel，App 不会代装。

`release.json` 记录 App 版本、Git commit、构建号、架构、签名状态和配套 wheel 文件名。此次 CLI wheel 是 macOS 预览的配套产物；macOS CD 不执行 PyPI 发布。保留 SHA256SUMS 和 release.json 可以核对后续下载或回滚。

如果你在维护这份源码，可使用本机已有 Apple Development 身份执行 `./script/build_and_run.sh --install`。该路径只安装 App 并验证签名，CLI 由用户另行安装，适用于本机迭代；开发证书不会被导出或上传。

App 0.2.0 配套 CLI 18.3.0，只接受项目配置 schema 5。已有 targets 配置需人工迁移并排空旧控制调用，步骤见[用户手册](https://github.com/xiaoland/svc/blob/main/USER_MANUAL.md#人工迁移-cli-配置)。用户自选 CLI 路径会保留，重装不会自动覆盖。
