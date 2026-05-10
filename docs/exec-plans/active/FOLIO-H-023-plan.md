# FOLIO-H-023 Plan: Phase 5 Product Spec and Backlog

## Goal

Record the executable shape of Phase 5 (the local-only Viewer) and
break the work into bounded backlog tasks aligned with the V0–V6
stages from §19.3.

## Scope

- New product spec at `docs/product-specs/phase-5-viewer.md`.
- Updated `docs/product-specs/README.md` index.
- Two backlog tasks:
  - `FOLIO-H-024` — V0–V3. FastAPI backend, REST routes, React +
    TanStack scaffold, type chips, provenance hover, derivation
    badges, edit affordance for `x-editable-by` fields, CSRF token,
    backend integration tests, and `scripts/smoke-viewer.sh`.
  - `FOLIO-H-025` — V4–V6. Materialize dashboard backed by a
    stubbed `AIClient`, history view, SSE event stream, Playwright
    frontend smoke, and the `folio serve` CLI alias for
    `folio-viewer`.

## Out of scope

- Authentication / multi-user (Phase 7).
- Tauri-based desktop bundle (Phase 7).
- Mobile-optimized layout. Phase 5 targets desktop first.
- Editing `contract.yaml` or `derivations/` from the UI (Spec
  decision; out of scope per §19.2).

## Evidence

- `make verify` passes after the spec and feature-list updates.
- `make validate-docs` accepts the new local link.

## Observation

Phase 0–4 give Folio a complete file-and-API surface. Humans still
need a visual review path that respects §19's local-only / 127.0.0.1
constraints and the `x-editable-by` field model. The Viewer is
the final Phase that makes the design overview's full shape
observable in this repository.

## Decision

Split Phase 5 along the V0–V6 boundary: V0–V3 are the read +
provenance + edit surface that humans need first, while V4–V6 add
materialize control, history, and live agent activity. Both halves
ship as their own backlog tasks so neither becomes too large.

`folio-viewer` ships as a sibling Python package (the FastAPI
backend) plus a `viewer/` Vite project under the same repository.
The existing `folio serve` CLI verb (named in design overview §17)
becomes a thin shortcut over `folio-viewer`.

## Permanent Fix

- `make validate-docs` enforces local-link integrity for the new
  spec.
- The Phase 5 spec restates the local-only / 127.0.0.1 + CSRF
  posture so future agents do not silently expose the Viewer.

## Next Check

Begin `FOLIO-H-024` (V0–V3) once Phase 5 work starts. Its plan
should pin the REST endpoint signatures, the CSRF token issuance
flow, and the frontend test harness (Playwright vs Vitest +
Testing Library).
