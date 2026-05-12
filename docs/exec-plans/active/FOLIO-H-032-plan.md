# FOLIO-H-032 Plan: Sandbox DuckDB Query File Access

## Goal

Remediate the Aardvark-reported information disclosure issue where
`Sheet.query` accepted SELECT statements that could call DuckDB external
file-reading functions (`read_text`, `read_csv_auto`, `read_json`, `glob`,
etc.) and return local files readable by the Folio process.

## Scope

- `src/folio/_query.py`: keep DuckDB for analytical SELECTs, but load
  `records.jsonl` through Python into a temporary `records` table and open
  DuckDB with `enable_external_access=false` before executing caller SQL.
- `tests/test_sheet.py`: add a regression test proving `read_text` cannot
  exfiltrate a file outside the sheet while normal queries still pass.
- Design/spec docs: update the query contract to say SELECT-only is not
  enough; caller SQL must also be filesystem-sandboxed.
- Quality and progress docs: record the security posture change and the
  permanent check.

## Out of Scope

- Replacing DuckDB with a custom SQL engine.
- Introducing a full SQL parser that enumerates every table reference.
- Changing `upsert_records`, `delete_records`, materialization provenance,
  or Viewer behavior.

## Evidence

- `uv run pytest tests/test_sheet.py -q` passes with the new regression
  coverage.
- `make verify` passes across the full harness, pytest, smokes, docs gates,
  and spec verification.

## Observation

Aardvark found that the Phase 0 query guard only rejected leading write
keywords. A leading `SELECT` could still invoke DuckDB file-reading table
functions and disclose files outside the sheet. That violates Folio's
operation contract: `query` is an analytical read over `records.jsonl`, not
a general local-filesystem read primitive.

## Decision

Keep the existing public SQL surface and write-keyword rejection, but remove
DuckDB's ability to touch the filesystem during caller SQL execution. The
reference implementation now reads `records.jsonl` through the existing
Python JSONL helper, creates a typed temporary `records` table, inserts each
record via bound parameters, and connects DuckDB with
`enable_external_access=false`.

## Permanent Fix

`tests/test_sheet.py::test_query_cannot_read_files_outside_sheet` creates a
secret file outside the sheet and asserts that `SELECT content FROM
read_text(...)` raises a `QueryError` containing DuckDB's external-access
rejection. The ordinary query/list/get tests continue to exercise the
in-memory `records` table path.

## Next Check

If future query work adds DuckDB extensions, path scans, attachments, or
alternate ingestion paths, preserve the invariant that caller-supplied SQL
cannot access files or networks other than Folio's preloaded `records`
relation, and add a focused regression test for the new surface.
