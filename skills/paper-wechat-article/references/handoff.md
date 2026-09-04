# 解析 → 公众号交接

直接接收已有笔记和 PDF，无需上游升级。只有在进入脚本排版时，由助手整理以下内部约定；单篇论文一个交接，多篇比较先分别核对证据，不混用 ID 或图号。

可运行的合成结构示例见 [示例 JSON](../examples/paper-handoff.example.json)，其中 example.org、标题与内容只是测试数据，不能用于真实发布。

## 交接结构 v1

- `paper`：`title`、`version`、`source_url`（官方页面 http/https）、`read_scope`（full-text / partial / abstract / notes-only），可附 `local_pdf`、`authors`。来源无法核实的私有稿件保持草稿，不编造公开网址来通过检查。
- `claims`：每条有 `id`、`claim`、`status`（verified / inference / unverified）、`locator`（如“PDF 第 6 页，Table 2”）、`notes`。verified 仅表示编辑实际核验过；inference 需要解释推理，不将摘要级材料包装成全文结论。模型不得按字段自动认证。
- `figures`：每个图位有 `id`、`kind`（original / redraw / generated）、`label`（Fig. 2 等）、`locator`、`local_path`、`alt`、`caption`、`credit`、`rights_status`（cleared / unknown）、`rights_note`、`checked`（是否实际查看核对）、`use_as_evidence`（布尔）。无图时使用空数组。
- redraw / generated 额外有 `fallback_reason`，写清已检查哪些原图以及为什么不适用；generated 另需 `generation_prompt`。它们只能承担说明作用，不能被声明为原论文实验证据。

`prepare` 将每条结论连到本篇来源，并把 locator 写入 research.claims[].notes；图注附带图号、原文位置、署名和“论文原图 / 依据原文重绘示意 / AI 生成概念配图”。图位初始都是 candidate，即使文件存在也不会自动就绪。没有图时不强制封面。

## 编辑 article.json

生成后以 article.json 为本次编辑的唯一记录，不再修改旧交接却遗漏文章包：

- 正文存 `article.content_html`，更改关键结论同步 `research.claims`。原文位置保留在每条 `notes`，文章正文也需给读者图表号/链接。
- 原论文身份保存在 `paper`。图像原始记录保存在各 `visuals.items[].paper_figure`，文件路径、显示图注和状态在同一 item。
- 改成 `ready` 前核对文件、图像、图注与使用依据；不能仅把布尔值改成 true 以消除错误。不采用的图设 rejected，不因图不够而造新实验图。
- `qa.content_reviewed`、`sources_reviewed`、`visuals_reviewed` 对应实际编辑检查；`browser_reviewed` 仅在预览后记录。浏览器检查在渲染之后，因此不是 --require-ready 的前置条件。
- 初始图位为 after-intro，可按论述改为 `before-section:2` 等（章节自 1 计）。原论文图不设置 cover，以免封面裁切或丢失图注；封面可单独设置无证据性质的概念图。

## 三个典型交接

1. 精读完成、有 PDF：沿用版本和笔记 → 核对核心图表 → 起草正文 → 提取原图 → 排版。不再搜索替代论文。
2. 只有摘要笔记：输出标注“摘要级解读”的短稿，不使用未读实验数据；请求 PDF 或保留待核验，不假装全文已读。
3. 论文有方法图、没有适合的封面：正文用方法原图；封面可省略。确实需要封面时记录原图不适合作封面的原因，再绘制/生成非实证插图。
