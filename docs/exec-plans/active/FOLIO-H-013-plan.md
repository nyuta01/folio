# FOLIO-H-013 Plan: Phase 2 Product Spec and Backlog

## Goal

Record the executable shape of Phase 2 (reusable `scripts/` runtime
plus `README.md` AI-frontmatter) and break the work into bounded
backlog tasks.

## Scope

- New product spec at
  `docs/product-specs/phase-2-scripts-and-readme-frontmatter.md`.
- Updated `docs/product-specs/README.md` index.
- Two backlog tasks registered in
  `docs/exec-plans/feature-list.json`:
  - `FOLIO-H-014` — `scripts/` discovery, runtime under
    `<user-cache>/folio/<sheet-id>/runtime/`, `Sheet.run_script`,
    `folio script run` CLI verb, and a deterministic shell smoke.
  - `FOLIO-H-015` — `README.md` YAML frontmatter (`purpose`,
    `default_actor`, optional `tags` / `links` / `agent_skills`),
    `Sheet.metadata`, and `folio validate` enhancement.

## Out of scope

- Implementing any Phase 2 code; that is `FOLIO-H-014` and
  `FOLIO-H-015`.
- The `python` derivation kind that *calls* a function in
  `scripts/` — Phase 4 (`FOLIO-H-021`).

## Evidence

- `make verify` passes after the spec and feature-list updates.
- `make validate-docs` accepts the new local link to the Phase 2
  spec from the index.

## Observation

Phase 1 is feature-complete, and the design overview §5 plus §13.4
already commit Folio to a `scripts/` surface and a README frontmatter
that surfaces AI-oriented metadata. Without a self-contained spec,
implementation loops would have to re-derive the runtime placement
rules and the frontmatter shape from §13 of the design overview.

## Decision

Mirror the Phase 1 spec format (`phase-1-derivations-and-provenance.md`):
a single self-contained product spec plus a small set of bounded
backlog tasks. Keep the backlog narrow (two tasks) because Phase 2
itself is small relative to the Phase 1 building-block surface.

## Permanent Fix

- `make validate-docs` enforces local-link integrity, so the new
  spec being indexed from `docs/product-specs/README.md` becomes a
  structural invariant.
- `harness-drift` continues to reject active plans without PDCA
  sections and tasks without `plan_url` once `done`.

## Next Check

Begin `FOLIO-H-014` (scripts runtime) once Phase 2 work starts. Its
plan should pin the runtime cache placement against ADR-0008 (no
runtime state inside the sheet) and the path-traversal guard for
`Sheet.run_script(name, ...)`.
