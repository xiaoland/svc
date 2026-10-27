# SVC macOS 开发预览安装

这个发布提供 macOS 14+、Apple Silicon（arm64）的 SVC App，以及同一 commit 的配套 CLI wheel。App 是 ad-hoc 签名、尚未公证的开发预览，不能当作 Developer ID 签名发行版；默认 Gatekeeper 可能阻止运行。没有提供关闭 Gatekeeper 或移除隔离标记的安装脚本。需要受信任正式分发时，应等待 Developer ID 签名与公证的版本。

先验证下载文件：

```sh
shasum -a 256 -c SHA256SUMS
```

配套 CLI 需要 Python 3.11+。在保存下载附件的目录创建独立环境，并安装该发布附带的 wheel；不要用旧 PyPI CLI 代替，因为本 App 要求 dev-status schema 4，dev-list／act／reconcile schema 1：

```sh
python3 -m venv "$HOME/Library/Application Support/SVC/release-cli"
"$HOME/Library/Application Support/SVC/release-cli/bin/python" -m pip install ./sustainable_vibe_coding-*.whl
"$HOME/Library/Application Support/SVC/release-cli/bin/svc" dev status --json-schema
```

最后一条结果的 `x-svc-result-schema-version` 应为 `4`。解压 App ZIP 后，按自己的系统信任策略安装 `SVC.app`。在 App 设置中选择上述 `release-cli/bin/svc` 的绝对路径；根据项目需要调整 PATH。公开包不会记录开发者或 CI runner 的路径。

`release.json` 记录 App 版本、Git commit、构建号、架构、签名状态和配套 wheel 文件名。此次 CLI wheel 是 macOS 预览的配套产物；macOS CD 不执行 PyPI 发布。保留 SHA256SUMS 和 release.json 可以核对后续下载或回滚。

如果你在维护这份源码，可使用本机已有 Apple Development 身份执行 `./script/build_and_run.sh --install`。该路径会安装稳定的配套 CLI 环境并验证签名，适用于本机迭代；开发证书不会被导出或上传。

App 0.2.0 配套 CLI 18.0.0，只接受项目配置 schema 5。已有 targets 配置需人工迁移并排空旧控制调用，步骤见[用户手册](https://github.com/xiaoland/svc/blob/main/USER_MANUAL.md#人工迁移-cli-配置)。用户自选 CLI 路径会保留，重装不会自动覆盖。
