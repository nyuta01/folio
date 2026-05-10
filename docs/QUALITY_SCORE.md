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
| Phase 0 CLI | 4 | `folio` CLI exposes `validate`, `query`, `list`, `count`, `upsert`, and `delete` via Typer; registered as a project script through `pyproject.toml`; covered by 16 `CliRunner` cases plus `scripts/smoke-cli.sh` that runs the §23.3 scenario end-to-end behind `make verify` | TOON output, `--format` switching, and the `materialize`/`status`/`provenance`/`serve` verbs are not implemented yet (Phase 1+) | `FOLIO-H-005` |
| Design Docs & ADRs | 4 | Canonical design docs live under `docs/design-docs/`, ADRs are indexed and templated, and `make verify` includes `validate-docs` for structure, reachability, and confirmation sections | ADR coverage is minimal (one record); the Phase 0 design choices encoded in code (Pydantic v2, ODCS subset, JSONL, DuckDB SELECT-only, filelock, fnmatch editable_by) are not yet ADR-anchored | `FOLIO-H-005` |

## Current Assessment

Phase 0 is now executable end-to-end: the `Sheet` SDK exposes six core
operations (`get_contract`, `query`, `list_records`, `get_record`,
`upsert_records`, `delete_records`) and the `folio` CLI exposes the same
verbs as a thin Typer wrapper. Writes go through `.lock` (30s timeout via
filelock) and an atomic temp file + rename sequence; `editable_by` is
enforced with fnmatch patterns. `make verify` runs `harness-check`,
`drift-check`, `validate-docs`, 62 pytest cases, and a deterministic
`scripts/smoke-cli.sh` that walks the §23.3 scenario (validate → count →
upsert → query → list → update → delete → write rejection). What is still
ahead: ADR coverage for the Phase 0 design choices (`FOLIO-H-005`) and
Phase 1+ derivations, provenance, and cache layers.

## Review Cadence

Update this document after every completed P0/P1 task and whenever an agent
failure produces a permanent fix.
