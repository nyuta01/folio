---
name: refresh-country-codes
description: Refresh the `country_code` derived field for every customer
             whose `country` was edited since the last materialize.
             Fully offline — runs the python kind, no API key needed.
audience: agent
tools:
  - materialize
  - list_records
  - provenance
allowed_actors:
  - "agent:*"
  - "human:*"
---

# Refresh country codes

Re-materialize `country_code` for customers whose `country` changed
since the last run. The derivation is `kind: python` against
`scripts/country_to_code.py` and ships fully offline — no
`ANTHROPIC_API_KEY` required.

## Steps

1. List customers whose `country_code` is missing or stale (e.g. `??`
   for an unmapped country name):
   ```bash
   folio list . --filter "country_code IS NULL OR country_code = '??'" \
     --fields id,company_name,country,country_code
   ```
2. Run the targeted materialize. The content-addressed cache makes
   any row whose `country` didn't change skip silently:
   ```bash
   folio materialize . country_code --actor agent:enrichment
   ```
3. Inspect the envelope's `failures` — should be `[]` for routine
   runs. If you see `??` codes, extend `scripts/country_to_code.py`'s
   `ISO_BY_NAME` mapping and re-run.
4. Verify a single record's provenance line:
   ```bash
   folio provenance . cust_001 country_code
   ```

## Notes

- `country_code` is a `python` derivation. The script lives at
  `scripts/country_to_code.py`; edit it to teach Folio new countries.
- After this skill runs, the sibling `cross_sheet` derivation
  (`current_revenue_usd`) still works independently — it joins by
  primary key, not by `country_code`.
- If you want to do the AI variant instead — classify into a free-text
  `industry_tag` — see `skills/add-derivation-ai/` in the
  [`folio-agent-skills`](https://www.npmjs.com/package/folio-agent-skills)
  npm package for the wire-up pattern.
