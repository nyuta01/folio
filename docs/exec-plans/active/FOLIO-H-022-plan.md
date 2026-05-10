# FOLIO-H-022 Plan: Frictionless datapackage.json Generation

## Goal

Land the Frictionless Data Package descriptor generator named in
§14.2 so external tools (`frictionless`, `datacontract-cli`, etc.)
can read a Folio sheet without bespoke glue.

## Scope

- `src/folio/datapackage.py`:
  - `LOGICAL_TO_FRICTIONLESS` mapping (string → string, integer →
    integer, number → number, boolean → boolean, date → date,
    timestamp → datetime, array → array, object → object).
  - `build_descriptor(contract, *, records_path="records.jsonl") ->
    dict` producing the Frictionless v1 descriptor named in the
    design overview mapping table.
  - `write_datapackage(sheet_path, output_path)` that loads the
    contract and writes the descriptor to `output_path` as
    pretty-printed JSON.
- `folio export datapackage <sheet> [--out <path>] [--stdout]`
  CLI sub-command. Writes to `<sheet>/datapackage.json` by default;
  `--stdout` prints the JSON to stdout for piping.
- `tests/test_datapackage.py` covers: every logicalType maps to its
  Frictionless type, primaryKey is surfaced as a string scalar,
  description fields are propagated, x-derived fields appear in the
  descriptor (so the Frictionless schema is a faithful projection),
  multi-field primaryKey handling (currently rejected at contract
  load time, so the export reflects exactly one), and missing
  description is omitted rather than emitted as `"description":
  null`.
- CLI test for `folio export datapackage` with `--stdout` and with a
  default output file.
- `scripts/harness_check.py` requires the new module and tests.

## Out of scope

- Live `frictionless` library validation. The descriptor builder
  produces valid JSON shape per §14.2; running `frictionless validate`
  on it is left to the user (and could land as a `--validate` flag
  in a follow-up that adds the dependency to a dev extra).
- Generating datapackage.json automatically on every sheet write.
  Phase 4 keeps it as an opt-in export.

## Evidence

- `make verify` passes locally with the new pytest cases.
- `folio export datapackage <sheet> --stdout` prints a JSON object
  whose `resources[0].schema.fields` matches the contract.

## Observation

Phase 4 has shipped extension kinds, and the design overview §14.2
already documents the ODCS → Frictionless mapping table. Without
this generator, every external consumer that wants to read a Folio
sheet has to re-derive the projection.

## Decision

- Keep the descriptor generator pure: it takes a `Contract` and
  returns a `dict`. The CLI is the only side-effecting layer.
- Map `description` only when present so the descriptor stays
  minimal and round-trips cleanly through `json.dumps(sort_keys=True)`.
- Do not depend on `frictionless` at runtime. The descriptor we
  produce is structurally valid; users who want full validation
  install `frictionless` separately and run it themselves.

## Permanent Fix

- `make verify` runs the new pytest cases. A regression in the
  logicalType → Frictionless type mapping fails the gate.
- `scripts/harness_check.py` requires `src/folio/datapackage.py`
  and `tests/test_datapackage.py`.

## Next Check

`FOLIO-H-021` adds `python` and `cross_sheet` kinds. Their derived
fields will appear in the Frictionless descriptor automatically
because the generator iterates the contract's properties without
discriminating on `x-derived`.
