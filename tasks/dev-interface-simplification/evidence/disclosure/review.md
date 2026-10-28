# 动画修复复核

参考为 nearby-audio 提交 027c8946a43776eac156f1d30417a5878064c432：局部 transaction 同时清空 animation 并设置 disablesAnimations。SVC 四处 DisclosureGroup 原先均有显式展开绑定，修改只覆盖对应组。独立只读 advisor 核对后未发现源码阻塞问题。

两次原生实验未取得 SwiftUI AX 节点，原因未确证。advisor 指出拟用的 fittingSize 高度采样也不能区分动画已取消、控件未触发和固定窗口尺寸，因此不继续增加宿主或绕过原生组件。源代码对应、最终构建与既有检查支持实现交付，不能声称已验证动态视觉体验。实验脚本未保留为工具或测试，未触发真实资源动作。
