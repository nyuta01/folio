# ADR-0005 Use DuckDB SELECT-Only for Queries

- **Status**: `accepted`
- **Date**: `2026-05-10`
- **Decision makers**: `agent`
- **Related**: `docs/design-docs/overview.md` §10.3, §10.4

## Context

The design overview §10.3 keeps the operation count small by routing all
aggregation, distribution, and ad-hoc analytical queries through a single
`query(sql, params)` verb against a DuckDB relation named `records`. §10.4
also lets `list_records` pass a DuckDB WHERE-clause string as `filter`.

That choice has two consequences worth pinning as an ADR: writes must
**not** flow through `query` (otherwise the operation contract gets
muddy), and the runtime cannot quietly swap DuckDB for a different
engine without rewriting the SQL surface that users depend on.

## Decision

`Sheet.query` opens a short-lived in-memory DuckDB connection per call,
constructs a typed temporary `records` table from the contract and
`records.jsonl`, executes the user's SQL, and returns rows as `list[dict]`.
Folio loads the JSONL file through Python before caller SQL runs so DuckDB
external file access can remain disabled for untrusted statements.

The query layer is read-only by construction:

- `query` rejects any leading keyword from
  `INSERT / UPDATE / DELETE / CREATE / DROP / ALTER / REPLACE / TRUNCATE
  / COPY / MERGE / ATTACH / DETACH / INSTALL / LOAD / PRAGMA / CALL /
  GRANT / REVOKE` after stripping line and block comments.
- Only `SELECT`, `WITH`, `TABLE`, `VALUES`, `FROM`, `DESCRIBE`, `EXPLAIN`,
  and `SHOW` lead-keywords are accepted.
- Writes must go through `upsert_records` and `delete_records`.
- DuckDB external access is disabled for caller SQL; file-reading table
  functions and path scans such as `read_text`, `read_csv_auto`,
  `read_json`, and `glob` cannot read files outside the sheet's in-memory
  `records` relation.

Filter strings supplied to `list_records` are concatenated as DuckDB
WHERE clauses; user-provided values pass through `params` as `?`
placeholders to prevent SQL injection (per §10.4).

## Consequences

- The operation count stays at the nine listed in §10.2, with no
  parallel `count_records` / `stats` / `distinct_values` / `group_by`
  verbs.
- Users get DuckDB's in-memory analytical surface (window functions,
  aggregations, regex, JSON path) without Folio-specific glue, but not
  DuckDB functions that require filesystem or network access.
- The DuckDB version is part of the compatibility surface. A breaking
  change in DuckDB SQL parsing would force a Folio bump too.
- A second-language implementation must either embed DuckDB or
  implement a DuckDB-compatible SQL layer for `query` and `filter`.

## Confirmation

`tests/test_sheet.py` parametrizes seven write-keyword rejections
(`INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, `ALTER`, `COPY`),
exercises comment-stripping before the keyword check, and asserts that
parameterized filters return the expected rows, and asserts that
`read_text(<outside file>)` fails with DuckDB external file access disabled.
`tests/test_cli.py` exercises the same rejection through the CLI, and
`scripts/smoke-cli.sh` asserts that `folio query <sheet> "DELETE FROM
records"` exits non-zero.

## Alternatives Considered

- Build a custom AST or filter DSL. Loses DuckDB's analytic surface and
  forces Folio to maintain its own parser. Rejected.
- Allow DuckDB writes through `query`. Simpler API, but breaks the
  invariant that all writes acquire `.lock` and produce auditable
  provenance. Rejected.
- Embed SQLite instead of DuckDB. Smaller dependency, but weaker analytic
  feature set and no native JSONL ingestion. Rejected.
