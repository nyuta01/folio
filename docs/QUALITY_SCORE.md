# Quality Score

Last updated: 2026-05-10

Scores use a 1-5 scale:

- 1: missing or unsafe
- 2: scaffolded but not yet reliable
- 3: usable with known gaps
- 4: solid and routinely verified
- 5: excellent, mechanically enforced, and resilient to agent drift

| Domain | Score | Evidence | Weak Spot | Next Task |
|---|---:|---|---|---|
| Harness PDCA | 4 | `make verify` runs `harness-check`, `drift-check`, `validate-docs`, and `python-test` (46 cases); GitHub Actions runs the same gate on pull requests and pushes to `main` after `uv sync --frozen` | Semantic design drift checks beyond docs structure are still shallow | `FOLIO-H-006` |
| Sheet Spec | 4 | Design overview defines `contract.yaml`, `records.jsonl`, derivations, provenance, cache-key, and operations end-to-end with ODCS subset alignment; pytest exercises Phase 0 read/write semantics | Derivations, provenance, and cache layer are still spec-only | `FOLIO-H-005` |
| Phase 0 SDK | 4 | `folio.open_sheet` exposes `get_contract`, `query` (DuckDB SELECT-only), `list_records` with pagination, `get_record`, `upsert_records`, and `delete_records` with `.lock` (30s timeout via filelock), atomic temp+rename writes, primaryKey/required validation, and fnmatch-based `editable_by` enforcement; pytest covers 35 cases including atomic-write rollback and concurrent-writer serialization | No CLI surface or smoke yet | `FOLIO-H-004` |
| Phase 0 CLI | 1 | Phase 0 spec lists the required CLI verbs | No `folio` CLI binary, no Typer wiring, no CLI smoke yet | `FOLIO-H-004` |
| Design Docs & ADRs | 4 | Canonical design docs live under `docs/design-docs/`, ADRs are indexed and templated, and `make verify` includes `validate-docs` for structure, reachability, and confirmation sections | ADR coverage is minimal (one record); the Phase 0 design choices encoded in code (Pydantic v2, ODCS subset, JSONL, DuckDB SELECT-only, filelock, fnmatch editable_by) are not yet ADR-anchored | `FOLIO-H-005` |

## Current Assessment

The Phase 0 SDK now exposes the six core operations on a `Sheet` object:
`get_contract`, `query` (DuckDB SELECT-only), `list_records`, `get_record`,
`upsert_records`, and `delete_records`. Writes go through a single-writer
`.lock` (30s timeout via filelock) and an atomic temp file + rename rename
sequence; `editable_by` patterns are matched with fnmatch. `make verify`
runs 46 pytest cases including atomic-write rollback and concurrent-writer
serialization. The CLI surface and the ADRs that anchor the Phase 0 design
choices are still ahead (`FOLIO-H-004` and `FOLIO-H-005`).

## Review Cadence

Update this document after every completed P0/P1 task and whenever an agent
failure produces a permanent fix.
