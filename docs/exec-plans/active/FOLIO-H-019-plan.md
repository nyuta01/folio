# FOLIO-H-019 Plan: Phase 4 Product Spec and Backlog

## Goal

Record the executable shape of Phase 4 (extension derivation kinds
plus Frictionless `datapackage.json` generation) and break the work
into bounded backlog tasks.

## Scope

- New product spec at
  `docs/product-specs/phase-4-extension-kinds-and-datapackage.md`.
- Updated `docs/product-specs/README.md` index.
- Three backlog tasks:
  - `FOLIO-H-020` — kind registry, `sql` and `http` extension
    kinds, deterministic stub HTTP transport, matching tests, and a
    new `extension-kinds-smoke.sh`.
  - `FOLIO-H-021` — `python` and `cross_sheet` extension kinds.
    `python` depends on Phase 2's `FOLIO-H-014`; `cross_sheet`
    introduces foreign-sheet stale detection.
  - `FOLIO-H-022` — `datapackage.json` generator,
    `folio export datapackage` CLI verb, and round-trip validation
    against the `frictionless` library.

## Out of scope

- Third-party plug-in entry points. The kind registry is in-process
  only for Phase 4.
- Multi-sheet workspace semantics (out-of-scope per design overview
  §14.3 and Appendix B).

## Evidence

- `make verify` passes after the spec and feature-list updates.
- `make validate-docs` accepts the new local link.

## Observation

Phase 1 ships the standard `ai` and `import` kinds; the design
overview §8.5 names `sql`, `http`, `python`, and `cross_sheet` as
representative extensions. Without a Phase 4 spec the kind plug
point would be re-litigated each time a new kind lands.

## Decision

Promote `kind` to a real registry by introducing a small in-process
`register_kind(name, model_cls, executor)` surface. The four kinds
ship as cohesive triples (Pydantic model + executor + validation
rules) so a future kind only adds a new triple, not a new branch in
`derivation.py`.

The Frictionless mapping (named in design overview §14.2) lands as
its own task because external interop has different review concerns
from execution semantics.

## Permanent Fix

- `make validate-docs` enforces local-link integrity for the new
  spec.
- The kind registry pattern keeps `derivation.py` agnostic to
  Phase 4 additions.

## Next Check

Begin `FOLIO-H-020` (sql + http) once Phase 4 work starts. Its plan
should pin the body schema for each kind, the deterministic HTTP
stub transport pattern (mirroring `StubAIClient` from ADR-0009),
and the failure-as-list invariant.
