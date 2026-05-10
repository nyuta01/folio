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

Phase 0 and Phase 1 are both feature-complete. The `Sheet` SDK now
exposes nine operations (Phase 0 six + `materialize`,
`materialization_status`, `provenance`), and the `folio` CLI exposes
the matching verbs as a thin Typer wrapper. `Sheet.materialize`
walks derivations in topological order, processes each derivation
file once (so multi-target ai derivations cost a single API call),
honors `respect_human_override` and stale `input_hash` checks,
short-circuits via the cache, persists records.jsonl atomically and
appends provenance only after the records write succeeds, and
surfaces kind-execution failures as entries on the §10.6 envelope
rather than raising. `make verify` runs 156 pytest cases plus
`cli-smoke` and `materialize-smoke`, all of which run offline
through `StubAIClient`. What remains: Phase 2+ (scripts/, MCP,
TOON, Viewer) and the standing self-PDCA / permanent-fix tasks.

## Review Cadence

Update this document after every completed P0/P1 task and whenever an agent
failure produces a permanent fix.
