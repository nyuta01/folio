# FOLIO-H-001 Plan: Install Lightweight AI-First Harness

## Goal

Add the smallest useful harness baseline before product implementation starts.

## Scope

- Compact `AGENTS.md` routing layer.
- Restartable `AGENT_PROGRESS.md`.
- Structured task state in `docs/exec-plans/feature-list.json`.
- Self-PDCA, harness-engineering, and permanent-fix protocol docs.
- Quality-score artifact and failure log.
- Required-file, task-state, active-plan, and failure-log checks.
- Design-doc / ADR index, template, and first ADR.
- First product spec (`phase-0-minimum-sheet.md`).
- Single `make verify` entrypoint and matching CI workflow.
- Move the existing root design document to
  `docs/design-docs/overview.md` and leave a short pointer at the root.

## Evidence

- `make verify` passes.
- `make agent-init` passes.

## Observation

The repository started with only the Folio design document and no repeatable
agent workflow. There was no structured task state, no PDCA loop, no failure
log, no docs validation, and no CI gate. The single design file at the root
mixed canonical product design with what should be a short routing layer.

## Decision

Install a lightweight harness modeled on the Jinba Drive AI-first harness
rather than importing a full sandbox process. Keep the initial gate to
harness shape, drift detection, and docs validation. Defer language-specific
smokes (Python tests, CLI smoke, MCP smoke, Viewer smoke) until product code
lands so the gate stays meaningful.

Use Python 3 for harness scripts so the only required runtime is Python,
matching Folio's reference implementation language. Move the canonical design
document to `docs/design-docs/overview.md` and keep root `design-doc.md` as a
short compatibility pointer enforced by `validate_docs.py`.

## Permanent Fix

`make verify` now runs deterministic harness shape, drift, and docs
validation. `AGENTS.md` routes agents to structured task state and the design
overview instead of relying on chat history. `validate_docs.py` enforces that
the root `design-doc.md` stays a short pointer and that every ADR has the
required structure and a confirmation path. GitHub Actions runs the same
`make verify` gate.

## Next Check

The next task (`FOLIO-H-002`) should add the Python package scaffold, Pydantic
v2 contract validation, and Phase 0 read operations, and extend `make verify`
beyond harness shape into Python unit tests.

## Follow-Up

- `FOLIO-H-002`: Scaffold the Python package and Pydantic v2 contract
  validation.
- `FOLIO-H-003`: Implement Phase 0 core read/write operations against
  `records.jsonl` using DuckDB.
- `FOLIO-H-004`: Add the `folio` CLI MVP and a CLI smoke under `make verify`.
