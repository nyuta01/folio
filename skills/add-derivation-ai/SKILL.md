---
name: add-derivation-ai
description: >-
  Wire up a Folio `kind: ai` derivation — the YAML file under
  `derivations/`, the prompt template (or `prompt_ref`), `output: text`
  vs `output: json` with `output_schema`, and a one-row materialize
  smoke. Invoke when the user asks to "have an LLM fill a column",
  "auto-classify", "summarize each row", or anything that maps a
  free-text field to a structured value via Claude/OpenAI/etc.
---

# Add an `ai` derivation to a Folio sheet

Author a `derivations/<target>.yaml` of `kind: ai`, declare the
contract field as `x-derived: true`, and verify with one
`folio materialize` call.

## When this skill applies

- The user says "make Folio fill this column with an LLM" or
  "classify / summarize / extract / translate every row".
- The answer is *fundamentally fuzzy* — free-text classification,
  summarization, extraction from messy inputs.
- The user wants Folio to manage the cache, retries, prompt versioning,
  and cost reporting — i.e. they don't just want a `for` loop calling
  the SDK.

This skill does **not** apply when:

- The answer is deterministic (use `kind: python` or `kind: sql`).
- The data already exists in a CSV / JSON file (use `kind: import`).
- The data lives in another Folio sheet keyed by the same PK (use
  `kind: cross_sheet` — see the `add-derivation-cross-sheet` skill).

## Prerequisites

- A working Folio sheet (see `folio-quickstart`). You should already
  have `contract.yaml` and `records.jsonl` and `folio validate <sheet>`
  exits 0.
- An `ANTHROPIC_API_KEY` (or whichever provider your AIClient targets)
  in the environment, **or** a `StubAIClient` for offline runs.
- `folio --help` shows the `materialize` subcommand.

## Procedure

1. **Pick the target field name** — what column the LLM will fill.
   Convention: snake_case ASCII, the same as other fields. Add it to
   `contract.yaml` with `x-derived: true` so it's clearly not a
   human-edited column:

   ```yaml
   - name: industry_tag
     logicalType: string
     x-derived: true
     x-inputs: [company_name]      # mirrors `inputs:` in the derivation
   ```

2. **List `inputs`** — every field the prompt reads. The cache hashes
   these, so an honest list is what makes the cache correct. If the
   prompt reads no field (very rare for `ai`), use `inputs: []`.

3. **Choose `output: text` or `output: json`.** One target → `text`.
   Multi-target → `json` plus `output_schema`. There is no "list" or
   "tuple" output — you express that as a JSON object.

4. **Write the prompt.** Use `prompt:` for one-liners; `prompt_ref:` for
   anything multi-paragraph. `prompt_ref` paths are relative to the
   sheet root and the file's bytes go into `input_hash`, so editing
   the prompt invalidates the cache (correct behaviour).

5. **Create `derivations/<target>.yaml`.** Skeleton (single target,
   text output):

   ```yaml
   # derivations/industry_tag.yaml
   targets: [industry_tag]
   inputs: [company_name]
   kind: ai
   model: claude-sonnet-4-6
   prompt: |
     Industry of {{ company_name }} in one word.
   output: text
   ```

   Multi-target with structured JSON output:

   ```yaml
   # derivations/enrich.yaml
   targets: [industry, employee_count]
   inputs: [company_name, country]
   kind: ai
   model: claude-sonnet-4-6
   prompt_ref: prompts/enrich.md
   output: json
   output_schema:
     industry: string
     employee_count: integer
   ```

6. **(Optional) Tune the loop.** `materialization:` is a sub-block:

   ```yaml
   materialization:
     respect_human_override: true   # default — skip cells a human edited
     retries: 0                     # default
     retry_delay_seconds: 1.0
   ```

   Retries cover **AIClient errors only** (timeouts, rate-limits). A
   missing `output_schema` key is a deterministic content error — it
   does not retry.

7. **Validate, then run materialize on one record.** Always smoke-test
   on a single record before letting the LLM loose on every row:

   ```bash
   folio validate ./customers
   folio materialize ./customers \
     --actor agent:demo \
     --target industry_tag \
     --record-ids cust_001
   ```

   The output is the §10.6 envelope:

   ```json
   {"materialized": 1, "skipped": 0, "failures": [], "total_cost": 0.0021}
   ```

8. **Inspect the value & provenance.** Read it back:

   ```bash
   folio list ./customers --record-ids cust_001
   folio provenance ./customers --record-id cust_001 --field industry_tag
   ```

   The provenance line includes `model`, `input_hash`, and `cost_usd`.

## Verify

```bash
folio validate <sheet>
folio materialize <sheet> --actor agent:demo --target <field> --record-ids <one_id>
```

Both should exit 0 and the envelope's `failures` should be `[]`.

## Tips & idioms

- **Substitution shape.** `{{ field }}` substitutes the **JSON-encoded**
  value — strings get quotes, integers stay bare, arrays become bracket
  lists. This keeps prompts safe against quotes / newlines in the data.
- **Deterministic first, AI fallback.** Common pattern: a `python`
  derivation that handles the easy cases, then an `ai` derivation on
  the long tail. Keep the AI rows scarce — the cache is the savings.
- **Prompts in their own file.** Once a prompt is more than ~3 lines,
  use `prompt_ref:` and put the file under `prompts/`. Reviewers hate
  diffs of multi-line YAML strings.
- **Multi-target = one cache key.** All targets in a multi-target
  derivation share an `input_hash`. They update together or stay
  cached together — that's the invariant.

## Common mistakes (don't make them)

- **Forgetting `x-derived: true` in `contract.yaml`.** The materialize
  loop still runs, but `folio status` and human editors will treat
  the field as a normal user-editable column.
- **`output: text` with multiple `targets`.** Folio will reject the
  contract — text output writes one cell. Use `output: json` +
  `output_schema`.
- **Listing inputs the prompt doesn't actually read.** The cache
  re-runs every time those (irrelevant) fields change. Keep `inputs:`
  honest.
- **Editing the prompt without expecting a re-run.** The prompt body is
  in the `input_hash`. That's the design — it means an old, outdated
  answer cannot stick around silently.
- **Hardcoding an API key in `derivations/*.yaml`.** Folio reads keys
  from the environment. The YAML stays clean and shippable.
