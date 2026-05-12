---
purpose: A deliberate type-showcase — every Folio `logicalType` at least once, plus enum, plus python and SQL derivations, in one realistic e-commerce schema.
default_actor: agent:human:you
tags: [type-showcase, e-commerce, derivations]
agent_skills: [restock-suggestions]
---

# product-catalog

The other examples are use-case-driven (`customers/` enriches data,
`task-tracker/` coordinates agent work, etc.). This one is
**type-driven**: it's the smallest realistic schema that uses every
Folio logical type and enum at least once, so you can see every
Viewer affordance and every contract-level guarantee in one place.

If you're evaluating Folio and want to know "what does an `array`
cell look like? a `boolean`? an `object`?", open this example in the
Viewer.

## Type coverage

| `logicalType` | Field           | Edit UI                       | Display UI                       |
|---|---|---|---|
| `string`         | `name`              | text input                  | plain text                       |
| `string` + `enum`| `category`, `status`| **dropdown**                | **`.tag` pill**                  |
| `integer`        | `stock`             | `type=number`, step=1       | right-aligned, thousand-grouped  |
| `number`         | `price_usd`         | `type=number`, step=any     | right-aligned, decimals kept     |
| `boolean`        | `is_featured`       | true/false/(empty) `<select>`| **tone pill** `✓ true` / `✗ false` |
| `date`           | `listed_on`         | `type=date`                 | plain ISO date                   |
| `timestamp`      | `updated_at`        | `type=datetime-local`       | `YYYY-MM-DD HH:MM:SS Z`          |
| `array`          | `tags`              | **tag-chip editor**         | inline chip strip with `+N`      |
| `object`         | `dimensions`, `vendor_codes` | JSON textarea       | compact one-line JSON            |

Plus four derivations exercising both the `python` and `sql` kinds:

| Field                       | Kind    | What it does                                     |
|-----------------------------|---------|--------------------------------------------------|
| `in_stock` (boolean)        | `python`| `stock > 0`                                      |
| `tag_count` (integer)       | `python`| `len(tags)`                                      |
| `price_tier` (string+enum)  | `python`| `< $20` budget, `< $100` mid, else premium       |
| `is_top_quartile_priced` (boolean) | `sql`   | True if `price_usd ≥` the 75th percentile across all `listed` rows. Cross-record window function. |

## Try it

```bash
folio validate examples/product-catalog
folio materialize examples/product-catalog --actor agent:demo
folio query examples/product-catalog "
  SELECT category, status, COUNT(*) AS n, ROUND(AVG(price_usd), 2) AS avg_price
    FROM records GROUP BY 1, 2 ORDER BY 1, 2
"
folio serve examples/product-catalog --port 3000 --actor human:alice
# → open http://127.0.0.1:3000/ to see every cell type live
```

## What you can actually test in the Viewer

Open the sheet in `folio serve` (or the desktop app) and click into
cells to confirm:

- **`status`** opens a 4-option dropdown (`draft` / `listed` /
  `sold_out` / `discontinued`); typing a value not in the enum is
  impossible.
- **`is_featured`** opens a 3-option dropdown
  (`(empty)` / `true` / `false`).
- **`stock`** opens a numeric input - the browser blocks
  non-numeric keys.
- **`listed_on`** opens a native date picker; `updated_at` opens a
  date-*time* picker.
- **`tags`** shows individual chips with × buttons; type a new tag
  and Enter to add, Backspace on empty input to peel one off.
- **`dimensions`** opens a JSON textarea pre-populated with the
  existing object; commit with Enter (Shift+Enter for newline,
  Escape to cancel).

Trying to commit an invalid value (e.g. `"P5"` into `priority` on
the task-tracker, or `"banana"` into `category` here) surfaces a
toast and keeps the editor open — the SDK side enforces the same
rules via `OperationError`, so CLI / SDK writes get the same
guarantee.

## Honest scope

This sheet is **not** a working store. There's no orderbook, no
fulfilment, no money movement. It exists to give every Folio type
a place to live so you can verify type-aware behaviours end-to-end.

For a real engineering use case, see
[`examples/task-tracker`](../task-tracker) (agent-driven backlog) or
[`examples/customers`](../customers) (AI-enriched customer master).
