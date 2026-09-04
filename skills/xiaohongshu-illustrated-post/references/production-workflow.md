# 可验证生产管线

当用户需要实际生成一组图片时使用本流程。文章创作和主题判断仍由模型完成；脚本只固定适合确定化的环节。

## 运行产物

一次生产使用独立的 `<run-dir>`：

```text
<run-dir>/
├── plan.json
├── manifest.json
├── prompts/
├── backgrounds/
└── final/
    └── render-report.json
```

## 1. 建立生产方案

根据定稿文章、主题引擎和版式系统生成草案 JSON。字段遵循 `schemas/production-plan.schema.json`。

关键字段：

- 默认生产 6 张且包含封面；一次可生产 1–9 张，超过 9 张的草案会被脚本拒绝。
- `theme.dna` 必须包含 `style-profiles.md` 定义的七个主题不变量。
- `theme.reference_assets` 只记录本次运行中用户提供的可访问参考图；没有参考图时使用空数组。不得假设技能包内存在 PNG。
- `pages[].layout.backbone` 使用版式系统中的骨架 ID。
- `pages[].text_blocks[].box` 使用 `[x, y, width, height]`，值为 0–1 的画布比例。
- 图中文字只进入 `text_blocks`，不要要求图片模型直接书写。
- `font_size` 和 `min_font_size` 是最终像素字号。

运行：

```bash
python3 scripts/prepare_plan.py draft-plan.json --output-dir <run-dir>
```

该命令会验证并规范化计划，建立稳定文件名，输出逐页提示词和 manifest。已有 run 不会被覆盖；确认要刷新时才传 `--force`。

若文章未指定数量，应先建立 6 页方案。文章无法在 9 页内清楚表达时，应拆成多个独立 run，每个 run 对应一篇可单独发布的帖子。

## 2. 生成无字底图

逐一读取 `<run-dir>/prompts/*.txt`，使用当前宿主可用的图像生成工具生成。工具不可用时交付提示词，不假装已经出图。提示词已要求：完整视觉设计、保留文字区域、绝不生成文字或伪文字。

没有用户参考图时，直接使用 prompt 内的文字化主题 DNA。用户提供参考图时，只把与当前主题相关的图片作为 style reference。生成后将每张选定图片复制到 manifest 指定的 `backgrounds/*.png`。不要修改 manifest 中的文件名。

先检查底图：主题一致、布局正确、保留区干净、无水印/署名/伪文字。底图有问题时先修底图，不进入排字。

## 3. 精确排字

运行：

```bash
python3 scripts/compose_text.py <run-dir>/plan.json \
  --background-dir <run-dir>/backgrounds \
  --output-dir <run-dir>/final
```

脚本会自动寻找常见中文字体、按框自动换行和缩小字号，并输出 `render-report.json`。如果用户提供了有权使用的品牌字体，用 `--font /path/to/font.ttf`。技能不内置第三方字体文件。

默认不覆盖既有成品；确认重新渲染时传 `--force`。底图尺寸与计划不一致时默认报错；只有确认缩放不会破坏布局时才传 `--resize-background`。

手写主题若需要真正的手写字形，应使用用户提供或系统已有且许可清楚的中文手写字体；没有合适字体时，优先保证可读和准确，不伪装成手写。

## 4. 自动校验

运行：

```bash
python3 scripts/validate_output.py <run-dir>/plan.json \
  --run-dir <run-dir> \
  --stage all \
  --strict
```

检查包括：

- 背景和成品是否齐全、可读取、尺寸一致。
- 是否出现重复图片或未列入计划的 PNG。
- `render-report.json` 是否来自当前 plan。
- 每个文字块是否按计划完整渲染，成品是否在渲染后又被修改。

该校验确认生产合同和文件完整性，不替代视觉审美检查。最终仍需按 `quality-checklist.md` 检查层级、留白、内容准确性和系列一致性。

## 5. 失败处理

- 文字装不下：缩短文字、扩大 box、拆页，或降低 `min_font_size`；不要关闭报错强塞。
- 中文字体缺失：用 `--font` 指向可用且有权使用的字体。
- 底图有伪文字：重新生成底图，并强化 `no letters / no numbers / no pseudo-text`。
- 重复页面：回到页面命题和骨架选择重新设计，不用装饰差异掩盖结构重复。
- 最终只交付 `final/` 成品、文章正文和主题/配图清单；`plan.json` 与报告可作为可复现附件保留。
