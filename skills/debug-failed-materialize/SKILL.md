---
name: debug-failed-materialize
description: >-
  Diagnose per-cell failures from `folio materialize` — read the §10.6
  envelope, locate the bad cell in `provenance.jsonl`, narrow with
  a positional target + `--ids`, and re-run with `--force`. Invoke
  when the user reports "materialize is failing", "this column came
  back null", "AI calls timing out", or pastes a non-empty
  `failures[]` list from the envelope.
---

# Debug a failed `folio materialize`

`folio materialize` exits **0** even on partial failures — bad cells
are reported in the envelope's `failures[]`. This skill walks an
agent through reading that envelope, narrowing scope to the offending
cell(s), and re-running until `failures` is empty.

## When this skill applies

- The user pasted a `materialize` envelope where `failures` is non-empty.
- The user says a derived column "came back null" or "didn't update".
- The user says materialize is "stuck", "slow", or "running forever".
- A CI gate failed because `failures | length > 0`.

This skill does **not** apply when:

- The user has a *contract* error (`folio validate` fails). That's a
  schema problem, not a materialize problem — fix `contract.yaml` first.
- The cells succeeded but the *values* are wrong. That's a prompt /
  script bug — narrow with the positional target + `--ids` +
  `--force` to iterate, but it's not a "failure" in the envelope
  sense.

## Recap: the §10.6 envelope

Every `folio materialize` run prints:

```json
{
  "materialized": 12,
  "skipped": 7,
  "failures": [
    {"record_id":"cust_006","field":"industry_tag",
     "error":"...","error_type":"FolioError"}
  ],
  "total_cost": 0.0034
}
```

| Field | Meaning |
|---|---|
| `materialized` | Cells written this run. |
| `skipped` | Cells avoided (cache hit, `respect_human_override`, no foreign match for `cross_sheet`, etc.). |
| `failures` | Per-record × field errors. Other records keep going. |
| `total_cost` | Sum of `cost_usd` from `ai` calls. |

**A non-zero exit code is not how partial failures are signalled.**
`failures: []` is the only success criterion.

## Procedure

1. **Capture the envelope and pretty-print it.**

   ```bash
   out=$(folio materialize ./<sheet> --actor agent:debug)
   echo "$out" | jq
   ```

   If `failures` is empty, the run is healthy — the user's complaint
   is probably about *values*, not failures. Jump to step 6.

2. **Group failures by `(field, error_type)`** to see if it's one bug
   or many:

   ```bash
   echo "$out" | jq '[.failures[] | {field, error_type}] | group_by(.) |
     map({key: (.[0].field + ":" + .[0].error_type), count: length})'
   ```

   - All failures share `(field, error_type)` → one bug; pick any
     `record_id` to reproduce.
   - Different `(field, error_type)` pairs → multiple bugs; treat
     each group independently.

3. **Narrow the next run to one cell.** Pick the smallest reproducible
   case from step 2 — one target, one record:

   ```bash
   folio materialize ./<sheet> <field> \
     --actor agent:debug \
     --ids <record_id> \
     --force
   ```

   `folio materialize` takes the target as a positional argument
   (one at a time); `--ids` is comma-separated or repeatable.

   `--force` ignores the cache so you re-execute even if the input
   hasn't changed. Without it, after the first failure the cell may
   still cache-miss but you risk wasted "skipped" runs while iterating.

4. **Read the `error` and `error_type`.** The pattern that diagnoses
   most failures:

   | `error_type` (typical)         | What it usually means |
   |---|---|
   | `FolioError` — "script exited with N" | Python derivation crashed. Run the script directly with the row's input JSON to repro. |
   | `FolioError` — "AIClient call failed" | Provider timeout / 5xx / rate limit. Check `ANTHROPIC_API_KEY`, retry; consider raising `materialization.retries`. |
   | `FolioError` — "missing key in output_schema" | LLM returned JSON missing a required key. Tighten the prompt or the schema. |
   | `FolioError` — "no rows in foreign sheet" | Misconfigured `cross_sheet` `source_sheet` path. Check it's relative to the calling sheet, not to `derivations/`. |
   | `FolioError` — "primary key not unique" | The sheet itself is broken; this is upstream of materialize. Run `folio validate`. |

5. **Inspect provenance to confirm the fix.** After a successful re-run,
   the cell should have a fresh provenance line:

   ```bash
   folio provenance ./<sheet> <record_id> <field>
   ```

   `folio provenance` takes the record ID and field as positional
   arguments. Add `--history` to see every entry in the append-only
   log instead of just the latest.

   You should see a new `at:` timestamp, the matching `actor:`, and
   for `ai` cells a populated `model:` and `cost_usd:` (unless the
   model is unknown to the price table — that's `null` by design).

6. **(If `failures` was empty but values look wrong.)** This is a
   logic bug, not a failure:

   - Read the cell's provenance line — what `source` produced it
     (`ai`, `python`, `cross_sheet`, `human`)?
   - If `source: human`, the cell was edited and `respect_human_override`
     (default `true`) is preserving the edit. Use `--force` or unset
     the override on the derivation.
   - If `source: cross_sheet` and the value is `null`, there was no
     foreign match — that's silent by design (see the
     `add-derivation-cross-sheet` skill).
   - Otherwise, fix the derivation (prompt / script / schema) and
     repeat from step 3 with `--force`.

7. **Once the one-record case is healthy, broaden.**

   ```bash
   folio materialize ./<sheet> <field> --actor agent:debug
   ```

   If `failures` is `[]`, drop the positional target and run
   everything.

## Verify

```bash
folio materialize ./<sheet> --actor agent:debug
echo $? ; echo "$last" | jq '.failures | length'
```

Exit code is `0` and `failures | length == 0`. To turn this into a
CI gate:

```bash
out=$(folio materialize ./<sheet> --actor agent:ci)
echo "$out"
[[ "$(echo "$out" | jq '.failures | length')" == "0" ]] || exit 1
```

## Common mistakes (don't make them)

- **Trusting exit code alone.** `folio materialize` exits 0 with a
  non-empty `failures[]`. Always inspect the envelope.
- **Re-running without `--force` while debugging.** The cache may
  hide your fix attempts as "skipped". Use `--force` until the cell
  goes green, then drop it.
- **Conflating "skipped" with "failed".** `skipped` includes cache
  hits, `respect_human_override` skips, and "no match" for
  `cross_sheet` — all benign. The only red signal is `failures[]`.
- **Editing a derivation file mid-debug and forgetting it invalidates
  the cache.** That's correct behaviour, but it means the next run
  will re-execute many cells. Narrow with a positional target +
  `--ids` during iteration.
- **Filing a bug against Folio for a `python` script crash.** The
  `error` field reproduces the user's script's exception verbatim;
  the bug is in their derivation, not in Folio. Repro by running the
  script directly with the input JSON.

## See also

- The `add-derivation-ai` and `add-derivation-cross-sheet` skills for
  authoring the YAML in the first place.
- `folio status <sheet>` for a roll-up of which derived fields are
  derived vs human vs missing across the whole sheet.
