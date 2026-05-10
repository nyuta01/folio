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
| Harness PDCA | 3 | `make verify` runs `harness-check`, `drift-check`, and `validate-docs`; GitHub Actions runs the same gate on pull requests and pushes to `main` | No product code, no smoke tests, no semantic drift checks beyond docs structure yet | `FOLIO-H-002` |
| Sheet Spec | 3 | Design overview defines `contract.yaml`, `records.jsonl`, derivations, provenance, cache-key, and operations end-to-end with ODCS subset alignment | Spec has no machine-checked sample sheet under `make verify` yet | `FOLIO-H-002` |
| Phase 0 SDK | 1 | Phase 0 spec exists at `docs/product-specs/phase-0-minimum-sheet.md` | No Python package, no Pydantic v2 contract validation, no DuckDB-backed read operations yet | `FOLIO-H-002` |
| Phase 0 CLI | 1 | Phase 0 spec lists the required CLI verbs | No `folio` CLI binary, no Typer wiring, no CLI smoke yet | `FOLIO-H-004` |
| Design Docs & ADRs | 4 | Canonical design docs live under `docs/design-docs/`, ADRs are indexed and templated, and `make verify` includes `validate-docs` for structure, reachability, and confirmation sections | ADR coverage is minimal (one record); semantic design-to-code drift checks will be needed once code lands | `FOLIO-H-005` |

## Current Assessment

The repository has only the design document and the AI-first harness baseline.
`make verify` validates harness shape, structured task state, active plan PDCA
sections, failure-log status, and design-doc/ADR structure. GitHub Actions runs
the same gate. No product code exists yet, so Phase 0 SDK and CLI scores are
expected to climb as `FOLIO-H-002` through `FOLIO-H-004` land.

## Review Cadence

Update this document after every completed P0/P1 task and whenever an agent
failure produces a permanent fix.
