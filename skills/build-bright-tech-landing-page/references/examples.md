# 如何使用示例

[landing-page.html](../examples/landing-page.html) 是可直接打开的独立示例，内联 CSS/JS，不请求外部资源，无需安装包。产品名、流程图和文案用于演示，不是真实业务资料，不含有效报名或付费接口。

示例包含：流式字号和可调整颜色；首屏与编辑式步骤的不同布局；支持 Escape、焦点返回和断点切换的展开导航；关闭 JS 后仍能使用的链接；减少动画处理。

按组件借鉴，不直接复制演示品牌和整页结构。迁入框架时采用现有路由、样式作用域和状态管理，不在每次组件渲染时重复绑定监听器。

在本技能目录验证（或换成绝对路径）：

```bash
python3 scripts/check_html.py examples/landing-page.html
python3 -m unittest discover -s tests -p 'test_*.py'
```

需要真实浏览器回归时，使用已安装的 Playwright 与 Chromium 执行 `tests/browser_smoke.py`。缺少依赖时明确失败，不自动安装，不把跳过写成通过。脚本仅在隔离的无头浏览器中打开本地示例，不操作用户已有浏览器。

如果只有已安装的 Chrome 或 Edge，可显式传 `--channel chrome` 或 `--channel msedge`；依然使用隔离测试会话，不读取用户浏览器配置。此测试不等于在五个 AI 客户端中完成了选技和运行验证。
