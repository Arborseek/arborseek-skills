# Article package contract

The article package is the handoff between creative reasoning and deterministic output. It prevents silent changes to tone, theme, claims, and images.

The canonical schema is [../schemas/article-package.schema.json](../schemas/article-package.schema.json). A minimal sample is [../examples/article-package.example.json](../examples/article-package.example.json).

## State flow

`topic/draft -> researched package -> visual plan -> approved assets -> validated package -> rendered HTML -> browser-reviewed HTML`

Visual item states:

- `planned`: editorial need, placement, and acquisition brief exist;
- `candidate`: an asset has been found or generated but not approved;
- `approved`: editor approved the choice, but local/remote availability may still need checking;
- `ready`: asset path or URL resolves and required credit is recorded;
- `rejected`: intentionally omitted; renderer ignores it.

Final rendering with `--require-ready` rejects unfinished research, unreviewed content/sources/visuals, undocumented image rights, and any visual item still in an intermediate state. Browser review happens after rendering. Preview rendering without that flag ignores unfinished items instead of inventing replacements.

## Authority order

1. Explicit current user instruction.
2. Approved values in the article package.
3. Automatic classifier and planner.
4. Stable defaults.

Changing an approved theme, source, image, or claim requires updating the package and rerunning validation. Never patch the final HTML as the only source of truth.

## Output boundary

The article package is an internal planning artifact. The default user-facing deliverable is the complete standalone HTML file. Only expose the package JSON or a body-fragment HTML when the user requests it or a batch workflow needs it.
