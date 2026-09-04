# Quality gates

## Source preservation

- Title and article-body text are present and non-empty.
- Paragraph order and heading order match the source.
- All meaningful images, captions, tables, lists, quotations, and links remain.
- Scripts, forms, iframes, tracking pixels, hidden controls, and host-page chrome are removed.
- The preview does not repeat the title or cover accidentally.

## Content and evidence

- Audience, reader outcome, article type, and tone are explicit or explainably inferred.
- Every material factual claim is represented in the claim ledger when research is enabled.
- Verified claims point to declared sources that directly support them.
- Inferences are labeled as analysis; unverified claims are removed or visibly qualified.
- Names, dates, metrics, units, comparison baselines, and quotations have been checked.
- The title promise is fulfilled without unsupported superlatives or fabricated certainty.

## Visual provenance

- Every planned image has a role, placement, ratio, alt text, source type, and status.
- Every ready searched image has a source page, credit, and documented usage basis.
- Every generated image retains its prompt and disclosure and is not presented as documentary evidence.
- Charts use verified data; generated images do not contain invented metrics or fake UI.
- No malformed, misleading, watermarked, pixelated, or badly cropped asset is approved.
- Unfinished visual slots are ignored or block `--require-ready`; the renderer never invents a substitute.

## Visual invariants

- `color-scheme: light` is set.
- Body, page, headings, quotations, tables, and code blocks compute to white or transparent-over-white backgrounds when white-only mode is selected.
- Desktop reading width is no more than 677 px.
- At 390 px viewport width, the page has no horizontal overflow.
- Body type computes to 15–16 px and line-height to 1.75–2.0.
- Major headings are visibly stronger than minor headings and body copy.
- One article uses only one dominant accent family.
- Long English tokens and URLs wrap; figures retain aspect ratio.

## Batch invariants

- Every source ID has exactly one preview and manifest entry.
- Style assignment is deterministic for a given seed.
- No style family appears more than twice consecutively.
- Every manifest entry includes category, confidence, feature summary, theme scores, and a human-readable selection reason.
- Style counts are reasonably varied after respecting content compatibility; equal counts are not required.
- Re-running with the same inputs, seed, and diversity mode produces the same assignments.
- Every input article produces exactly one standalone HTML file.

## Browser checks

Inspect at least:

1. The batch index on desktop.
2. A dense technical article on desktop.
3. The same or another long article at 390 × 844.
4. A source with semantic headings.
5. A source whose headings were inferred from bold Word-style paragraphs.

Check computed typography, background colors, missing/broken images, console errors, and horizontal overflow. Do not approve based only on source-code inspection.

For a complete authored article, also check that the cover crop is intentional, section images appear beside the claims they support, captions are readable, attribution is present, and the visual rhythm is neither empty nor crowded.
