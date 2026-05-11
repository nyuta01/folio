# Folio logo drafts — variant 1 (folded sheet)

Four directions on the "folded sheet" concept. Each ships as `light`
(for warm backgrounds) and `dark` (for the dark theme).

Open the SVGs directly in a browser tab to compare. They're all
28 × 28 viewBox so they render at the same size as the existing
placeholder logo for fair comparison.

## A. Outline (Phosphor-style file icon)

Files: `A-outline-{light,dark}.svg`

```
┌─────╮
│      ╲
│       │
│       │
│       │
└───────┘
```

- Thin clay stroke on cream background, transparent fill.
- Reads like a familiar "document" icon. Friendly, restrained.
- ⚠️ At 16 × 16 favicon size, the stroke may compress; less iconic.

## B. Cream page on clay tile

Files: `B-cream-page-{light,dark}.svg`

- Solid clay rounded square, with a cream "page" floating inside,
  fold visible as a slightly lighter triangle.
- Strong silhouette, very recognizable at small sizes.
- The fold's lighter shade reads as "the back of the paper",
  giving subtle depth without skeuomorphism.

## C. Clay page with JSONL row hints

Files: `C-clay-page-rows-{light,dark}.svg`

- Inverted from B: cream background, clay page, fold in deeper clay.
- Three short cream bars inside the page suggest the `records.jsonl`
  rows — most explicit about what Folio actually contains.
- ⚠️ Most detail-heavy; the rows may disappear at favicon size.
  Still works if we keep a row-less version for the favicon and use
  this for the marketing site / desktop app.

## D. Full-tile cut corner (boldest)

Files: `D-cut-corner-{light,dark}.svg`

- The whole 28 × 28 *is* the sheet — no inner page-on-tile framing.
- Top-right corner is cut at a 45° diagonal; the exposed triangle is
  a deeper clay to suggest the back of the fold.
- Maximum visual weight at small sizes; reads more like a "brand
  mark" than a "file icon".

## How to view

```bash
# macOS: open each in Preview / browser
open apps/docs/src/assets/logo-drafts/*.svg

# or render a single one in a HiDPI preview
open -a "Google Chrome" apps/docs/src/assets/logo-drafts/B-cream-page-light.svg
```

Pick one direction (or ask to blend two) and I'll wire it through:

- `apps/docs/src/assets/logo-{light,dark}.svg`
- `apps/docs/public/favicon.svg`
- `apps/desktop/assets/` (Electron icons — need PNG sizes too)
- The viewer header (if it embeds the logo)
