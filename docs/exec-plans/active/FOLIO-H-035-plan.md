# FOLIO-H-035 Plan: Confine cross_sheet sources

## Goal

Close the path-containment gap in `cross_sheet` derivations so an
untrusted sheet cannot materialize values from arbitrary local
`records.jsonl` files outside its sibling-sheet workspace.

## Scope

- `src/folio/kinds/_cross_sheet.py` — reject absolute `source_sheet`
  values, resolve relative paths against the calling sheet, require the
  resolved source to remain inside the calling sheet's parent directory,
  and require a valid foreign Folio sheet before reading records.
- `tests/test_kind_cross_sheet.py` — add regressions for absolute
  paths, parent-directory escapes, symlink escapes, and records-only
  directories.
- `scripts/harness_drift.py` — pin the resolver ingredients and
  regression names so future refactors cannot silently reopen the class.
- Specs, public docs, and handoff artifacts — update the documented
  `cross_sheet` boundary from "path to records" to "validated sibling
  Folio sheet".

## Out of scope

- A general workspace or multi-root registry for cross-sheet reads.
  Phase 6 can add that explicitly; Phase 4 remains a sibling-sheet
  feature.
- Changing the materialize API or provenance schema.
- Restoring the retired MCP server surface.

## Evidence

- `uv run pytest tests/test_kind_cross_sheet.py -q` passes.
- `python3 scripts/harness_drift.py` passes.
- `make verify` passes before this task is marked complete.

## Observation

Security review found that `resolve_foreign_sheet()` accepted
`source_sheet` as an unconstrained path, resolved it with
`Path(sheet_path) / source_sheet`, and only required `records.jsonl`.
That let a malicious derivation read records from directories outside
the caller's intended sheet workspace and copy selected fields into the
attacker-controlled sheet during materialize.

## Decision

Keep `cross_sheet` as a sibling-sheet join. `source_sheet` must be
relative, the resolved real path must stay under `Path(sheet).parent`,
and the source must load as a Folio sheet (`contract.yaml`) before
`records.jsonl` is read. Resolving before the containment check also
blocks sheet-local symlinks that point outside the parent directory.

## Permanent Fix

The resolver now enforces the path boundary and validates the foreign
contract. The cross-sheet test suite covers absolute path rejection,
`..` escape rejection, symlink escape rejection, and the historical
records-only directory bypass. `scripts/harness_drift.py` rejects
removing the resolver checks or these regression tests.

## Next Check

If Folio later gains explicit workspace roots for cross-sheet reads,
make that root a first-class resolver parameter and add a regression that
proves materialize cannot read beyond it.
