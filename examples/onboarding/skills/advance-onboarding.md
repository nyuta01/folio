---
name: advance-onboarding
description: Walk the next pending onboarding record forward by one
             checklist item, update progress, and re-materialize the
             status.
audience: both
arguments:
  - name: hire_id
    description: Onboarding record id, e.g. ob_002.
    required: true
allowed_actors:
  - "human:hr:*"
  - "human:buddy"
---

# Advance onboarding for {hire_id}

Mark one checklist item complete on `{hire_id}` and let the
derivations recompute the rolled-up `progress` / `status`.

## Steps

1. Open the record:
   ```bash
   folio list . --filter "id = ?" --param {hire_id}
   ```
2. Decide which checklist item is being completed today. Update the
   `checklist[].done` flag for that label:
   ```bash
   folio upsert . --actor human:buddy --file - <<'JSON'
   {"id": "{hire_id}", "checklist": [/* full list with the one item flipped */]}
   JSON
   ```
   Folio merges on `primaryKey`; you do need to send the whole
   `checklist` array because Folio doesn't do partial array merges.
3. Re-materialize derived fields:
   ```bash
   folio materialize . --actor human:buddy --ids {hire_id}
   ```
4. Confirm the rolled-up state moved the right direction:
   ```bash
   folio list . --filter "id = ?" --param {hire_id} --fields id,status,progress
   ```

## Notes

- `status` flips from `pending` → `in_progress` on the first
  completion and `in_progress` → `complete` when every item flips.
- If the hire churned (left before completion), do **not** delete
  the record. Run `folio upsert` with `status: cancelled` and a
  human-override note — provenance is more useful than a clean
  table.
