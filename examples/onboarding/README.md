# onboarding — Use Case 2.4: Operational Worklist

A new-hire onboarding worklist. Each row is one onboarding flow
that an HR partner owns end-to-end.

| Field | Owner | Notes |
|---|---|---|
| `hire_name`, `role`, `start_date` | `agent:human` | Captured at hire time. |
| `owner` | `agent:human` | HR partner email. |
| `status` | `agent:human` | `pending` / `in_progress` / `complete`. |
| `checklist` | `agent:human` | JSON array of `{label, done}` items. |
| `progress` | derived (`python`) | `<done>/<total>` derived from `checklist`. |

## Try it

```bash
uv run folio validate examples/onboarding
uv run folio materialize examples/onboarding --actor agent:demo

uv run folio query examples/onboarding \
  "SELECT status, COUNT(*) AS n FROM records GROUP BY status"

uv run folio serve examples/onboarding --port 3000 --actor agent:human
```

## Pattern this captures

Repetitive but not-fully-automatable processes. The `checklist`
column is **structured JSON** that humans tick off in the Viewer
(or via `folio upsert`); the python derivation summarizes it on
every change so the worklist always shows current progress
without recomputing in the UI.
