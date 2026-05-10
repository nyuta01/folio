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
| Harness PDCA | 4 | `make verify` runs `harness-check`, `drift-check`, `validate-docs`, and `python-test`; GitHub Actions runs the same gate on pull requests and pushes to `main` after `uv sync` | Semantic design drift checks beyond docs structure are still shallow | `FOLIO-H-006` |
| Sheet Spec | 3 | Design overview defines `contract.yaml`, `records.jsonl`, derivations, provenance, cache-key, and operations end-to-end with ODCS subset alignment | Records.jsonl conformance and derivation execution are not yet covered by an executable check | `FOLIO-H-003` |
| Phase 0 SDK | 2 | `folio` Python package loads `contract.yaml` via Pydantic v2 with primary-key, duplicate-name, and derived-input invariants; `pytest` covers ten cases including invalid YAML and unknown extension attributes | Records.jsonl reading, query/list/get/upsert/delete, `.lock` semantics, and atomic writes are not implemented yet | `FOLIO-H-003` |
| Phase 0 CLI | 1 | Phase 0 spec lists the required CLI verbs | No `folio` CLI binary, no Typer wiring, no CLI smoke yet | `FOLIO-H-004` |
| Design Docs & ADRs | 4 | Canonical design docs live under `docs/design-docs/`, ADRs are indexed and templated, and `make verify` includes `validate-docs` for structure, reachability, and confirmation sections | ADR coverage is minimal (one record); semantic design-to-code drift checks will be needed as code lands | `FOLIO-H-005` |

## Current Assessment

The repository now has the AI-first harness baseline and the first product
code: a `folio` Python package whose `load_contract` validates `contract.yaml`
against the Phase 0 invariants in `docs/design-docs/overview.md` §6. `make
verify` validates harness shape, structured task state, active plan PDCA
sections, failure-log status, design-doc/ADR structure, and the Phase 0
contract test suite. GitHub Actions runs the same gate after installing
dependencies via `uv sync --frozen`. Records.jsonl reading, write
operations, and the CLI are still ahead, so Phase 0 SDK and CLI scores will
keep climbing as `FOLIO-H-003` and `FOLIO-H-004` land.

## Review Cadence

Update this document after every completed P0/P1 task and whenever an agent
failure produces a permanent fix.
