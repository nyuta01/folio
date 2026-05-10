# Agent Progress

Last updated: 2026-05-10

## Current State

- Repository contains the Folio product design document and the lightweight
  AI-first harness baseline.
- Canonical design lives at `docs/design-docs/overview.md`; root
  `design-doc.md` is only a compatibility pointer.
- ADR-0001 records the design-doc and ADR location convention.
- `make verify` runs harness shape (`harness-check`), drift detection
  (`drift-check`), and docs validation (`validate-docs`).
- GitHub Actions runs the same `make verify` gate on pull requests and pushes
  to `main`.
- No product code exists yet. Phase 0 (`contract.yaml + records.jsonl + core
  operations + CLI`) is the next executable slice.

## Next Action

Start one P0 backlog task in dependency order:

- `FOLIO-H-002`: Scaffold the Python package (`folio/`) and add Pydantic v2
  contract.yaml validation behind `make verify`.
- `FOLIO-H-003`: Implement Phase 0 core operations against `records.jsonl`
  using DuckDB (`get_contract`, `query`, `list_records`, `get_record`,
  `upsert_records`, `delete_records`).
- `FOLIO-H-004`: Add the `folio` CLI MVP (`validate`, `query`, `list`,
  `count`, `upsert`, `delete`) on top of the SDK with a deterministic CLI
  smoke.

## Open Notes

- Keep the initial harness intentionally small. Phase-specific smokes (Python
  unit tests, CLI smoke, MCP smoke, Viewer smoke) should land alongside the
  product code that needs them, not before.
- Add or update an ADR when future changes alter architecture, persistence,
  protocol, security posture, or harness policy.
- A sheet must remain `tar`-portable: caches, venvs, and audit logs live
  outside the sheet directory.
- Use `FOLIO-H-001` as the harness baseline anchor in `feature-list.json`.
