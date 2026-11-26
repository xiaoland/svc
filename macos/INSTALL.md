# SVC macOS 开发预览安装

这个发布提供 macOS 14+、Apple Silicon（arm64）的 SVC App ZIP，以及同一 commit 构建的 `SVC-CLI.zip`。App 是 ad-hoc 签名、尚未公证的开发预览，默认 Gatekeeper 可能阻止运行。需要受信任正式分发时，应等待 Developer ID 签名与公证的版本。

先验证下载文件：

```sh
shasum -a 256 -c SHA256SUMS
```

App 1.0.0 配套 `sustainable-vibe-coding` 发行版 `1!1.0.0`，CLI 需要 Python 3.11+。用自己的环境管理器从 [PyPI](https://pypi.org/project/sustainable-vibe-coding/) 安装，例如 `pipx install 'sustainable-vibe-coding==1!1.0.0'`。也可以从 [GitHub Releases](https://github.com/xiaoland/svc/releases) 下载配套 ZIP，解压后安装其中的 wheel：

```sh
unzip SVC-CLI.zip -d svc-cli
pipx install ./svc-cli/sustainable_vibe_coding-*.whl
```

解压 App ZIP 后，将 `SVC.app` 放入「应用程序」。App 默认准备用户的 zsh／bash 项目终端环境，再从其 PATH 查找 `svc`。也可在设置中保留已有自定义 PATH，或选择已安装 `svc` 的绝对路径。未找到时，App 会显示安装入口和重新检测操作。CLI 必须满足 `release.json` 记录的协议，安装及升级由用户完成。

`release.json` 记录 App 版本、Git commit、构建号、架构和签名状态。`cli_archive` 是发布附件名，`cli_wheel` 是 ZIP 内的原始 wheel 文件名，`cli_version` 是 Python 发行版版本。保留 `SHA256SUMS` 和 `release.json` 可以核对后续下载或回滚。

如果你在维护这份源码，可使用本机已有 Apple Development 身份执行 `./script/build_and_run.sh --install`。该路径只安装 App 并验证签名，CLI 由用户另行安装，适用于本机迭代；开发证书不会被导出或上传。

App 1.0.0 使用项目配置 schema 5。已有 targets 配置需人工迁移并排空旧控制调用，步骤见[用户手册](https://github.com/xiaoland/svc/blob/main/USER_MANUAL.md#人工迁移-cli-配置)。重装会保留自选 CLI 路径。
