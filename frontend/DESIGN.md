# TruHire design system: the newsroom assignment desk

Mode: Operate. Recruiters and admins work in it for hours, so scanning speed beats expression. The world supplies type, palette, density and one signature move; layout and controls stay standard web components.

## World
Requirements are stories on a desk, candidates are wire items, recruiters take assignments. Cool newsprint-grey ground, ink-black type, one logo-blue action colour.

## Tokens (source of truth: `src/styles/tokens.css`)
- Ground `--bg-app #eef0ee`, sheet `--bg-surface #f8f9f7`, ink `--text-main #15191c`.
- Action `--primary #3a4aa0` (light) / `#8ea2dc` (dark). It appears only where something can be done or is selected.
- State colours (`--success`, `--warning`, `--danger`, `--info`) are used only where they carry meaning.
- Radii 6 / 10 / 14px. Cards, tables and result cards sit on a soft two-layer shadow (`--shadow-card`), lifting to `--shadow-lift` on hover; modals and popovers use `--shadow-lg`. Only palette tokens are used for colour, never hex values in components.
- Space is a 4px scale (`--space-1` to `--space-7`); body measure is 68ch.

## Type
- Source Serif 4 for page titles and for the names of requirements and candidates (the "headline").
- Public Sans for all UI text.
- JetBrains Mono only for ids (`TRU-CN-0012`), scores and counts (the "slug"). Tabular numerals everywhere.

## Signature moves
- Status marks instead of coloured pills: hollow circle = pending, filled = shortlisted, struck = not shortlisted (`components/ui/StatusMark.jsx`, `config/statusMarks.js`).
- Ranked rows read like wire items: score numeral, serif name, slug line, dek (the AI summary), then the review controls in fixed columns that never reflow.
- Page sections (Tracker: Pipeline / Submission, Interviews: Internal / Client) are a row of underlined tabs (`.page-tabs`, routed with `NavLink`); stage tables in the trackers are collapsible sections with a count.

## Components
`tracker/*` (stage tables with inline add/edit rows), `insights/*` (progress bars, ranked bars, area chart; plain-language sections), `ui/Modal`, `ui/Notice`, `ui/StatusMark`, `requirements/*` (list, editor, matches, modals), `search/*` (form, result row, results panel), `review/*` (assignment picker, comment thread). Layout primitives (`.stack`, `.cluster`, `.page`, `.section-head`, `.slug`, `.dek`) live in `src/styles/layout.css`.

## Rules
- No inline `style={{}}` in new or rewritten components; colours come from tokens.
- Enums and limits (statuses, page sizes, top-N bounds, comment length, accepted file types) come from `GET /api/meta`; storage keys, timeouts and polling intervals come from `src/config/env.js`.
- Never put the word "analytics" in a file name or URL the browser fetches: privacy and ad blockers refuse such URLs and the page blanks. The Analytics page lives at `/insights`, its API at `/api/insights`, its files under `insights/`; only the visible label says Analytics.
- Avoid: identical icon-in-box cards, coloured side borders, gradient text, all-caps eyebrow labels, unicode glyphs as icons.

## Not yet restyled
Ingestion, Ingestion History, Email and the candidate profile inherit the new tokens and fonts but keep their previous layouts.
