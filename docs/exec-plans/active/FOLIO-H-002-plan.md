# FOLIO-H-002 Plan: Scaffold Python Package and Phase 0 Contract Validation

## Goal

Add the smallest folio Python package that loads and validates `contract.yaml`
via Pydantic v2, with deterministic `python-test` coverage behind
`make verify`.

## Scope

- `pyproject.toml` with hatchling build backend, Pydantic v2 + PyYAML
  runtime dependencies, and a `dev` dependency group containing pytest.
- `src/folio/` package:
  - `__init__.py` re-exports `Contract`, `Schema`, `Property`, `LogicalType`,
    `load_contract`, `FolioError`, and `ContractError`.
  - `contract.py` Pydantic v2 models that mirror §6 of the design overview
    (1 sheet = 1 model, single primary key, ODCS subset of `logicalType`,
    `x-derived` / `x-inputs` / `x-editable-by` extension attributes).
  - `exceptions.py` error hierarchy (`FolioError`, `ContractError`).
- `tests/test_contract.py` covering: minimal valid contract, missing file,
  invalid YAML, multiple schema models, multiple primary keys, invalid
  `logicalType`, derived field with valid `x-inputs`, derived field with
  unknown input, and duplicate property names.
- Makefile `python-test` target that runs `uv run pytest tests` and is
  included in `make verify`.
- `scripts/harness_check.py` requires the new package, tests, and Makefile
  gate so the harness rejects regressions to the Phase 0 surface.
- `.github/workflows/verify.yml` installs uv and primes the project virtual
  environment before running `make verify`.

## Out of scope

- Records.jsonl validation against the contract schema. Phase 0 records
  reading and write semantics land with `FOLIO-H-003`.
- The `folio` CLI binary. `FOLIO-H-004` adds the Typer wrapper and CLI
  smoke.
- ADR coverage for Pydantic v2, ODCS subset, JSONL, DuckDB, and RFC 8785.
  Tracked separately under `FOLIO-H-005`.

## Evidence

- `make verify` passes locally with the new `python-test` gate.
- `uv run pytest tests` reports the contract test suite as green.

## Observation

After the harness baseline (`FOLIO-H-001`) was installed, the repository had
no product code. The Phase 0 product spec at
`docs/product-specs/phase-0-minimum-sheet.md` defines `contract.yaml`
validation as the first executable slice and constrains the implementation
to Pydantic v2 + DuckDB + JSONL.

## Decision

- Build the Python package under `src/folio/` (PEP 621 + hatchling) so the
  package layout matches the published `folio` distribution.
- Use Pydantic v2 (`model_validator`) for cross-property invariants
  (single primary key, unique property names, derived inputs reachable),
  keeping the class-level shape close to the YAML.
- Drive dependency management with `uv` because it is already available on
  the developer machine and the user-cache pattern fits Folio's portability
  posture (no environment-dependent state inside a sheet).
- Wire the gate as `make python-test` so future phases can extend it without
  changing the verify entrypoint.
- Add CI uv setup so `make verify` in GitHub Actions runs the same gate as
  developers run locally.

## Permanent Fix

- `scripts/harness_check.py` now requires `pyproject.toml`,
  `src/folio/__init__.py`, `src/folio/contract.py`, `src/folio/exceptions.py`,
  `tests/__init__.py`, `tests/test_contract.py`, and that `make verify`
  includes `python-test`. A regression that removes the package or test
  surface fails the harness gate.
- `make verify` now runs `python-test`. Contract validation behavior is
  protected by deterministic pytest cases, not by code review alone.
- `.github/workflows/verify.yml` installs uv and primes `.venv` before
  running `make verify`, so the gate is reproducible across local and CI.

## Next Check

`FOLIO-H-003` should add DuckDB-backed read operations (`get_contract`,
`query`, `list_records`, `get_record`) and write operations
(`upsert_records`, `delete_records`) with `.lock` acquisition, atomic temp
file + rename writes, and `editable_by` enforcement. The python-test gate
must grow alongside it.
