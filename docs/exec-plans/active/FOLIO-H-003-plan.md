# FOLIO-H-003 Plan: Phase 0 Core Operations

## Goal

Implement the six Phase 0 SDK operations (`get_contract`, `query`,
`list_records`, `get_record`, `upsert_records`, `delete_records`) on a
`Sheet` object that operates a single sheet directory, with DuckDB-backed
reads, atomic writes, `.lock` acquisition, and `editable_by` enforcement.

## Scope

- `src/folio/sheet.py`: `Sheet` class plus `open_sheet(path, actor=None)`
  factory. The class owns the contract, the records.jsonl path, and the
  lock helper.
- `src/folio/_records.py`: read/write JSONL with empty-file handling and
  atomic temp file + rename writes.
- `src/folio/_lock.py`: 30-second-timeout context manager around `.lock`
  using `filelock`.
- `src/folio/_query.py`: DuckDB query helper that builds an in-memory view
  over `records.jsonl` and rejects non-SELECT statements.
- Operations:
  - `get_contract()` returns the `Contract`.
  - `query(sql, params=None)` rejects INSERT/UPDATE/DELETE/CREATE/DROP and
    similar; passes `?` parameters through to DuckDB.
  - `list_records(filter=None, fields=None, limit=50, cursor=None,
    params=None)` returns `{records, format, limit, next_cursor}` with
    `format == "json"`.
  - `get_record(id, fields=None)` returns a single dict or `None`.
  - `upsert_records(records, actor=None)` requires actor (instance or
    argument), enforces primaryKey + required + `editable_by`, merges by
    primary key, atomic write.
  - `delete_records(ids, actor=None)` requires actor, atomic write.
- New runtime dependencies: `duckdb`, `filelock`.
- Tests under `tests/test_sheet.py` covering empty/populated read, query
  rejection, parameter binding, pagination, get/missing, insert/update,
  required/primary-key enforcement, `editable_by` allow/deny, atomic-write
  rollback, and lock-based serialization across two threads.
- `scripts/harness_check.py` requires the new modules and tests.

## Out of scope

- The `folio` CLI binary. `FOLIO-H-004` adds the Typer wrapper and CLI
  smoke.
- TOON output, derivations, materialization, provenance, and the cache
  layer. Phase 1+.
- ADR coverage for the design choices (Pydantic v2, ODCS subset, JSONL,
  DuckDB, RFC 8785, cache placement). `FOLIO-H-005`.

## Evidence

- `make verify` passes locally with the expanded `python-test` gate.
- `uv run pytest tests` reports the contract and sheet test suites green.

## Observation

The harness baseline and Phase 0 contract scaffold (`FOLIO-H-002`) provide
typed access to `contract.yaml` but no data layer. Phase 0 is meaningless
without read and write operations against `records.jsonl`, since the CLI in
`FOLIO-H-004` is supposed to be a thin wrapper over the same SDK.

## Decision

- Build a single `Sheet` class as the SDK's main verb surface, with
  module-private helpers under `src/folio/_*`. The leading underscore makes
  the public API explicit.
- Use DuckDB only for reads (`query` and the `list_records` SQL builder),
  matching §10.3 of the design overview. Writes stay in pure Python over
  the JSONL list to keep atomicity simple.
- Use `filelock` for `.lock` (named in the design overview library
  selection).
- Enforce `editable_by` only when the contract declares it (Phase 0 spec),
  with a small fnmatch-based pattern matcher (`agent:*`, `human:*`,
  literals, plain `*`).
- Reject `INSERT`/`UPDATE`/`DELETE`/`CREATE`/`DROP`/`ALTER`/`COPY` in
  `query` by inspecting the leading SQL keyword after stripping comments.
  Writes flow through `upsert_records` and `delete_records`.

## Permanent Fix

- `make verify` runs `python-test`, which now exercises every Phase 0 SDK
  operation including failure paths.
- `scripts/harness_check.py` requires `src/folio/sheet.py`,
  `src/folio/_records.py`, `src/folio/_lock.py`, `src/folio/_query.py`, and
  `tests/test_sheet.py` so deletion of the data layer fails the harness
  gate.
- The lock test serializes two threads and asserts both writes land,
  guarding the single-writer invariant in §12 of the design overview.
- The atomic-write test forces `os.replace` to fail and asserts that the
  original `records.jsonl` is untouched and no `*.tmp` leftover remains,
  guarding the temp file + rename invariant.

## Next Check

`FOLIO-H-004` will add the `folio` CLI MVP (Typer) on top of the Sheet
operations and a deterministic `scripts/smoke-cli.sh` behind `make verify`.
`FOLIO-H-005` will then turn the Phase 0 design choices already encoded in
the SDK into accepted ADRs so future agents do not re-debate them.
