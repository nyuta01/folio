# Architecture Decision Records

ADR files capture one architecturally meaningful decision each. Use them when
a choice changes system boundaries, persistence, protocol behavior,
specification surface, security, operability, or the agent harness itself.

## Records

| ADR | Status | Decision |
|---|---|---|
| [0001](0001-record-design-docs-and-adrs-under-docs.md) | accepted | Record design docs and ADRs under `docs/design-docs/` |
| [0002](0002-use-python-as-the-reference-implementation.md) | accepted | Use Python as the reference implementation |
| [0003](0003-use-odcs-subset-for-contract-yaml.md) | accepted | Use the ODCS subset for `contract.yaml` |
| [0004](0004-store-records-as-line-delimited-json.md) | accepted | Store records as line-delimited JSON |
| [0005](0005-use-duckdb-select-only-for-queries.md) | accepted | Use DuckDB SELECT-only for queries |
| [0006](0006-use-single-writer-dot-lock-for-sheet-writes.md) | accepted | Use a single-writer `.lock` for sheet writes |
| [0007](0007-match-x-editable-by-with-fnmatch-patterns.md) | accepted | Match `x-editable-by` with fnmatch patterns |
| [0008](0008-place-caches-and-runtime-outside-the-sheet.md) | accepted | Place caches and runtime outside the sheet |

## Status Values

- `proposed`: under discussion and not yet binding.
- `accepted`: binding for new work until superseded.
- `rejected`: considered and intentionally not chosen.
- `deprecated`: no longer recommended, but no single replacement ADR exists.
- `superseded`: replaced by a later ADR that must be linked.

## New ADR Checklist

1. Copy [template.md](template.md).
2. Name the file `NNNN-kebab-title.md` with the next sequence number.
3. Add it to the Records table.
4. Fill every required section.
5. Include a confirmation path for accepted decisions.
6. Run `make validate-docs`.
