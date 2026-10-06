# Skills 升级调查

本调查区分发布身份、文件更新、项目采用的语义迁移。用户基本认可 Skills release 合同，但质疑 version.json 的必要性，并要求参考 matt-skills 与主流管理器的实际升级方式。安装实现未获授权，本轮仅调查、隔离实验和任务材料更新。

## OpenSkills

调查日期 2026-10-05，npm openskills 1.5.0；上游 HEAD 为 `57d933a4f0d5c8659bd8b285f50fb9554360f0b3`。[源码元数据](https://github.com/numman-ali/openskills/blob/57d933a4f0d5c8659bd8b285f50fb9554360f0b3/src/utils/skill-metadata.ts) 记录 source、sourceType、repoUrl/subpath 或 localPath、installedAt，没有发布 SemVer、固定 ref 或安装基线内容散列。[Git 安装](https://github.com/numman-ali/openskills/blob/57d933a4f0d5c8659bd8b285f50fb9554360f0b3/src/commands/install.ts) 及 [更新](https://github.com/numman-ali/openskills/blob/57d933a4f0d5c8659bd8b285f50fb9554360f0b3/src/commands/update.ts) 使用默认分支 shallow clone；指定本地目录则重读该路径。它没有在源码合同中依据 Skill metadata.version 选择新版本。

隔离实验只在临时 project/source 与 npm cache 中执行，未操作真实全局 Skills：安装一个 fixture Skill，修改安装后的正文并新增 consumer-note.md，来源改为 v2，再 update 指定名称。结果为 v2 复制成功，但正文定制与新增文件均消失，无冲突确认。源码 updateSkillFromDir 删除目标目录后重复制，与观察一致。

第二轮删除本地来源，update 指定名称：输出 0 updated / 1 skipped，退出码 0；第三轮请求不存在名称也退出 0。因此不能用退出码单独证明安装到了目标内容。实测范围是 local-source 路径；默认 Git 分支行为为固定源码推断，没有执行远端 Git 更新。

更新没有项目迁移或采用指令重写合同；sync 是单独的 AGENTS 发现表操作。这不证明任意版本更新都兼容消费者，也不等价于 SVC 全任务采用迁移。临时项目、源与缓存已清理。

## Vercel Skills

Owner 调查 commit `18f96ea131dab3b0fcc9b27cf7c6f6cbb6174680`，npm CLI 1.7.0。官方 [Git ref 处理](https://github.com/vercel-labs/skills/blob/18f96ea131dab3b0fcc9b27cf7c6f6cbb6174680/src/git.ts)、[升级来源](https://github.com/vercel-labs/skills/blob/18f96ea131dab3b0fcc9b27cf7c6f6cbb6174680/src/update-source.ts)、[更新实现](https://github.com/vercel-labs/skills/blob/18f96ea131dab3b0fcc9b27cf7c6f6cbb6174680/src/update.ts) 与 [安装实现](https://github.com/vercel-labs/skills/blob/18f96ea131dab3b0fcc9b27cf7c6f6cbb6174680/src/installer.ts) 共同拥有行为。更新依据来源、ref、Skill 路径和内容散列，不依据 SVC version.json 或标准 metadata.version 做 SemVer 选择。保持原 ref：追踪 main 可以取新内容，固定 tag/SHA 不自动改为下一发布版本。

Owner 临时实验从公开 Git 来源安装 main 与完整 SHA，成功生成包含 ref 的项目 skills-lock.json。项目锁和全局锁是不同格式，不是 SVC release manifest。编辑安装正文后，执行项目 update 的实验观察到 marker 被替换；源码重新 add 的覆盖路径与此一致。没有定制三方合并承诺。

源码表明更新按项进行，已有成功项不会因其它项失败而回滚；有失败时最终 exitCode=1。上游路径迁移可尝试重定位；删除处理依赖交互且非交互时跳过，不是项目采用的语义迁移框架。实际本地修改覆盖和安装 ref 的证据来自 Owner 隔离实验；部分失败、路径重定位与删除分支未实测。

## Matt Skills

Owner 的初步调查显示上游使用 Changesets、private package.json 发布版本、插件 manifest 与 changelog，不是无版本发布；版本脚本同步插件版本。托管插件被作者描述为随发布更新的只读 bundle；普通 skills.sh 安装得到可编辑文件，用户主动执行 skills update。持久定制建议置于项目指令或 fork/自有 Skill，升级不提供通用本地 patch 合并。插件实际自动更新还受宿主 marketplace 配置影响；[Claude 官方更新说明](https://code.claude.com/docs/en/discover-plugins#keep-plugins-updated) 区分官方默认自动更新、第三方默认关闭和会话重新加载。

Owner 已通过本轮 git ls-remote 与临时 clone rev-parse 确认实时 HEAD：上游 `24fe0ef7737efae15c87225755e9f6f5965e4888`，curated `05cfa8bdea1d93ec7253daeb5d89555ccd5a290f`。上游 [版本同步脚本](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/scripts/sync-plugin-version.mjs) 从 private package.json 1.3.1 同步插件 manifest；Changesets workflow 拥有版本 PR 与 tag，不由 Skill frontmatter 决定管理器更新。

[ask-matt 文档](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/docs/engineering/ask-matt.md) 与 [code-review 文档](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/docs/engineering/code-review.md) 明确覆盖本地编辑，建议项目指令或 fork；[setup 文档](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/docs/engineering/setup-matt-pocock-skills.md) 描述模板变化后重新 setup，不构成任意消费者内容自动迁移；[to-spec 文档](https://github.com/mattpocock/skills/blob/24fe0ef7737efae15c87225755e9f6f5965e4888/docs/engineering/to-spec.md) 描述重命名后的人工处理。

curated [source-provenance.json](https://github.com/imMamdouhaboammar/matt-skills/blob/05cfa8bdea1d93ec7253daeb5d89555ccd5a290f/source-provenance.json) 记录独立快照的上游 revision、选择与改名映射，不能当作上游透明镜像；它的插件版本是 1.0.0。Owner 未找到当前仓库 package.json/Changesets，但 release workflow 仍调用 npm ci/version，说明该发布步骤未闭合。未验证其实际发布或宿主升级，不能从脚本存在推导已有更新服务。

## 对 version.json 的事实判断

通用管理器不使用它；当前 SVC 已无 CLI 运行时消费者。但它在仓库内仍有两个真实消费者：publish-corpus 读取发布前版本输入，check_corpus_release 检查发布链、迁移目标与源码变更版本同步。是否删除应分别决定单一版本输入与历史迁移索引，而不是把这些消费者当作用户必须保留的产品能力。版本身份、管理器安装基线与消费者迁移说明不能混为一个概念。

调查决策建议已写入 design.md，尚未修改任何升级功能或 version.json。统一发布版本与同仓库是用户已确认约束。
