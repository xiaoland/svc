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

框架权威源位于 `corpus/`，从 `corpus/index.md` 与各 Skill 入口进入；维护者须遵守 `corpus/AGENTS.md`。CLI workspace member 使用 `cli/src/svc_cli`，测试位于 `cli/tests`。SVC 自身持久的产品、技术与运行时事实位于 `docs/`。CLI 构建和运行均不读取 Corpus，归档不包含框架正文、模板或 catalog。

## 本机试用

先提交待试用的改动。从干净的工作树运行对应的命令，CLI、App 与 Skills 可以分别更新。CLI 安装需要 uv，App 安装需要[本机开发签名](macos/README.md)，Skills 安装只需要 Git 和 Python。

```console
./script/install_local_cli.sh
./script/build_and_run.sh --verify
python3 -m tools.install_local_skills
```

CLI 脚本归档 Git `HEAD` 的 CLI 源码，按提交保留 wheel，安装到 `${XDG_DATA_HOME:-$HOME/.local/share}/svc/dogfood`。将该目录的 `bin` 放到日常终端的 PATH 前面，并在 App 设置中填入脚本打印的绝对路径。回退 CLI 时从上次验证的提交重跑 CLI 安装，App 回退使用上次验证的源码重装。App 的实际源码 revision 记录在已安装 bundle 的 `SVCSourceRevision`。

Skills 安装器从 Git 提取并校验已提交的 Skill 目录，在 `~/.agents/skills` 建立宿主入口。首次迁移前先对比本机修改，将对应旧目录和 `.svc` 安装记录一起备份到宿主发现范围之外。每次更新后在新会话检查实际读取的 Skill。回退时运行 `python3 -m tools.install_local_skills <上一提交>`。验证公开交付时，在隔离环境构建并安装正式归档。

## 开发分支与工作树

`develop` 是日常开发和集成分支。主工作树保持检出 `develop`。范围明确的小修或局部更新可以直接在主工作树提交并推送到 `develop`。新功能、跨模块改动或需要并行推进的工作，从当前 `develop` 创建独立分支和工作树，并通过以 `develop` 为基线的 PR 合入。工作树按开发目录的约定建立，合入后清理已结束且无未提交改动的工作树和分支。

普通 CI 覆盖 PR 和推送到 `develop`、`main` 的提交。涉及 App、CLI 或相应构建文件的变更也运行 macOS 验证。发布从已通过验证的 `develop` 选定内容，通过发布 PR 合入受保护的 `main`，之后把 `main` 的发布提交同步回 `develop`。

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

Towncrier 位于 PDM quality dependency group。每项消费者可见的变化向 CLI、Corpus 或 macOS 对应队列添加简洁中文片段：

```console
printf '%s\n' '说明 CLI 变化。' > .changes/cli/123.added.md
printf '%s\n' '说明 Corpus 变化。' > .changes/corpus/123.added.md
```

使用 `added`、`changed`、`removed` 或 `fixed` 后缀，按 Behavioral SemVer 选择版本：

- `major`：不兼容地改变必要义务、默认行为、权限边界、Task Packet 语义、消费者布局、稳定 CLI 合同或支持的能力。
- `minor`：可选的向后兼容能力，或扩大可接受输入。
- `patch`：修正或澄清而保持已声明协议行为。

没有消费者可见影响则不添加片段。影响多个产品时分别添加片段。Release PR 消费片段并生成 changelog，`CHANGELOG.md` 保留发布流拆分前的共同历史。

在同一发行线内，相对于最近已发布版本评估 Behavioral SemVer。未发布版本可以继续积累变化和片段。已发布 tag 对应的版本不可复用。

CLI 输出 schema 仍维护自己的结果版本；它要求的 package major 以现行 CLI 发行项目的 `svc-cli-v<version>` 或随附同一发行项目 wheel 的 `macos-v<version>` 为基线。命令结果版本继续与发行包版本独立管理。

消费者需要版本相关步骤或判断时，在 `corpus/migrations/` 添加 Markdown 指导。它是可选指导，不是通用文件迁移图，也不负责 CLI 配置变换。CLI 配置采用 current-only 合同，schema 5 的人工迁移说明由[用户手册](USER_MANUAL.md)拥有，不加入自动迁移或字段别名。

## Release PR

`main` 是唯一发布源。先试用待发变更，将已验收的功能、静态版本和 Towncrier 片段合入 `develop`。从待发布的 `develop` 提交建立同仓库的 `release/<名称>` 分支，以 `main` 为目标。只发布部分产品时，先确认选定源码不会把其它产品的未发布合同暴露给消费者。

生成此次发布计划和选定产品的 changelog。以下命令准备三个产品，独立发布可只选需要的产品。

```console
pdm run python -m tools.release_pr prepare --base origin/main skills cli macos
```

提交生成的 `.release-plan.json`、changelog 和已消费的片段删除，审阅 Release PR，等 CI 通过后合入 `main`。发布工作流核对合入的 Release PR 和实际提交，并从同一个提交按 Skills、CLI、macOS 的顺序发布所选产品。普通同步 PR 可以推进 `main`，无需提交发布计划。出现失败时按原运行重新执行，发行 tag 与附件绑定原提交。

- CLI 的 PyPI 项目仍为 `sustainable-vibe-coding`，`cli/pyproject.toml` 使用 `1!<version>`。Release PR、changelog 和 `svc-cli-v<version>` 使用后面的 SemVer。沿用仓库 `xiaoland/svc`、workflow `publish.yml` 与环境 `release` 的 Trusted Publisher。GitHub 的 Python 下载包以 ZIP 保留 wheel 和 sdist 的原始文件名。
- Skills 版本和 tag 前缀见根 `pyproject.toml` 的 `[tool.svc.corpus]`。修改 Skill 版本或许可后，在开发分支运行 `pdm run prepare-corpus-release` 并提交结果。发布器从同一提交构建每个 Skill 的 ZIP、共同清单及校验文件。
- macOS 版本见 `macos/VERSION`，tag 为 `macos-v<version>`。App 的构建号和源码 revision 记录在发行附件中。
- 保护 `main` 的 PR 和 CI 检查。旧 `v*`、`cli-v*`、`corpus-v*` 及现行 `svc-cli-v*`、`skills-v*`、`macos-v*` 发行 tag 禁止移动或删除。

发布后把 `main` 同步回 `develop`，防止已消费的片段或旧发布计划重新进入下一轮。

## macOS 版本与发布

App 与 CLI 的职责、公开调用和运行时兼容性由 [跨单元合同](docs/product-tdd/macos-client.md) 拥有。

macOS App 使用独立的 `macos/VERSION` 与 `macos-v<version>` tag。版本遵循 SemVer；首版 `0.1.0` 是 macOS 14+ Apple Silicon 开发预览。构建号由 Git 主线提交计数生成，包和 `release.json` 记录准确 commit；本地未提交源码标记为 `-dirty`，不能发布。

源码版本见 `macos/VERSION`，公开版本见 [macOS 发行记录](MACOS_CHANGELOG.md)。本机迭代使用构建号和源码 revision 区分安装，功能变化记录在 `.changes/macos/` 的中文 Towncrier 片段中。CLI 继续按自己的兼容性规则管理版本。

普通 CI 为 App 和配套 CLI 验证原生测试、构建归档及服务验收。Release PR 选中 macOS 后发布 GitHub prerelease。重试同一次失败运行可以继续已校验的草稿。不同提交、同名不同内容或已发布但缺失附件会被拒绝。

macOS runner 使用 PDM 管理的独立 CPython 3.12.10，并在独立进程中验证 HTTPServer 能在 10 秒内构造完成。此选择处理 framework Python 在 macOS 15+ runner 上的 [loopback 反向解析延迟](https://github.com/actions/setup-python/issues/1223)；构建环境的修正不改变 CLI 的业务超时或跳过服务生命周期测试。更换解释器时，须同时保持最终 wheel 验收使用同一解释器来源。

每次发布包含 App ZIP、装有同一提交 CLI wheel 的 `SVC-CLI.zip`、`INSTALL.md`、`release.json` 和 `SHA256SUMS`。配套 CLI 的版本及原始 wheel 文件名记录在发行元数据中，接口兼容性由[跨单元合同](docs/product-tdd/macos-client.md#公开调用与兼容性)维护。

公开预览使用 ad-hoc 签名，不含本机路径或私钥，也未经公证，不能承诺通过其他机器的 Gatekeeper。Developer ID 分发与公证需要另行配置有效身份和凭据。当前工作流只需 GitHub 自带的短期 token；本机 Apple Development 私钥不上传到 CI。

本机迭代运行 `./script/build_and_run.sh --verify`，会使用钥匙串的开发身份重新安装到 `/Applications/SVC.app` 并后台启动。仅安装用 `--install`，只构建用 `--build-only`。设置与运行中的开发服务器保留；安装前的正常退出会等待未完成的控制操作。详细运行合同由 `macos/README.md` 拥有。
