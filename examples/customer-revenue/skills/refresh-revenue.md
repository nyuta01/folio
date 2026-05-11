---
name: refresh-revenue
description: Re-import the latest revenue numbers from finance and
             let any downstream cross-sheet derivations pick them up
             on the next materialize.
audience: human
arguments:
  - name: as_of
    description: ISO date for the snapshot tag, e.g. 2026-05-31.
    required: true
allowed_actors:
  - "human:finance:*"
  - "human:ops"
---

# Refresh revenue

Finance exports a `customer-revenue-{as_of}.csv` every month. Push
the new numbers into this sheet so the `customers` sidecar can pick
them up.

## Steps

1. Place the file: copy `customer-revenue-{as_of}.csv` from the
   shared drive to this sheet's `imports/` directory (create it if
   missing).
2. Upsert from JSONL form:
   ```bash
   csvkit | folio upsert . --actor human:finance:you --file -
   ```
3. Update the `as_of` field on every record you just touched. The
   sidecar's downstream `customers.current_revenue_usd` derivation
   reads this; stale values silently leak through otherwise.
4. Notify the customers sheet: `folio materialize ../customers current_revenue_usd --actor human:ops`.

## Notes

- The cross-sheet hash includes this sheet's `records.jsonl`, so the
  re-materialize is automatic on next run, but you should kick it
  manually so dashboards reflect the new month immediately.
- If finance ships a partial update, only the touched records'
  derivations will re-run on the customers side — caching handles
  the rest.
