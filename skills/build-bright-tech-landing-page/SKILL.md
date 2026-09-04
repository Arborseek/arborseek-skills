---
name: build-bright-tech-landing-page
description: 设计、搭建和优化明亮科技风网站与响应式落地页，适用于产品、企业、服务、课程和活动专题页。
metadata:
  version: "1.0.1"
---

# 科技风网站与落地页设计

Create production-ready landing pages that feel designed for the supplied subject rather than assembled from a generic card template. Adapt the rules to the content and framework already in use.

For a new runtime, read [references/runtime.md](references/runtime.md) for tool and path handling. Maintenance provenance is recorded in [SOURCES.md](SOURCES.md).

## Workflow

1. Inspect the existing page, project conventions, assets, responsive rules, and user-provided references before editing.
2. Identify the audience, value proposition, primary action, content hierarchy, and 6–9 useful sections.
3. Establish one coherent visual direction. Do not mix unrelated styles between sections.
4. Give each section a structure suited to its information: hero, split editorial layout, comparison, data panel, capability grid, timeline, scene cards, proof, or CTA.
5. Implement responsive behavior at desktop, tablet, and mobile widths.
6. Add only motion that improves comprehension.
7. Inspect the result for spacing, cropping, overflow, hover behavior, accessibility, and visual consistency.

When working in an existing repository, preserve its framework, routing, localization, asset strategy, and user changes. When asked for standalone output, produce a complete runnable HTML file without hidden dependencies.

## Visual Direction

- Use white, ice blue, pale blue-gray, deep navy text, and one clear blue accent.
- Keep the page bright, professional, restrained, and engineering-led.
- Prefer strong typography, deliberate whitespace, useful diagrams, and scene imagery over decorative effects.
- Avoid dark AI themes, neon glows, cyberpunk imagery, dense grids, purple-blue washes, gradient borders, and gradient divider lines.
- Do not make every section a grid of identical rounded cards.
- Do not add icons merely to fill space. Prefer an image, number, typographic marker, or no decoration.
- Maintain smooth background continuity between adjacent sections; avoid abrupt pale-color mismatches.

Suggested neutral palette when no brand system exists:

- Background: `#ffffff`
- Soft section background: `#f4f9fd` or `#edf6fc`
- Primary text: `#10263f`
- Secondary text: `#65768a`
- Accent: `#0968eb`
- Supporting blue: `#08a9df`
- Border: `#d9e5ef`

## Typography

- Prefer `PingFang SC`, `Microsoft YaHei`, and a clean sans-serif for Chinese; use Inter or Arial for English.
- Use confident 600–700 weight for major headings and 400 weight for body copy.
- Make desktop hero headings roughly 56–76px and section headings 38–52px when space permits.
- Keep body copy around 14–17px with 1.65–1.9 line height.
- Highlight only meaningful words in blue. Do not turn whole paragraphs into gradient text.
- Use small uppercase English eyebrows sparingly.
- Let English headings reflow or reduce in size; never force them into a Chinese-width layout.
- Preserve readable alignment. Use offset title lines only when intentional and subtle.

## Layout

- Center content within roughly 1320–1440px on desktop unless the project defines another container.
- Keep at least 48px desktop side safety space, 22–32px on tablet, and 18–22px on mobile.
- Prefer left copy and right imagery for primary desktop sections.
- Use two to four columns only when the content supports comparison.
- Convert multi-column content to two columns on tablet and one column on mobile.
- Keep vertical rhythm compact and consistent. Remove unexplained empty space.
- Never allow horizontal scrolling, clipped headings, or cards made tall only to fill a row.

## Navigation

- Use a clean white or lightly translucent header around 68–76px tall.
- Keep the logo readable and vertically centered.
- Use 15–16px desktop navigation text with regular default weight and semibold active weight.
- Show active state through accent color and a short marker, not a full-width border.
- Keep hover feedback subtle.
- Collapse navigation around 900px when needed.
- Place the mobile menu control at the far right, never immediately after the logo.
- Make the opened mobile menu clear, accessible, and easy to dismiss.

## Hero

- State the value proposition immediately with a short eyebrow, strong title, concise explanation, and clear primary action.
- Keep desktop copy on the left and the main visual on the right unless the supplied composition requires otherwise.
- Limit the title to approximately four visual lines.
- Use at most two primary actions and one concise trust statement.
- Avoid piling floating tags and cards over the hero image.
- Keep the subject visible and separated from adjacent UI such as QR cards or buttons.

## Images

- Use bright, clean, professional people or business-scene imagery.
- Favor engineers, operators, product teams, customer environments, interfaces, servers, or relevant industry scenes.
- Avoid generic AI brains, cheap 3D characters, neon rooms, and dark data-center clichés.
- Integrate images into the background with careful cropping or a subtle edge fade.
- Never place a heavy white, blue, or dark wash over the full image.
- Use a small local readability treatment only where text overlaps the image.
- Inspect the source composition before choosing `object-position` or `background-position`.
- If the source has large blank areas, reposition the focal subject instead of describing the blank crop as a mask.
- Do not enlarge background images on hover unless the user explicitly asks for it.

## Sections and Cards

Choose structures based on meaning rather than repeating one template:

- Problems: editorial list, expandable visual strip, or comparison.
- Definition: split narrative, quote, facts, and supporting capabilities.
- Capabilities: image-led grid with varied emphasis.
- Data: metric rows paired with a chart or diagram.
- Process: three to five aligned phases with outputs.
- Audience: static scene cards or a concise segmented list.
- Conversion: strong summary, supporting visual, and contact mechanism.

For cards:

- Use 8–16px radius, light borders, restrained shadows, and 24–32px padding.
- Keep title-to-copy spacing around 8–12px.
- Do not repeat icon-title-copy-button anatomy on every card.
- Do not add hover effects without interaction value.
- If hover is useful, limit it to a 2–4px lift or a small border/shadow change.
- If hover is not useful, disable transition, transforms, background scaling, overlays, and color inversion completely.

## Data and Diagrams

- Use numbers only when their meaning is defensible.
- Distinguish targets, examples, and assessment results explicitly.
- Keep radar charts to roughly five or six dimensions with readable labels.
- Pair charts with a concise explanation.
- Animate numbers or chart strokes once on entry, not continuously.
- Never imply fabricated precision.

## Conversion Section

- End with a complete CTA rather than an isolated button.
- Use a strong summary, short supporting copy, two or three service options, and one primary action.
- Use a bright background and preserve clear separation between copy, people, forms, and QR cards.
- Keep QR codes unobstructed with adequate quiet space.
- If opening a modal, support a close button, backdrop click, Escape, focus visibility, and correct stacking above fixed navigation.

## Motion

- Use restrained one-time entrance motion: opacity and 20–30px vertical movement over 0.6–0.8s.
- Stagger related items by roughly 50–80ms.
- Use 0.8–1.2s for count-up or chart drawing.
- Prefer `cubic-bezier(.2,.75,.2,1)` for editorial entrance motion.
- Avoid continuous floating, breathing, spinning, large zooms, and excessive bounce.
- Ensure later general transitions do not overwrite component-specific transitions.
- Support `prefers-reduced-motion` and show final states immediately when requested.

## Responsive and Localization

- Validate at wide desktop, common laptop, tablet, and narrow mobile widths.
- Keep important image subjects visible after cropping at every breakpoint.
- Reduce decorative imagery when it makes mobile sections too tall.
- Stack actions or make them full width on small screens when useful.
- Design for both Chinese and English text expansion.
- When localization is requested, translate the complete page, including labels, diagrams, alt text, dialogs, buttons, and footer copy—not only navigation.
- Prefer an existing application-level locale mechanism. For standalone pages, use a simple explicit locale state and persist a user choice only when requested.

## Accessibility and Code Quality

- Use semantic `header`, `nav`, `main`, `section`, and `footer` elements.
- Provide meaningful image alt text and accessible labels for charts and controls.
- Use buttons for actions and links for navigation.
- Preserve keyboard access and visible focus states.
- Give dialogs appropriate roles and dismissal behavior.
- Keep selectors local and understandable; avoid large chains of conflicting overrides.
- Reuse project assets and conventions where available.
- Do not invent missing business facts. Mark or resolve genuine content gaps.

## Final Review

Before handing off, verify:

- The result is bright, coherent, and subject-specific.
- Sections do not look cloned from one component template.
- Images are visible, correctly cropped, and free of accidental washes.
- Hover states do not introduce zoom, masks, layout shifts, or illegible text.
- Spacing is consistent without oversized gaps.
- Navigation, dialogs, anchors, and responsive menus work as intended.
- Long Chinese and English copy fits at all target widths.
- Motion is restrained and reduced-motion behavior is respected.
- The page looks ready for a real company to publish.
