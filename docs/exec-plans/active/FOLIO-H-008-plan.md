# FOLIO-H-008 Plan: Phase 1 Product Spec and Backlog

## Goal

Record the executable shape of Phase 1 (derivations, materialization,
provenance, and cache) and break the work into bounded backlog tasks so
implementation loops stay one-task-at-a-time.

## Scope

- New product spec at
  `docs/product-specs/phase-1-derivations-and-provenance.md` covering:
  - `derivations/<field>.yaml` shape, including the `targets / output /
    output_schema` correspondence table from §8.2 of the design
    overview.
  - `ai` kind (Anthropic SDK, prompt templates, multi-target
    output_schema) and `import` kind (CSV / JSONL / JSON file
    sources).
  - `materialize` and `materialization_status` operation contracts.
  - `provenance.jsonl` schema and read semantics.
  - `input_hash` cache key over RFC 8785 canonical JSON, cache root
    at `<user-cache>/folio/<sheet-id>/cache/`.
  - Dependency-resolution DAG and stale detection.
  - CLI verbs (`materialize`, `status`, `provenance`) and a stubbed
    smoke for deterministic offline coverage.
  - Verification expectations (Pydantic models, mocked Anthropic
    integration, import-kind CSV fixture, deterministic CLI smoke).
- Updated `docs/product-specs/README.md` index.
- Four backlog tasks registered in
  `docs/exec-plans/feature-list.json`:
  - `FOLIO-H-009` — derivation parsing + validate-time cycle
    detection + `import` kind.
  - `FOLIO-H-010` — `input_hash` + cache layer + `provenance.jsonl`.
  - `FOLIO-H-011` — `ai` kind via the `anthropic` SDK.
  - `FOLIO-H-012` — CLI verbs + materialize smoke.

## Out of scope

- Implementing any Phase 1 code. That is the work of `FOLIO-H-009`
  through `FOLIO-H-012`.
- Phase 2 (`scripts/`, README frontmatter), Phase 3 (MCP, TOON), Phase
  4 (extension kinds, `datapackage.json`), Phase 5 (Viewer).

## Evidence

- `make verify` passes after the spec and feature-list updates.
- `make validate-docs` accepts the new local link to the Phase 1 spec
  from the index.

## Observation

Phase 0 is feature-complete and ADR-anchored
(`FOLIO-H-001` … `FOLIO-H-005`). The next executable surface — the
"AI-native" half of the project — has only the spec in
`docs/design-docs/overview.md` §8 – §11, which is too coarse to drive
a single-loop implementation. There is also no concrete spec page that
explains what Phase 1 must verify before it can ship.

## Decision

- Write a self-contained product spec for Phase 1 modeled on
  `phase-0-minimum-sheet.md`: in-scope, out-of-scope, verification
  expectations, reference scenario (§23.3 from the design overview),
  and an implementation breakdown.
- Split implementation into four loops to keep each plan small enough
  to reason about and to land behind `make verify` independently:
  parsing + import (H-009), cache + provenance (H-010), ai kind
  (H-011), CLI + smoke (H-012).
- Register the four follow-up tasks now so the backlog reflects the
  upcoming work and the harness drift check still recognizes the
  permanent-fix and self-PDCA tasks (`FOLIO-H-006`, `FOLIO-H-007`).

## Permanent Fix

- `make validate-docs` enforces local-link integrity, so the new
  Phase 1 spec being indexed from `docs/product-specs/README.md`
  becomes a structural invariant.
- `harness-drift` continues to reject active plans without PDCA
  sections and tasks without `plan_url` once `done`. The new
  `FOLIO-H-009` … `FOLIO-H-012` tasks are registered as `todo` with
  `plan_url: null`, which is permitted; they will gain plans when
  their implementation loops start.

## Next Check

Begin `FOLIO-H-009` (derivation parsing + import kind). Its plan
should record the exact set of Pydantic models, the prompt source
collision rule (`prompt` vs `prompt_ref`, exactly one), and how
import-kind fixtures live under `tests/fixtures/` without breaking
`tar`-portability for any sample sheet.
