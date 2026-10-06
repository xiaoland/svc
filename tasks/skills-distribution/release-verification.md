# Corpus Skills 发布验收

这份记录保留本次发布工具的独立验收边界，不是 Corpus 内容或 CLI 测试。发布前应在干净、已提交的工作树中执行；当前共享工作区有其它代理的未提交 CLI 修改，不能直接运行归档构建。

先验证源码合同：

```console
pdm run check-skills
pdm run check-corpus-release
pdm run ruff check tools
pdm run mypy --follow-imports=silent tools/corpus.py tools/check_skills.py tools/check_corpus_release.py tools/build_corpus_archive.py tools/prepare_corpus_release.py
```

准备并提交版本元数据后，在同一源码 commit 上构建归档：

```console
pdm run prepare-corpus-release
git add pyproject.toml corpus .changes/corpus
git commit -m 'chore(corpus): prepare Skills release'
pdm run build-corpus-archive --output /tmp/svc-corpus-16.1.0.zip
pdm run check-corpus-release --archive /tmp/svc-corpus-16.1.0.zip
unzip -l /tmp/svc-corpus-16.1.0.zip
cat /tmp/svc-corpus-16.1.0.zip.sha256
```

观察到的有效归档必须包含根 `manifest.json`、六个 `corpus/svc-*` 目录和每个 Skill 的逐字 MIT `LICENSE`；manifest 的 `repository` 为 `https://github.com/xiaoland/svc`，`revision` 必须等于当前 `HEAD` 且所有归档源文件都能由该 commit 的 `git show` 重建，所有 Skill 文件散列与源码一致，外部校验文件名为归档名追加 `.sha256`。归档不包含维护者 `AGENTS.md`、`tasks/`、CLI 或 Corpus 根导航。

同一输出路径重复构建必须保持字节一致；使用不同 revision 或不同源内容重复写入同一路径必须失败，并报告拒绝覆盖不同 release artifact。发布 workflow 必须先以 `GITHUB_SHA` 构建和校验归档，再创建或复用 `corpus-v<version>` tag；已存在 tag 指向其它 commit 时失败。Release 附件上传不使用 `--clobber`，已有附件内容不同或下载校验失败时失败，只有 ZIP 与 `.zip.sha256` 都齐全后才将 draft Release 公开。
