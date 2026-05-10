# FOLIO-H-009 Plan: Derivation Parsing and Import Kind

## Goal

Land the parsing and validation surface for `derivations/<field>.yaml`
plus the `import` kind so subsequent tasks (cache, ai kind, CLI) can
build on a typed object graph without re-deriving the YAML shape.

## Scope

- `src/folio/derivation.py`:
  - `MaterializationConfig` Pydantic model (`trigger: on_demand`,
    `respect_human_override: bool`).
  - `AIDerivation` and `ImportDerivation` Pydantic models with a
    `kind` discriminator.
  - `Derivation` discriminated-union alias.
  - `load_derivation(path)` for a single file and
    `load_derivations(sheet_path)` for the whole directory.
  - `detect_cycles(by_target)` and `topological_sort(by_target)` over
    the target → derived-input DAG.
  - Cross-derivation invariants surfaced as `DerivationError`:
    duplicate target across files, multi-target without
    `output_schema`, `output_schema` keys not matching `targets`,
    `prompt` and `prompt_ref` collision (exactly one allowed),
    `value_field` and `value_fields` collision (exactly one allowed),
    multi-target import without `value_fields`.
- `src/folio/_import_kind.py`:
  - `load_import_source(sheet_path, source)` for `*.csv`, `*.jsonl`,
    and `*.json` sources rooted in the sheet directory.
  - `apply_import(derivation, source_rows, primary_key_value)`
    returning `{target_field: value}` or `{}` when the source has no
    matching row.
  - `ImportSourceError` for missing files, ambiguous matches, and
    unsupported extensions.
- `tests/fixtures/import-kind/customers.csv` and
  `tests/fixtures/import-kind/legacy.jsonl` for deterministic source
  fixtures.
- `tests/test_derivation.py` covering: minimal `ai` derivation, multi-
  target `ai` derivation with `output_schema`, multi-target rejection
  without `output_schema`, prompt-source collision, prompt-source
  missing, single-target `import` with `value_field`, multi-target
  `import` with `value_fields`, value-mapping collision, malformed
  YAML, unknown `kind`, target/output_schema-key mismatch, duplicate
  target across files, and `detect_cycles` / `topological_sort` over
  a representative DAG.
- `tests/test_import_kind.py` covering: CSV/JSONL/JSON source loading,
  missing file, unsupported extension, ambiguous match, single-value
  vs multi-value mapping, and the no-match no-op path.
- `scripts/harness_check.py` requires `src/folio/derivation.py`,
  `src/folio/_import_kind.py`, both new test files, and the import-
  kind fixture directory.

## Out of scope

- Integrating derivation cycle detection into `Sheet` /
  `folio validate`. That belongs to `FOLIO-H-012` together with the
  CLI verbs.
- `input_hash`, cache layer, and `provenance.jsonl`. `FOLIO-H-010`.
- The `ai` kind driver. `FOLIO-H-011`.
- ADR additions. Pickup once a binding implementation choice (e.g.,
  source file matching beyond primary key) needs anchoring.

## Evidence

- `make verify` passes, with the pytest count growing past the
  current 62.
- Every parametrized rejection case in `test_derivation.py` raises
  `DerivationError`.
- `test_import_kind.py` round-trips a CSV fixture and returns the
  expected `{target_field: value}` mapping.

## Observation

Phase 1 is now spec'd at
`docs/product-specs/phase-1-derivations-and-provenance.md`, but the
repository still has no code that reads `derivations/<field>.yaml`.
Without a typed parsing surface, the cache (`H-010`) and ai kind
(`H-011`) tasks would re-derive the YAML shape ad hoc and risk
diverging from the spec.

## Decision

- Use Pydantic v2 with a discriminator on `kind` so each derivation
  body is validated against exactly one model. The discriminator
  rejects unknown kinds early.
- Match import sources against a record's primary-key value (per the
  example in design overview §8.2) and treat any other matching
  semantics as a future extension. `key_field` names the column in
  the **source** that compares against the record's primary key.
- Keep `Sheet` untouched for now. Standalone functions
  (`load_derivations`, `detect_cycles`, `topological_sort`,
  `load_import_source`, `apply_import`) make the surface easy to test
  and let the CLI integration happen on the same loop as the
  materialize verb (`H-012`).
- Treat fixtures as test-only data under `tests/fixtures/import-kind/`
  so no sample sheet under `tests/` accidentally bundles a generated
  cache or runtime, preserving ADR-0008.

## Permanent Fix

- `scripts/harness_check.py` requires the new derivation module, the
  import-kind module, both test files, and the fixture directory.
  Removing any of them fails `make verify`.
- Pydantic discriminator + `extra="forbid"` rejects unknown kinds and
  unknown derivation attributes at parse time, so a future
  derivation file with a typo cannot pass silently.
- Cycle detection on the target → derived-input DAG raises
  `DerivationError` with the offending cycle, which is the only
  Phase 1 invariant that cannot be surfaced by per-file Pydantic
  validation.

## Next Check

`FOLIO-H-010` should add `input_hash` per RFC 8785 (using the
`rfc8785` package), the cache root at
`<user-cache>/folio/<sheet-id>/cache/`, and the `provenance.jsonl`
append + latest-resolution + history helpers, with stale detection
across edits to the prompt body, the derivation file, the input
value, and the model id.
