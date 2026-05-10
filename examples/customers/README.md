# customers — Use Case 2.1: Customer Master Enrichment

A customer master where humans (or AI agents) populate the names /
countries / industries, and two derived fields fill in automatically:

| Field | Kind | Source |
|---|---|---|
| `country_code` | `python` | local script `scripts/country_to_code.py` (ISO-3166-1 alpha-2 lookup) |
| `current_revenue_usd` | `cross_sheet` | sibling sheet [`../customer-revenue`](../customer-revenue) keyed by `id` |

The cross_sheet derivation demonstrates the canonical **1:1 sidecar
pattern**: `customer-revenue` carries the same primary key as
`customers`, so each row joins naturally.

## Try it

```bash
# Validate the schema
uv run folio validate examples/customers

# Run the derivations (offline; no AI key needed)
uv run folio materialize examples/customers --actor agent:demo

# Inspect provenance
uv run folio provenance examples/customers cust_001 country_code
uv run folio provenance examples/customers cust_001 current_revenue_usd

# Open the Viewer
uv run folio serve examples/customers --port 3000 --actor agent:human
```

## What to look for in the Viewer

- `country_code` cells show a `python` dot, `current_revenue_usd`
  cells show a `cross` dot.
- `cust_006` and `cust_007` have a `??` country_code (Finland and
  the UK aren't in the demo lookup) and a null
  `current_revenue_usd` — the cross_sheet sidecar only has rows for
  `cust_001`..`cust_005`. Both gaps are surfaced visibly.
- Editing `country` re-runs the python derivation on the next
  `Materialize all` (cache invalidates on input change).
- Editing `company_name` / `country` / `industry_name` writes a
  `human` provenance entry; the existing derived value is kept
  unless you force a re-run.
