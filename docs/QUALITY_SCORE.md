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
| Sheet Spec | 4 | Design overview defines `contract.yaml`, `records.jsonl`, derivations, provenance, cache-key, and operations end-to-end with ODCS subset alignment; pytest exercises Phase 0 read/write semantics and Phase 1 derivation parsing + import-kind execution | Provenance, cache layer, and ai kind are still spec-only | `FOLIO-H-010` |
| Phase 0 SDK | 4 | `folio.open_sheet` exposes `get_contract`, `query` (DuckDB SELECT-only), `list_records` with pagination, `get_record`, `upsert_records`, and `delete_records` with `.lock` (30s timeout via filelock), atomic temp+rename writes, primaryKey/required validation, and fnmatch-based `editable_by` enforcement; pytest covers 35 cases including atomic-write rollback and concurrent-writer serialization | No CLI surface or smoke yet | `FOLIO-H-004` |
| Phase 0 CLI | 4 | `folio` CLI exposes `validate`, `query`, `list`, `count`, `upsert`, and `delete` via Typer; registered as a project script through `pyproject.toml`; covered by 16 `CliRunner` cases plus `scripts/smoke-cli.sh` that runs the §23.3 scenario end-to-end behind `make verify` | TOON output, `--format` switching, and the `materialize`/`status`/`provenance`/`serve` verbs are not implemented yet (Phase 1+) | `FOLIO-H-005` |
| Design Docs & ADRs | 5 | Canonical design docs live under `docs/design-docs/`; eight indexed ADRs cover the docs hierarchy plus every Phase 0 design choice encoded in code (Python reference implementation, ODCS subset, JSONL records, DuckDB SELECT-only queries, single-writer `.lock`, fnmatch `x-editable-by`, cache/runtime placement); `make validate-docs` enforces sequential numbering, indexing, required sections, and a confirmation path for accepted ADRs | Semantic ADR-to-code drift checks (e.g., asserting `duckdb` and `filelock` remain in `src/folio/`) are not enforced yet | `FOLIO-H-006` |

## Current Assessment

Phase 0 is feature-complete and ADR-anchored. Phase 1 has begun: the
parsing surface (`folio.derivation`) loads `derivations/<field>.yaml`
into discriminated `AIDerivation` / `ImportDerivation` models with
field-level cycle detection and topological sort, and
`folio._import_kind` executes CSV / JSONL / JSON imports against
records under the sheet directory. `make verify` now runs 98 pytest
cases plus the CLI smoke. The cache layer, provenance log, and ai
kind driver remain ahead under `FOLIO-H-010` and `FOLIO-H-011`; the
CLI verbs that surface them land with `FOLIO-H-012`.

## Review Cadence

Update this document after every completed P0/P1 task and whenever an agent
failure produces a permanent fix.
