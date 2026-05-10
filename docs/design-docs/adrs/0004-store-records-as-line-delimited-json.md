# ADR-0004 Store Records as Line-Delimited JSON

- **Status**: `accepted`
- **Date**: `2026-05-10`
- **Decision makers**: `agent`
- **Related**: `docs/design-docs/overview.md` §7, §14.3

## Context

A sheet's record data needs a format that is portable, diffable in Git,
inspectable by AI agents without bespoke tooling, and reachable by
existing data ecosystems (`jq`, `pandas`, DuckDB, Frictionless). The
design overview §7 already specifies JSON Lines for this purpose; §14.3
explicitly leaves columnar formats (Parquet, Iceberg, Delta) out of
scope because they conflict with directly-editable line-oriented files.

Without an ADR, implementations could legitimately reach for Parquet or
SQLite when scaling. Recording the decision keeps the portability
invariant load-bearing.

## Decision

Records live in `records.jsonl` as JSON Lines:

- One JSON object per line, with keys matching property names from the
  contract.
- An empty file (zero records) is a valid sheet.
- The file is wrapper-free (no `{"records": [...]}` outer object) so
  external tools (`jq`, DuckDB `read_json`, pandas) consume it
  natively.
- Lineage information lives in a separate file (`provenance.jsonl` from
  Phase 1) rather than embedded inside record values.

Hundreds-of-millions-record analytics workloads are out of scope. For
that scale, design overview §14.3 directs implementers to a different
sheet specification.

## Consequences

- Phase 0 reads can use DuckDB `read_json(format='newline_delimited')`
  directly without staging into a different format.
- Atomic writes are simple: serialize the in-memory list of dicts to a
  temp file and `os.replace` (§12 of the design overview).
- Diffing changes via Git is line-oriented and reviewable. Bots that
  upsert single records produce small diffs.
- Per-record overhead (key repetition) makes JSONL ~2-5x larger than a
  packed columnar format for the same data. Acceptable for Folio's
  scale ceiling (tens to hundreds of thousands of records per §2.5).
- A schema evolution that renames a property requires either a
  `migrations/` script or a coordinated rewrite of `records.jsonl`.

## Confirmation

`tests/test_sheet.py` exercises empty-file reads, empty-file inserts,
and `records_jsonl_lines_are_valid_json` which round-trips every line
through `json.loads`. `scripts/smoke-cli.sh` walks the §23.3 scenario
end-to-end (validate → upsert → query → list → delete) against a
JSONL records file under `make verify`.

## Alternatives Considered

- Parquet records. Better at scale and for analytic queries, but loses
  Git-diffability and editability through plain shell tools. Out of
  scope per design overview §14.3.
- A single sheet-level JSON document (`records.json` containing a
  list). Simpler to write, but ~equivalent to JSONL in size while
  losing line-wise streamability and tooling compatibility. Rejected.
- SQLite. Excellent for embedded relational queries, but binary,
  not Git-diffable, and reduces the spec to "a SQLite file plus
  metadata." Out of scope.
