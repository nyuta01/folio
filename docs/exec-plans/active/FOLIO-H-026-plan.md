# FOLIO-H-026 Plan: Semantic ADR-to-Code Drift Checks

## Goal

Promote three ADR-driven invariants from "review by hand" to
"deterministic check inside `make verify`" so the harness rejects
silent drift away from the Phase 0 / Phase 1 design choices.

## Scope

Add to `scripts/harness_drift.py`:

- **ADR-0009 anchor**: `import anthropic` (and `from anthropic`)
  appears only in `src/folio/_ai_kind.py`. Any other module
  importing the SDK fails the gate.
- **ADR-0005 anchor**: `duckdb` is imported somewhere in
  `src/folio/`. A future refactor that drops DuckDB cannot quietly
  pass.
- **ADR-0006 anchor**: `filelock` is imported somewhere in
  `src/folio/`. Same logic for the single-writer lock.
- **ADR-0008 anchor**: no sample sheet under `tests/fixtures/`
  contains `.cache/`, `.venv/`, `.folio-cache/`, or `.folio-runtime/`
  directories. A regression that bundles environment-dependent state
  into a fixture sheet fails the gate.

## Out of scope

- A full import-graph dependency check. The four anchors above are
  the high-impact set; a generic checker would be larger and would
  need its own ADR if introduced.
- Running the checks in CI separately. They become part of
  `harness-drift`, which CI already runs.

## Evidence

- `make verify` passes locally with the four new checks active.
- Manually introducing `from anthropic import Anthropic` in
  `src/folio/sheet.py` reproduces the failure (verified during
  development).

## Observation

ADRs 0005, 0006, 0008, and 0009 each pin a binding choice (DuckDB,
filelock, cache placement, AI-client Protocol with anthropic only in
the adapter). All four were enforced only by review until now. The
standing self-PDCA backlog (`FOLIO-H-006`) has explicitly named
these as the natural next semantic-drift checks.

## Decision

Add a new function `validate_adr_anchored_invariants()` to
`scripts/harness_drift.py` that performs the four checks. Each check
emits a single failure with the relevant file path so an offending
diff lands cleanly in the `make verify` output.

The checks use small regex over file text (not a real Python AST
parser) to keep `harness_drift.py` dependency-free. This is enough
for the four invariants and matches the existing style of the
script.

## Permanent Fix

- `make verify` now fails when any of the four invariants are
  violated, so a future agent cannot land a regression silently.
- `FOLIO-H-006` (self-PDCA standing task) remains open to capture
  the next semantic invariant as it appears, but the most obvious
  drift signals are now mechanically guarded.

## Next Check

When future ADRs land (e.g., when `FOLIO-H-022` ships
`datapackage.json` generation, when `FOLIO-H-017` ships the MCP
server), extend `validate_adr_anchored_invariants` with the matching
import / placement anchors so the drift gate keeps growing alongside
the codebase.
