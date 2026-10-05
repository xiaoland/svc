# Skills 分发实现验收

日期：2026-10-05。本次实现已获用户授权，MIT 已明确选定；未提交、推送或发布。以下区分本地观察与尚未执行的发布或宿主行为。

`SVC_BASE_REF=HEAD pdm run check` 最终通过：格式、Ruff、51 个源码文件的 mypy、7 条 import-linter 合同、Skills 资源/版本/许可与输出 schema 检查，以及 `cli/tests/` 中 239 个测试全部通过。没有新增根或 Corpus 测试。`git diff --check` 通过，锁文件仅更新 CLI 的两处版本记录，没有升级其它依赖。

`pdm build -p cli` 生成 16.1.0 wheel 与 sdist。系统 Python 使用 `pip wheel --no-cache-dir --no-deps` 在独立构建环境从该 sdist 重建 wheel 成功。两个 wheel 都携带逐字 MIT LICENSE、MIT SPDX metadata 和当前 Skills 输出 schema，均不携带 Corpus 正文、SKILL.md 或 catalog；sdist 同样不携带 Corpus。此结果覆盖独立发行输入，未执行 PyPI 上传。

隔离端到端实验将当前 Corpus 复制到临时 Git 仓库并提交，在该 fixture commit 上生成、校验 ZIP，随后用 CLI 的真实归档解析器读取。它验证六个 Skill、manifest、checksum 和准确源码 revision 的关系；真实工作区保持未提交，不能直接生成正式绑定当前实现的 release artifact。发布工具的边界与命令见[发布验收](release-verification.md)。

同一实验在全新 venv 中安装当前 CLI wheel，以临时消费者项目运行真实 `svc skills` 命令。六个 Skill 在 Codex 与 Claude 目录逐文件、逐字节匹配，包含 MIT；计划阶段不写文件，精确 apply 后才报告实际版本。重复安装、只读 check、独立采用、消费者内容保留、额外文件引发的更新拒绝、移除后采用块保留、取消采用和重装均通过。临时 fixture、消费者、venv 与实验脚本已清理。

Vercel Skills 1.7.0、OpenSkills 1.5.0 对单 Skill、六 Skill 和当前 Git 根布局的隔离安装已实际验证；manager 自有 metadata 不计入源码字节比较。Codex 0.159.3 app-server 的只读 `skills/list` 实际发现六个 enabled 项目 Skill，描述和加载路径匹配源码。详细观察见[管理器与宿主记录](manager-verification.md)。

未执行真实 GitHub Release workflow、固定远端 tag 安装或实际全局目录写入。Claude 运行时发现与模型在任务中的自动触发未验证；目录与安装成功不能替代这些观察。发布后仍需以真实 release URL 验证网络链路；本次本地 ZIP 验收不宣称官方 16.1.0 已存在。
