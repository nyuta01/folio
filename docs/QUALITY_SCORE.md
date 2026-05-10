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
| Sheet Spec | 5 | Design overview defines `contract.yaml`, `records.jsonl`, derivations, provenance, cache-key, and operations end-to-end with ODCS subset alignment; `make verify` exercises every Phase 0 and Phase 1 spec surface (parsing, querying, write semantics, derivations, materialize loop, cache, provenance, CLI verbs) through 156 pytest cases plus the CLI smoke and the materialize smoke | Phase 2+ surfaces (scripts/, MCP, TOON, Viewer) are spec-only | `FOLIO-H-006` |
| Phase 0 SDK | 4 | `folio.open_sheet` exposes `get_contract`, `query` (DuckDB SELECT-only), `list_records` with pagination, `get_record`, `upsert_records`, and `delete_records` with `.lock` (30s timeout via filelock), atomic temp+rename writes, primaryKey/required validation, and fnmatch-based `editable_by` enforcement; pytest covers 35 cases including atomic-write rollback and concurrent-writer serialization | No CLI surface or smoke yet | `FOLIO-H-004` |
| Phase 0 CLI | 4 | `folio` CLI exposes `validate`, `query`, `list`, `count`, `upsert`, and `delete` via Typer; registered as a project script through `pyproject.toml`; covered by 16 `CliRunner` cases plus `scripts/smoke-cli.sh` that runs the §23.3 scenario end-to-end behind `make verify` | TOON output, `--format` switching, and the `materialize`/`status`/`provenance`/`serve` verbs are not implemented yet (Phase 1+) | `FOLIO-H-005` |
| Design Docs & ADRs | 5 | Canonical design docs live under `docs/design-docs/`; nine indexed ADRs cover the docs hierarchy, every Phase 0 design choice encoded in code, and the Phase 1 AI client Protocol + deterministic stub (ADR-0009); `make validate-docs` enforces sequential numbering, indexing, required sections, and a confirmation path for accepted ADRs | Semantic ADR-to-code drift checks (e.g., asserting `anthropic` is only imported in `AnthropicClientAdapter`) are not enforced yet | `FOLIO-H-006` |

## Current Assessment

Phases 0 / 1 / 2 / 3 / 4 are all feature-complete and ADR-anchored.
The repository now ships:

- The Phase 0 SDK + CLI (contract, query, list, get, upsert, delete).
- The Phase 1 materialize loop with cache + provenance + ai/import
  kinds (offline-capable through `StubAIClient`).
- Phase 2 reusable scripts (`Sheet.run_script` + `folio script
  run`) and a typed README frontmatter (`Sheet.metadata`).
- Phase 3 MCP server (`folio-mcp` exposing nine tools through
  FastMCP, offline-tested via the in-process Client harness) and a
  thin TOON encoder for `list_records`.
- Phase 4 extension kinds (`sql`, `http`, `python`, `cross_sheet`)
  and Frictionless `datapackage.json` export.

Drift-check enforces four ADR invariants mechanically: anthropic
import location (ADR-0009), duckdb / filelock retention
(ADR-0005 / ADR-0006), and fixture sheets free of cache / runtime
/ venv state (ADR-0008). `make verify` runs 259 pytest cases plus
five offline smokes (`cli`, `materialize`, `scripts`, `mcp`,
`extension-kinds`). The only remaining product backlog is
Phase 5 (Viewer V0–V6) under `FOLIO-H-024` and `FOLIO-H-025`.

## Review Cadence

Update this document after every completed P0/P1 task and whenever an agent
failure produces a permanent fix.
