# Visual planning, search, generation, and provenance

Every image must perform an editorial job: identify a real subject, explain a mechanism, prove a claim, compare data, establish a scene, or provide a deliberate reading pause. Decorative density is not a quality metric.

## Decision order

For `hybrid` mode:

1. Reuse user-supplied assets when relevant and permitted.
2. Search official project pages, papers, press kits, organization media libraries, or clearly open-licensed repositories.
3. Generate a conceptual illustration only when a suitable lawful source is unavailable, rights are unclear, or the concept is inherently abstract.

For real people, products, events, documents, screenshots, logos, paper figures, and empirical evidence, search first. Do not generate a look-alike and present it as reality.

## What to generate

Good candidates:

- abstract cover concepts;
- conceptual scenes that are clearly illustrative;
- editorial metaphors;
- non-documentary section illustrations.

Prefer code-native SVG/HTML for simple flows, timelines, relationship diagrams, and labeled schematics. Build charts from verified data. Image generation must never invent data labels, benchmark bars, screenshots, source documents, or scientific evidence.

## Search and rights record

An approved searched image needs:

- the source page URL in `source_page_url`, separate from a raw image `source_url`;
- creator/organization credit;
- license or usage basis;
- a local project copy only when downloading and reuse are permitted;
- alt text and optional caption.

Do not treat “found on the internet” as permission. If reuse terms cannot be established, choose a generated conceptual image or publish text-only.

## Image generation brief

The prompt should specify:

- editorial role and the information it should communicate;
- subject, setting, composition, and focal point;
- aspect ratio (`2:1` cover, usually `16:9` section art);
- visual theme, palette, and white/light base;
- constraints: no watermark, unwanted logo, decorative frame, fake UI, fake data, or illegible Chinese text.

Generate one distinct asset per call. Inspect the result at full size. Regenerate or reject for malformed hands/objects, misleading product details, embedded nonsense text, wrong aspect ratio, excessive visual noise, or conflict with the article claim. Record the final prompt and `generated_disclosure: true`.

## Density guidance

- `sparse`: one cover, optionally one essential explanatory visual; maximum 2.
- `balanced`: cover plus roughly one useful visual per 1,800 Chinese characters; maximum 5.
- `rich`: cover plus roughly one visual per 1,000 characters; maximum 8, only when the topic benefits from it.

These are ceilings, not quotas. Reject an unnecessary slot. Long technical prose may need a diagram; an opinion essay may be stronger with only a cover.

## Placement

- Place a visual immediately before the section whose question it helps answer, or after the paragraph that introduces it.
- Captions identify what the reader should notice and include attribution when needed.
- Alt text describes the informative content rather than repeating “图片”.
- Do not separate a chart from the paragraph that states its unit, baseline, and data source.
