# Content classification and style selection

## Principle

Style selection is a ranking problem, not a one-keyword lookup. Infer the article's editorial job first, rank visual families second, and apply batch diversity only after compatibility has been established.

## Inputs

Use both lexical and structural signals:

- Title and body terms, with title matches weighted more heavily.
- Total text length and paragraph count.
- Semantic heading count and hierarchy depth.
- Image density per 1,000 characters.
- Table and blockquote count.
- Digit ratio, percentage mentions, and metric language.
- Question-mark density and argumentative phrases.
- Chinese quotation pairs, colon-led speaker lines, and interview vocabulary.
- Launch/event punctuation and action vocabulary.

## Editorial categories

### `technical-paper`

Signals include paper/model/algorithm/architecture/training terminology, conference or arXiv references, several semantic headings, and method-focused prose. Preferred families: `cobalt-journal`, `blueprint`, then `cyan-research`.

### `data-report`

Signals include benchmark/experiment/evaluation language, high digit ratio, percentage results, tables, and repeated comparisons. Preferred families: `cyan-research`, `cobalt-journal`, then `blueprint`.

### `interview-profile`

Signals include interview language, speaker-like colon lines, quoted dialogue, names/roles, and person-centered structure. Preferred families: `violet-dialogue`, `teal-editorial`, then `cobalt-journal`.

### `launch-news`

Signals include release/funding/price/open-source announcements, exclamatory titles, short sections, and high image density. Preferred families: `orange-launch`, `blueprint`, then `cobalt-journal`.

### `editorial-analysis`

Signals include why/how/meaning/trend language, questions, thesis-driven long prose, and fewer metric blocks. Preferred families: `teal-editorial`, `cobalt-journal`, then `blueprint`.

### `event-promo`

Signals include livestream, registration, recruitment, prize, community opening, or preview language. Preferred families: `orange-launch`, `violet-dialogue`, then `teal-editorial`.

### `tutorial`

Signals include guide/tutorial language, ordered steps, installation or configuration instructions, code blocks, checklists, and practical examples. Preferred families: `blueprint`, `cobalt-journal`, then `cyan-research`.

## Confidence

Confidence describes separation between the top two category scores. Low confidence does not mean the output is invalid; it means several editorial jobs overlap. In that case:

- Prefer the calmer `cobalt-journal` or `teal-editorial` family.
- Let structural signals break ties.
- Expose the ranking in the manifest so a reviewer can override it.

## Diversity modes

`content-first` keeps candidates within 0.55 points of the best theme. `balanced` widens the compatibility window to 1.8 and applies a modest prior-use penalty. `high` widens it to 2.8 and increases the prior-use penalty. A repeat penalty prevents an avoidable third consecutive use of one family.

The seed adds only tiny deterministic tie-breaking jitter. It must never overpower the semantic score.

## Override rules

Honor an explicit user theme. Preserve an already approved `theme` or `style_id` from a manifest. Reclassify only when content changed materially or the user asks for it.

Do not use visually loud event/launch treatments for sensitive, legal, medical, memorial, or crisis content without an explicit editorial decision.
