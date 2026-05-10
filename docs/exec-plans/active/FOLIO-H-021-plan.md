# FOLIO-H-021 Plan: python and cross_sheet Extension Kinds

## Goal

Complete the Phase 4 extension-kind set by shipping `python` (calls
into a `scripts/` helper from Phase 2) and `cross_sheet` (reads a
sibling sheet) so multi-sheet derivations and bespoke logic become
expressible without leaving the materialize loop.

## Scope

- `src/folio/kinds/_python.py`:
  - `PythonDerivation` Pydantic v2 model with required `script` (a
    basename under `scripts/` per Phase 2) and optional `output:
    text|json` plus `output_schema` for multi-target.
  - `execute_python(derivation, inputs, *, sheet_path, sheet_id)`
    invokes the script via `folio.scripts.run_script`, passing the
    inputs dict as a JSON-encoded argument (after the sheet path
    `argv[1]`), parses stdout per the same text/json correspondence
    as the ai kind, and surfaces non-zero exit codes as
    `FolioError`.
- `src/folio/kinds/_cross_sheet.py`:
  - `CrossSheetDerivation` model with `source_sheet` (relative
    path), `key_field`, and a `value_field` / `value_fields`
    pair (XOR, mirroring the import kind).
  - `execute_cross_sheet(derivation, primary_key_value, *,
    sheet_path)` resolves the foreign sheet, reads its
    `records.jsonl`, finds the row whose `key_field` matches
    `primary_key_value`, and returns the value map. Returns `{}`
    on no match.
  - `foreign_records_hash(sheet_path, source_sheet) -> str`
    streamed-SHA-256 over the foreign records file so cross-sheet
    cache keys invalidate when the foreign sheet changes.
- Extend the `Derivation` discriminated union to include both new
  kinds.
- `Sheet.materialize` adds branches for `PythonDerivation` and
  `CrossSheetDerivation`. The python kind caches results keyed by
  inputs + script-file-hash. The cross_sheet kind caches results
  keyed by primary_key_value + foreign-records hash + derivation
  file hash.
- `tests/test_kind_python.py` covering: text-output single-target,
  json-output single-target, json-output multi-target with schema,
  failed-exit-code surfacing, invalid-JSON rejection,
  missing-script rejection, and the Sheet.materialize integration.
- `tests/test_kind_cross_sheet.py` covering: foreign sheet match
  by primary key, no-match no-op, multi-value mapping, missing
  foreign sheet rejection, foreign-records hash invalidation.
- `scripts/harness_check.py` requires the new modules and tests.

## Out of scope

- Sandboxing python kind beyond the existing subprocess isolation
  in `folio.scripts.run_script`. Re-evaluate if multi-tenant use
  appears.
- A general "load a Python callable in-process" mode for the
  python kind. Subprocess execution keeps the materialize loop
  side-effect-bounded.
- Multi-workspace routing for cross_sheet. Phase 6 introduces a
  workspace concept; for now `source_sheet` is a relative path.

## Evidence

- `make verify` passes locally with the expanded `python-test`.
- A python kind script that prints `Software` populates the target
  for the matching record.
- A cross_sheet derivation against a sibling sheet populates the
  expected fields.

## Observation

`FOLIO-H-014` shipped the `scripts/` runtime; `FOLIO-H-020` shipped
the kind dispatch surface. Without `python` and `cross_sheet` the
Phase 4 extension set is incomplete.

## Decision

- Use `folio.scripts.run_script` for the python kind so the
  subprocess isolation, runtime cache placement (ADR-0008), and
  safe-name regex from `FOLIO-H-014` apply automatically.
- Resolve `source_sheet` as a path relative to the current sheet
  (e.g., `../parent-customers`) and validate that the resolved
  target contains a `contract.yaml` + `records.jsonl`. Cross-sheet
  paths can legitimately escape the current sheet directory (that's
  the whole point of the kind), so the path-traversal guard from
  the import kind does not apply here.
- Fold the foreign `records.jsonl` content hash into the cache key
  so a derivation re-runs when the upstream sheet changes.

## Permanent Fix

- `make verify` runs the new pytest cases.
- `scripts/harness_check.py` requires the two new modules and the
  two new test files.
- The cross-sheet hash test pins the invalidation invariant so a
  refactor cannot accidentally cache stale foreign data.

## Next Check

`FOLIO-H-024` and `FOLIO-H-025` ship the Viewer; the existing
materialize CLI keeps working unchanged.
