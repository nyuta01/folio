---
name: restock-suggestions
description: >-
  Surface every `listed` product that is out of stock (`in_stock=false`)
  and propose a restock quantity per row. Read-only - human approves
  before any write.
audience: agent
arguments:
  - name: target_days_of_supply
    description: Days of supply to size the restock against (e.g. 30).
    required: true
tools:
  - query
  - list_records
allowed_actors:
  - "agent:*"
  - "human:*"
---

# Restock suggestions

Produce a markdown table the human can skim and approve before any
write hits the sheet.

## Steps

1. **Pull empty shelves**:
   ```bash
   folio query . "
     SELECT id, name, category, price_tier, tags
       FROM records
      WHERE status = 'listed'
        AND in_stock = false
      ORDER BY category, price_usd DESC
   "
   ```
2. **Estimate weekly velocity** from the `updated_at` cadence (no
   real velocity column exists - this skill is a *suggestion*
   surface, not an authoritative forecast). For each row guess a
   conservative number of units per week based on `category` and
   `price_tier`:
   - book / food / toy + `budget` → 50/week
   - book / food / toy + `mid`    → 20/week
   - clothing / electronics       → 10/week
   - anything `premium`           → 5/week
3. **Multiply** by `{target_days_of_supply} / 7` to get a target
   restock quantity. Round up to the nearest 10.
4. **Render** a markdown table for the human:
   `| id | name | category | suggested_restock | reason |`
   The `reason` cell should cite the velocity bucket so the human
   can sanity-check the number.

## Notes

- This skill **never writes** - it only surfaces a proposal. Once
  the human says "yes, apply this", a separate `apply-restock`
  skill (not bundled) would handle the upserts.
- `is_top_quartile_priced` is a useful sanity check: if a P75-priced
  item shows zero stock for weeks, the inventory miss is costing
  more than its share of revenue and the human should escalate
  rather than just refill at the suggested rate.
