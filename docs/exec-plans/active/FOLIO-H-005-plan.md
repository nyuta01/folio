# FOLIO-H-005 Plan: ADR Coverage for Phase 0 Design Choices

## Goal

Anchor the Phase 0 design choices already encoded in the SDK and CLI as
accepted ADRs so future agents cannot silently re-debate them, and so each
binding decision has a confirmation path mapped to `make verify`.

## Scope

Add seven ADRs under `docs/design-docs/adrs/`:

- `0002-use-python-as-the-reference-implementation.md`
- `0003-use-odcs-subset-for-contract-yaml.md`
- `0004-store-records-as-line-delimited-json.md`
- `0005-use-duckdb-select-only-for-queries.md`
- `0006-use-single-writer-dot-lock-for-sheet-writes.md`
- `0007-match-x-editable-by-with-fnmatch-patterns.md`
- `0008-place-caches-and-runtime-outside-the-sheet.md`

Each ADR follows the template (Context, Decision, Consequences,
Confirmation, Alternatives) and has Status `accepted`. Update
`docs/design-docs/adrs/README.md` to list every record in numerical order.

## Out of scope

- Adding a semantic ADR-to-code drift check (e.g., asserting that
  `duckdb` and `filelock` are still referenced in `src/folio/`). That
  belongs to a follow-up enhancement to `harness_drift.py`.
- ADR coverage for Phase 1+ derivations, provenance, cache key, MCP
  server, and Viewer. Those land alongside the matching product code.

## Evidence

- `make validate-docs` passes with the seven new ADRs in sequential order.
- `make verify` passes.

## Observation

`FOLIO-H-002` through `FOLIO-H-004` encoded several decisions in code
without ADR anchors: Pydantic v2 + ODCS subset, JSONL records, DuckDB
SELECT-only queries, filelock-based `.lock`, fnmatch `x-editable-by`
matching, and the placement of caches and the project virtual
environment outside any sample sheet. ADR-0001 covers only the docs
hierarchy, so a future agent could legitimately reopen any of these.

## Decision

Convert each implemented Phase 0 design choice into a single-decision ADR
with a confirmation path tied to `make verify`. Where the decision came
straight from the design overview, the ADR cites the relevant section
rather than re-deriving the rationale.

## Permanent Fix

- Seven new ADRs make the Phase 0 design surface explicit and
  individually addressable. `scripts/validate_docs.py` already enforces
  sequential numbering, indexed entries, required sections, and a
  confirmation path for accepted ADRs, so future drops of a decision fail
  the gate.
- Each ADR's confirmation explicitly names a deterministic check that
  is part of `make verify` (`python-test`, `cli-smoke`, `validate-docs`,
  or the harness-required-files list).

## Next Check

A follow-up enhancement to `scripts/harness_drift.py` should assert that
the dependency choices named in ADRs 0005 and 0006 (`duckdb` and
`filelock`) remain in `src/folio/`, and that the cache placement decision
in ADR-0008 stays out of any sample sheet under `tests/`. That sits under
`FOLIO-H-006` (Maintain self-PDCA loop and quality feedback artifacts) as
the natural place to grow semantic drift coverage.
