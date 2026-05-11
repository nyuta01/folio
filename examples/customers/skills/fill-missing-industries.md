---
name: fill-missing-industries
description: Fill the `industry_tag` field for every customer that's
             still null. Uses the existing `ai` derivation and reports
             cost + failures.
audience: agent
tools:
  - materialize
  - list_records
  - provenance
allowed_actors:
  - "agent:*"
  - "human:*"
---

# Fill missing industries

Refresh `industry_tag` for every customer where it is still `null`,
then verify the result.

## Steps

1. Identify candidates:
   ```bash
   folio list . --filter "industry_tag IS NULL" --fields id,company_name,country
   ```
2. Run the targeted materialize (cache makes already-filled rows skip):
   ```bash
   folio materialize . industry_tag --actor agent:enrichment
   ```
3. Inspect the envelope's `failures` array. For each failure, log the
   `record_id` and the `error_type` and decide whether to retry.
4. Spot-check 2–3 newly filled rows by reading the AI provenance line,
   which carries the prompt's `input_hash`, the model, and `cost_usd`:
   ```bash
   folio provenance . cust_001 industry_tag
   ```

## Notes

- `industry_tag` is an `ai` derivation. Make sure the runtime has an
  `ANTHROPIC_API_KEY` exported (or inject a `StubAIClient` for tests).
- If the materialize envelope shows `total_cost > 0`, log it — Folio
  doesn't bill, but the team's monthly LLM spend does.
- A long-tail with many failures probably means the prompt needs a
  retry policy. Set `materialization.retries: 2` on the derivation if
  you see transient AIClient errors.
