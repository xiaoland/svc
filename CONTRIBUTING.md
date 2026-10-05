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

消费者需要版本相关步骤或判断时，在 `corpus/migrations/` 添加 Markdown 指导。它是可选指导，不是通用文件迁移图，也不负责 CLI 配置变换。CLI 配置采用 current-only 合同，schema 4 的人工迁移说明由[用户手册](USER_MANUAL.md)拥有，不加入自动迁移或字段别名。

## 发布边界

`main` 是唯一集成与发布源，不创建或面向长期 `develop` 或 release 分支。每个已接纳的 `main` commit 都已通过必要 CI，可进入后续发布。

维护者在首次发布前配置：

- `main` 只通过 PR 接纳，要求 CI 通过，禁止 force-push/删除，并明确狭窄 bypass 政策。
- 标准发布 workflow 的 PyPI Trusted Publishing。
- 禁止更新或删除 workflow 创建的发布 tag。

发布顺序如下：

1. 功能 PR 合并 `.changes/cli/` 或 `.changes/corpus/` 的片段。改变 Corpus 源内容时推进根 `pyproject.toml` 的 `[tool.svc.corpus].version` 与需要的迁移指导；仓库检查要求内容和版本一起变化。根 `LICENSE` 是 MIT 许可权威源，六个 Skill 和 CLI 各带逐字副本。Corpus release PR 合并前运行发布准备命令，把版本元数据和已存在的许可副本同步后与正文一起提交。
2. 维护者更新 `cli/pyproject.toml` 静态版本，准备 CLI 发布 PR 并生成 changelog：

   ```console
   pdm run towncrier build --config towncrier.cli.toml --version 16.1.0 --yes
   pdm run check
   ```

   版本须等于 package version。合并 `CLI_CHANGELOG.md` 后，验证并以 `cli-v<version>` 发布接受的 wheel。
3. Corpus 发布 PR 使用功能变更已接纳的 Corpus 版本并消费其片段：

   ```console
   pdm run towncrier build --config towncrier.corpus.toml --version 16.1.0 --yes
   pdm run prepare-corpus-release
   pdm run check
   ```

   提交并合并包含 `CORPUS_CHANGELOG.md`、六个 Skill 元数据和许可副本的 release PR 后，发布 workflow 以同一 commit 创建 `corpus-v<version>`。workflow 只读校验已提交源文件，发布物包含六个 Skill 与根 `manifest.json` 的精简 ZIP 及外部 SHA-256 校验文件；CLI wheel 不再携带 Corpus，归档重跑不得覆盖不同内容。
