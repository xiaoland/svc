# 贡献 SVC

SVC 是 source-first 的协议。贡献完成意味着行为影响、发布说明与验证证据可审查，而不仅是代码在本地通过。

## 安全问题

疑似漏洞遵循[安全政策](SECURITY.md)，不要在公开 issue 或 PR 发布可利用细节。

## 准备与验证

使用 Python 3.11+ 和 PDM 2.28+：

```console
pdm install -d -G test -G quality
pdm run check
pdm build -p cli
pdm run svc --help
```

框架权威源位于 `corpus/`，从 `corpus/index.md` 与六个 Skill 入口进入；维护者须遵守 `corpus/AGENTS.md`。CLI workspace member 使用 `cli/src/svc_cli`，测试位于 `cli/tests`。SVC 自身持久的产品、技术与运行时事实位于 `docs/`。CLI 构建和运行均不读取 Corpus，归档不包含框架正文、模板或 catalog。

## 提交说明

使用以下语法，人类可读的说明写中文：

```text
feat|fix|ref|docs|chore(<scope>): <summary>
```

首行简洁；正文 bullet 只保留难以重建的上下文、约束或验证结果。例如：

```text
feat(run): 增加命名运行入口
docs(protocol): 明确项目采用权限
ref(cli): 移除框架内容依赖
```

`update files` 缺少类型、scope 与意图；`feat: migration` 缺少 scope。Commit type 只是导航元数据，不决定发布影响或下个版本。

## 声明行为影响

Towncrier 位于 PDM quality dependency group。每项消费者可见的 CLI 或 Corpus 变化向对应产品添加简洁中文片段：

```console
printf '%s\n' '说明 CLI 变化。' > .changes/cli/123.added.md
printf '%s\n' '说明 Corpus 变化。' > .changes/corpus/123.added.md
```

使用 `added`、`changed`、`removed` 或 `fixed` 后缀，按 Behavioral SemVer 选择版本：

- `major`：不兼容地改变必要义务、默认行为、权限边界、Task Packet 语义、消费者布局、稳定 CLI 合同或支持的能力。
- `minor`：可选的向后兼容能力，或扩大可接受输入。
- `patch`：修正或澄清而保持已声明协议行为。

没有消费者可见影响则不添加片段；影响两产品则向两队列各添加片段。功能 PR 不修改生成的 changelog；`CHANGELOG.md` 保留发布流拆分前的共同历史。

版本相对于最近的已发布版本评估，不能把同一未发布开发线中的每个提交或功能当成一次发布。尚未发布的目标版本可以持续积累变化和片段；例如本轮 v15 同时包含布局拆分、Skills 分发、Verification 与 Agent 协作改进。已发布 tag 对应的版本不能通过后续源码修改重新使用。

CLI 输出 schema 仍维护自己的结果版本；它要求的 package major 以最近已发布的 `v<version>` 或 `cli-v<version>` 为基线，而不是分支中的暂定 package version。Corpus 的 `corpus-v<version>` 不参与 CLI 的 major 判定。

消费者需要版本相关步骤或判断时，在 `corpus/migrations/` 添加 Markdown 指导。它是可选指导，不是通用文件迁移图，也不负责 CLI 配置变换。CLI 配置采用 current-only 合同，schema 4 的人工迁移说明由[用户手册](USER_MANUAL.md)拥有，不加入自动迁移或字段别名。

## 发布边界

`main` 是唯一集成与发布源，不创建或面向长期 `develop` 或 release 分支。每个已接纳的 `main` commit 都已通过必要 CI，可进入后续发布。

维护者在首次发布前配置：

- `main` 只通过 PR 接纳，要求 CI 通过，禁止 force-push/删除，并明确狭窄 bypass 政策。
- 标准发布 workflow 的 PyPI Trusted Publishing。
- 禁止更新或删除 workflow 创建的发布 tag。

发布顺序如下：

1. 功能 PR 合并 `.changes/cli/` 或 `.changes/corpus/` 的片段。改变 Corpus 源内容时维护根 `pyproject.toml` 的 `[tool.svc.corpus].version` 与需要的迁移指导：未发布目标可以继续积累变更，已发布版本的源内容变化需要新的目标版本。版本检查需要完整的发行 tags；CI 使用完整 Git 历史，发布比较采用 `v<version>` 与 `corpus-v<version>` 对应的源码。根 `LICENSE` 是 MIT 许可权威源，六个 Skill 和 CLI 各带逐字副本。Corpus release PR 合并前运行发布准备命令，把版本元数据和已存在的许可副本同步后与正文一起提交。
2. 维护者更新 `cli/pyproject.toml` 静态版本，准备 CLI 发布 PR 并生成 changelog：

   ```console
   pdm run towncrier build --config towncrier.cli.toml --version 16.0.0 --yes
   pdm run check
   ```

   版本须等于 package version。合并 `CLI_CHANGELOG.md` 后，验证并以 `cli-v<version>` 发布接受的 wheel。
3. Corpus 发布 PR 使用功能变更已接纳的 Corpus 版本并消费其片段：

   ```console
   pdm run towncrier build --config towncrier.corpus.toml --version 16.0.0 --yes
   pdm run prepare-corpus-release
   pdm run check
   ```

   可先用 `pdm run build-corpus-archive --output-dir /tmp/svc-skills-release` 构建全部附件，再用 `pdm run check-corpus-release --artifacts /tmp/svc-skills-release` 校验。构建要求版本、Skill 元数据和正文已提交且与 HEAD 相符。

   提交并合并包含 `CORPUS_CHANGELOG.md`、六个 Skill 元数据和许可副本的 release PR 后，发布 workflow 以同一 commit 创建 `corpus-v<version>`。workflow 只读校验已提交源文件，从 v16 起，发布物为六个 `<skill-name>-<version>.zip` 及各自 `.sha256`，加上 `svc-skills-<version>.json` 与其 `.sha256`；每个 ZIP 仅含 `<skill-name>/` 的完整源码目录，外部 schema-2 catalog 记录共同发布身份、逐文件摘要和各 ZIP 摘要，不再生成整体 Corpus ZIP；CLI wheel 不再携带 Corpus，归档重跑不得覆盖不同内容。


## macOS 版本与发布

App 与 CLI 的职责、公开调用和运行时兼容性由 [跨单元合同](docs/product-tdd/macos-client.md) 拥有。

macOS App 使用独立的 `macos/VERSION` 与 `macos-v<version>` tag。版本遵循 SemVer；首版 `0.1.0` 是 macOS 14+ Apple Silicon 开发预览。构建号由 Git 主线提交计数生成，包和 `release.json` 记录准确 commit；本地未提交源码标记为 `-dirty`，不能发布。

功能变化向 `.changes/macos/` 添加中文 Towncrier 片段。准备发布时更新 `macos/VERSION`，在仓库根目录执行：

```console
mkdir -p .changes/macos
pdm run towncrier build --config towncrier.macos.toml --version 0.1.0 --yes
pdm run check
SVC_TEST_CLI="$PWD/.venv/bin/svc" swift test --package-path macos
```

版本须等于 `macos/VERSION`。将生成的 `MACOS_CHANGELOG.md` 与版本、实现一起通过 PR 合入 `main`；macOS workflow 先执行仓库检查、后台原生测试和配套 wheel 的真实服务验收，再发布 GitHub prerelease。普通功能合并只验证和归档，只有发布记录变更或在 `main` 手动运行 workflow 才发布。重试同一次失败运行可以继续已校验的草稿；不同 commit、同名不同内容或已发布但缺失附件均会被拒绝，不移动 tag，不覆盖附件。新的发布使用新版本。

macOS runner 使用 PDM 管理的独立 CPython 3.12.10，并在独立进程中验证 HTTPServer 能在 10 秒内构造完成。此选择处理 framework Python 在 macOS 15+ runner 上的 [loopback 反向解析延迟](https://github.com/actions/setup-python/issues/1223)；构建环境的修正不改变 CLI 的业务超时或跳过服务生命周期测试。更换解释器时，须同时保持最终 wheel 验收使用同一解释器来源。

每次发布包含 App ZIP、同一 commit 的 CLI wheel、`INSTALL.md`、`release.json` 和 `SHA256SUMS`。macOS CD 不发布 PyPI；CLI schema 或 package 变化仍遵守 CLI 的版本规则。当前 dev-status schema 3 要求配套 CLI 17.0.0，预览安装时必须使用随附 wheel，不能用旧版 PyPI CLI 替代。

公开预览使用 ad-hoc 签名，不含本机路径或私钥，也未经公证，不能承诺通过其他机器的 Gatekeeper。Developer ID 分发与公证需要另行配置有效身份和凭据。当前工作流只需 GitHub 自带的短期 token；本机 Apple Development 私钥不上传到 CI。

本机迭代运行 `./script/build_and_run.sh --verify`，会使用钥匙串的开发身份重新安装到 `/Applications/SVC.app` 并后台启动。仅安装用 `--install`，只构建用 `--build-only`。设置与运行中的开发服务器保留；安装前的正常退出会等待未完成的控制操作。详细运行合同由 `macos/README.md` 拥有。
