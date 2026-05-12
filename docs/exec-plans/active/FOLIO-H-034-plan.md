# FOLIO-H-034 Plan: Lock Viewer Query Sandbox Regressions

## Goal

Close the Viewer `/api/query` file-read finding as a permanent invariant. The
root DuckDB sandbox from `FOLIO-H-032` already prevents local file reads; this
task adds the missing HTTP-layer regression, rejects stacked statements, and
turns the query sandbox shape into a drift check.

## Scope

- `src/folio/_query.py`: reject stacked SQL statements while still allowing a
  single trailing semicolon.
- `tests/test_sheet.py`: prove stacked statements are rejected at the SDK
  query surface.
- `tests/test_viewer.py`: prove `POST /api/query` does not return local file
  contents through DuckDB file-reading table functions.
- `scripts/harness_drift.py`: fail if query execution stops disabling DuckDB
  external access, stops loading records through Python, reintroduces DuckDB
  `read_json` setup, or loses the Viewer HTTP regression.
- Docs and PDCA artifacts: record the Viewer-specific security follow-up.

## Out of Scope

- Removing the Viewer query route. It remains a local Viewer read feature.
- Adding authentication to the Viewer; the current product model is still
  local-first with localhost default binding.

## Evidence

- `uv run pytest tests/test_sheet.py tests/test_viewer.py -q` passes.
- `make verify` passes.

## Observation

Aardvark reported that Viewer `POST /api/query` exposed request-controlled SQL
over HTTP, and the old leading-keyword-only DuckDB helper allowed file-reading
SELECT table functions. `FOLIO-H-032` fixed the root local-file-read primitive
by preloading records through Python and disabling DuckDB external access, but
Viewer lacked a direct regression and DuckDB still accepted stacked statements.

## Decision

Keep the query feature, but make its security properties explicit and
mechanically checked. Caller SQL must be a single SELECT-style statement, must
run only after Folio has loaded records into an in-memory relation, and must
execute with DuckDB external access disabled. The Viewer route inherits the SDK
guard and has its own HTTP regression.

## Permanent Fix

`tests/test_viewer.py::test_query_sandbox_blocks_external_file_reads` posts a
`read_csv(<outside file>)` query and asserts the local secret is not returned.
`tests/test_sheet.py::test_query_rejects_stacked_statement` ensures a leading
SELECT cannot smuggle a later statement. `make drift-check` rejects removal of
the core sandbox ingredients or the Viewer regression.

## Next Check

Any future query, SQL derivation, or Viewer query-route changes must keep both
the SDK query tests and the Viewer HTTP regression passing. If Viewer moves
beyond localhost-only assumptions, add authentication/authorization as a
separate product change rather than weakening the SQL sandbox.
