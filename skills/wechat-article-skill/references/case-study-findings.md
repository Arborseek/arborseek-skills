# Findings from the saved WeChat cases

## Sample

The reference folder contained 26 saved HTML files. One generic `微信公众平台.html` file duplicated another article, leaving 25 editorial examples. The useful set spans short news, technical papers, research explainers, interviews, opinion pieces, product launches, and event promotion. Article bodies ranged from about 1,250 to 6,900 Chinese characters and from 3 to 47 images.

## Stable patterns

- The dominant body sizes are 15, 16, and 17 px. Fifteen and sixteen are the safest reusable values; 17 works for shorter editorial pieces.
- Common line heights cluster at 1.6, 1.75, 1.8, 1.82, and 2.0. Long technical prose benefits from 1.85–1.95 rather than the tightest values.
- Body colors repeatedly use near-black rather than pure black: `#222222`, `#3e3e3e`, and blue-gray `#27384d`.
- Paragraphs are usually justified. Effective letter spacing ranges from about `0.01em` to `0.04em`; the repeated 1 px pattern is visually strong and should be reserved for airy editorial variants.
- Captions are commonly 12 px, gray, and centered. Metadata is 13–15 px and muted.
- Visual identity comes chiefly from section headings, emphasis, quotes, and captions—not from changing body copy on every article.

## Reusable design families

### Blueprint

Observed in structured robotics/AI explainers: 30 px dark-blue section numbers, 18 px titles, deep blue rules, and a small yellow number shadow. It is strong for numbered technical narratives. The original often used dark-blue title fills and pale-blue subheading fills; for white-background output, retain the blue hierarchy and rules but remove the fills.

### Teal editorial

Observed in opinion and education pieces: 16 px body, 2.0 line-height, about 1 px tracking, and 20 px bold headings with a 6 px teal left rule. This family is readable and direct. Replace gray quote panels with white blocks and a quieter border when pure white output is required.

### Cobalt journal

Observed in research/editorial explainers: 16 px blue-gray body at roughly 1.82 line-height; 21 px headings in `#153f77` with a 4 px `#2f6feb` left rail. This is the most publication-like family and works well when sections have meaningful prose titles.

### Violet dialogue

Observed in interview/profile layouts: restrained purple headings, small overlines, centered separators, and clear speaker or guest blocks. The source body sometimes used 14 px; normalize it upward to at least 15 px for long mobile reading.

### Orange launch

Observed in product-launch and price-driven news: compact 15 px prose, approximately 1.75 line-height, 19 px statement headings, and orange `#ff6827` highlights. Use orange sparingly on numbers, key claims, and rules.

### Cyan research

Observed in benchmark-heavy technical papers: 15 px prose at about 1.8, 18 px headings, bright cyan-blue `#0e88eb` for results and labels, plus star/bullet callouts. It is appropriate for metrics and experimental conclusions, but long sentences should remain dark gray.

## Anti-patterns discovered

- Saved WeChat pages inherit dark mode from the host UI. Transparent article blocks therefore become black even when the editor expected white. Standalone output must explicitly pin light mode and white backgrounds.
- Many examples contain hundreds of inline styles and deep decorative wrappers. Copying them directly makes later editing brittle; normalize to semantic classes and a small token set.
- Fourteen-pixel body copy is too small for sustained mobile reading.
- One-pixel tracking combined with 2.0 line-height on every paragraph feels loose in data-dense research writing.
- Coloring every `<strong>` produces visual noise. Accent only short, intentional emphasis.
- Large filled title bars and tinted paragraph panels dominate scientific figures. On a white-only brief, use rules, rails, numbering, and type weight instead.

## Synthesis

The shared system should keep typography and spacing stable while varying only four controlled dimensions: heading geometry, primary accent, secondary marker, and optional quote/caption treatment. This yields recognizable variety without making the publication look like unrelated templates.
