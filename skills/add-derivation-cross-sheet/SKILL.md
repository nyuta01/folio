---
name: add-derivation-cross-sheet
description: >-
  Wire up a Folio `kind: cross_sheet` derivation — pull a field from a
  sibling Folio sheet that shares the same primary key (the 1:1
  sidecar pattern). Invoke when the user wants to "join two sheets",
  "pull revenue from the finance sheet into customers", or otherwise
  copy values keyed by PK from one sheet to another.
---

# Add a `cross_sheet` derivation to a Folio sheet

Author a `derivations/<target>.yaml` of `kind: cross_sheet` that joins
this sheet 1:1 with a sibling sheet on **the calling sheet's primary
key**, and verify with one materialize.

## When this skill applies

- Two Folio sheets exist side by side, share an identifier 1:1, and
  the user wants one of them to pull a field from the other.
- The classic shape: a `customers/` sheet next to a `customer-revenue/`
  sheet, both keyed by `id`. `customers` wants `current_revenue_usd`
  copied in from `customer-revenue`.
- The user wants Folio's contract on the foreign sheet enforced (so
  bad foreign data fails validation rather than poisoning the join).

This skill does **not** apply when:

- The foreign source is **not** a Folio sheet (CSV, JSON file, HTTP
  endpoint) — use `kind: import` instead.
- The join key is **not** the calling sheet's primary key — the
  built-in `cross_sheet` only matches the foreign `key_field`
  against the calling sheet's PK. Use `import` or a `python`
  derivation that does the lookup explicitly.
- The relationship is 1:N or M:N — `cross_sheet` writes one cell per
  calling-sheet record. Aggregations need `kind: sql` or `kind: python`.

## Prerequisites

- The calling sheet exists, validates, and has the target field
  declared `x-derived: true` in `contract.yaml`.
- The foreign sheet exists at a path resolvable from the calling
  sheet (typically `../<sibling>`), validates, and contains the
  field you want to copy.
- Both sheets agree on the PK value space (identical strings, same
  case, no leading/trailing whitespace).

## Procedure

1. **Confirm the sidecar layout.** Folio resolves `source_sheet`
   relative to the calling sheet's root. The conventional layout:

   ```text
   customers/                         customer-revenue/
   ├── contract.yaml      ──→         ├── contract.yaml
   ├── records.jsonl                  ├── records.jsonl
   │                                      (id, revenue_usd, ...)
   └── derivations/
       └── revenue.yaml   ◀── reads from ../customer-revenue
   ```

2. **Add the target field to `contract.yaml`** of the calling sheet,
   marked derived:

   ```yaml
   - name: current_revenue_usd
     logicalType: number
     x-derived: true
     x-inputs: []          # join is by PK, no other inputs
   ```

3. **Write `derivations/<target>.yaml`** in the calling sheet.
   Single-target skeleton:

   ```yaml
   # customers/derivations/revenue.yaml
   targets: [current_revenue_usd]
   inputs: []                          # join is by PK, no other inputs
   kind: cross_sheet
   source_sheet: ../customer-revenue   # path relative to this sheet
   key_field: id                       # field on the foreign sheet
   value_field: revenue_usd            # field whose value to copy
   ```

   Multi-target (all updated atomically, share one `input_hash`):

   ```yaml
   targets: [current_revenue_usd, contract_value_usd, finance_as_of]
   inputs: []
   kind: cross_sheet
   source_sheet: ../customer-revenue
   key_field: id
   value_fields:                       # mutually exclusive with value_field
     current_revenue_usd: revenue_usd
     contract_value_usd: contract_value_usd
     finance_as_of: as_of
   ```

4. **Validate both sheets, then materialize the calling one.**
   `folio validate` runs against the foreign sheet too — broken foreign
   data shows up here, not silently in the join.

   ```bash
   folio validate ./customers
   folio validate ./customer-revenue
   folio materialize ./customers --actor agent:demo --target current_revenue_usd
   ```

   The §10.6 envelope:

   ```json
   {"materialized": 2, "skipped": 0, "failures": [], "total_cost": 0.0}
   ```

5. **Spot-check a row.**

   ```bash
   folio query ./customers \
     "SELECT id, current_revenue_usd FROM records ORDER BY id LIMIT 5"
   ```

## Verify

```bash
folio validate <sheet>
folio validate <foreign_sheet>
folio materialize <sheet> --actor agent:demo --target <field>
```

All three should exit 0. The materialize envelope's `failures` should
be `[]`. Records with no foreign match keep the field `null` and are
**not** counted as failures (see below).

## Cache behaviour

`input_hash` for a `cross_sheet` cell includes:

- the canonical JSON of every input value (often empty),
- the calling sheet's primary key value,
- the SHA-256 of the foreign sheet's `records.jsonl`,
- the SHA-256 of the derivation file.

That third item is load-bearing: edit the foreign `records.jsonl`,
*every* calling-side row's hash changes, and the next materialize
re-joins everything. Right behaviour when you don't know which
foreign rows changed.

If the foreign sheet is huge and changes constantly, prefer a
snapshot via `kind: import` instead.

## "No match" semantics

If the foreign sheet has no row whose `<key_field>` equals the
calling sheet's PK, Folio writes nothing for that cell, the value
stays `null`, and **nothing is reported on the envelope**. Missing
foreign rows are an expected case for `cross_sheet`.

If you want a *failure* in that case, layer a `kind: python`
derivation downstream that asserts the field is non-null after
`cross_sheet` runs.

## Common mistakes (don't make them)

- **Joining by a non-PK field.** `cross_sheet` matches the foreign
  `key_field` against the **calling sheet's PK**, not against an
  arbitrary calling-side input. If you need lookup by an input,
  reach for `import` or `python`.
- **Both `value_field` and `value_fields` set.** They are mutually
  exclusive. Folio rejects.
- **Wrong relative path on `source_sheet`.** Paths are relative to
  the *calling sheet's root*, not to `derivations/`. Most sidecar
  setups use `../<other_sheet>`.
- **PK mismatch.** Trailing whitespace, case differences, or
  numeric-vs-string discrepancies will silently produce no match
  (see "No match" above). Normalize on the source side.
- **Foreign records edited but the calling sheet not re-materialized.**
  The cache flips correctly on the next run; what's wrong is letting
  agents read the stale `current_revenue_usd` in between. Re-run
  materialize after foreign updates, or schedule it.
