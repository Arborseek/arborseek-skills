# Article style system

## Shared foundation

Use these defaults unless source or user requirements justify a narrow change.

| Token | Default | Allowed range |
|---|---:|---:|
| Reading width | 677 px | 640–677 px |
| Mobile side padding | 20 px | 18–22 px |
| Article title | 22 px / 500 / 1.4 | 21–24 px |
| Body | 15.5 px / 400 / 1.9 | 15–16 px / 1.75–2.0 |
| Major heading | 19–21 px / 700 | 18–22 px |
| Minor heading | 15–17 px / 700 | 15–18 px |
| Caption | 12 px / 600 / 1.8 | 12–13 px |
| Paragraph gap | 16 px | 14–20 px |
| Section gap | 32 px | 28–40 px |

Font stack: `"PingFang SC NEW", "PingFang SC", -apple-system, BlinkMacSystemFont, "Helvetica Neue", "Microsoft YaHei", Arial, sans-serif`.

Core neutral colors:

- Main text: `#30343b` or `#3e3e3e`
- High-emphasis title: `rgba(0,0,0,.9)`
- Metadata: `rgba(0,0,0,.5)`
- Hairline: `#dbe4ee`
- Background: `#ffffff`

## Style families

### `blueprint`

- Primary `#004080`, accent `#223170`, marker `#ffdf21`, link `#1306fa`
- Major heading: two-column number plus title, with a 2 px bottom rule
- Best for robotics, world models, model architecture, multi-stage methods, and strongly numbered source material

### `teal-editorial`

- Primary `#008a73`, accent `#14665b`, marker `#72c7b7`, link `#007d6a`
- Major heading: 5 px left rail, large text, no number unless the source is numbered
- Best for arguments, opinion, education, ethics, and conceptual analysis

### `cobalt-journal`

- Primary `#153f77`, accent `#2f6feb`, marker `#8cb4ff`, link `#2459b3`
- Major heading: left rail plus a short upper label; calm blue-gray body text
- Best for research explainers, literature synthesis, and long-form analysis

### `violet-dialogue`

- Primary `#660874`, accent `#a65bcb`, marker `#d5a9e5`, link `#7d2990`
- Major heading: centered title between thin rules; small section label above
- Best for interviews, profiles, founder stories, and event conversations

### `orange-launch`

- Primary `#b94a1c`, accent `#ff6827`, marker `#ffbd9c`, link `#c94f1d`
- Major heading: bold statement with a short orange underline and optional inline index
- Best for launches, pricing, funding, product releases, and fast news

### `cyan-research`

- Primary `#006c9c`, accent `#0e88eb`, marker `#8dd8ff`, link `#0879c9`
- Major heading: bracket/rail geometry and compact numbering; metric callouts use the accent
- Best for benchmarks, autonomous driving, experiments, datasets, and quantitative comparisons

## Content-aware selection

For the full scoring model and diversity thresholds, read [content-classification.md](content-classification.md).

Score theme eligibility from the title and body structure:

- Interview/profile signals: `对话`, `访谈`, `专访`, `创始人`, `负责人`, speaker labels → `violet-dialogue`
- Launch/news signals: `发布`, `刚刚`, `融资`, `售价`, `万元`, `新品`, `开源` → `orange-launch`
- Quantitative research signals: `benchmark`, `评测`, `提升`, `%`, `实验`, `数据集`, `ECCV`, `CVPR` → `cyan-research`
- Robotics/architecture signals: `机器人`, `具身`, `世界模型`, `VLA`, `强化学习`, `架构` → `blueprint` or `cobalt-journal`
- Argument/explainer signals: `为什么`, `如何`, `重新认识`, `分析`, `观点`, `教育` → `teal-editorial` or `cobalt-journal`

For a single article, choose the top content-compatible family. For a batch, use soft diversity penalties rather than forcing equal counts: a technical-paper collection should naturally contain more blueprint/cobalt/cyan treatments than interview or event treatments. Choose deterministically from a seed, avoid an unnecessary third consecutive repeat, and persist the selected ID after approval.

## Component rules

- Major headings may vary by family; minor headings remain simpler than major headings.
- Quotations use a border or quotation mark, never a heavy colored panel on a white-only brief.
- Scientific tables use white cells, subtle borders, horizontal scrolling, and 13 px text.
- Images use intrinsic aspect ratio, `max-width:100%`, and no decorative crop.
- A short paragraph immediately following an image and starting with `图` or `表` may become a caption.
- Links use the family link color and must wrap safely.
- Keep ordinary bold text dark. Add accent color only to short semantic highlights, labels, metrics, or result claims.

## Variation boundary

Keep the foundation constant across a publication. Vary heading geometry, accent palette, quote treatment, and markers. Do not randomize body size, reading width, paragraph rhythm, font family, or image behavior per article.
