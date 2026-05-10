# FOLIO-H-004 Plan: Folio CLI MVP

## Goal

Add the `folio` CLI binary as a thin Typer wrapper over the Phase 0 SDK,
covering the six required verbs (`validate`, `query`, `list`, `count`,
`upsert`, `delete`) with deterministic shell smoke coverage behind
`make verify`.

## Scope

- `src/folio/cli.py`: Typer app with the six commands and a top-level
  `main()` that catches `FolioError` and exits non-zero with a clean
  message.
- `pyproject.toml`:
  - add `typer` to runtime dependencies.
  - register `[project.scripts] folio = "folio.cli:main"` so `uv run folio`
    and the installed `folio` binary share one entry point.
- `tests/test_cli.py`: Typer `CliRunner`-based unit tests covering each
  verb's success path and key error paths (missing actor, invalid SQL).
- `scripts/smoke-cli.sh`: bash smoke that creates a temp sheet, runs every
  verb in sequence, and asserts the expected exit codes and output values.
- `Makefile`: add `cli-smoke` target and include it in `make verify`.
- `scripts/harness_check.py`: require `src/folio/cli.py`, the smoke script,
  the test, and the new `cli-smoke` line in the verify target.

## Out of scope

- `materialize`, `status`, `provenance`, and `serve` verbs. Those land
  with Phase 1 (`materialize`, `status`, `provenance`) and Phase 5 (`serve`).
- TOON output formatting.
- ADR coverage for the Phase 0 design choices. `FOLIO-H-005`.

## Evidence

- `make verify` passes locally with the expanded `python-test` and the new
  `cli-smoke` gates.
- `uv run folio --help` prints all six verbs.
- `scripts/smoke-cli.sh` exits 0 against a freshly built temp sheet.

## Observation

The Phase 0 SDK (`FOLIO-H-003`) exposes the operations needed for the CLI
verbs but has no shell-facing surface. The Phase 0 product spec
(`docs/product-specs/phase-0-minimum-sheet.md`) lists `validate`, `query`,
`list`, `count`, `upsert`, and `delete` as the first executable slice, and
the design overview §17 specifies a Typer-based wrapper.

## Decision

- Build the CLI on Typer because the design overview library selection
  names Typer for the CLI layer and Typer auto-derives `--help` from type
  hints, which keeps the wrapper thin.
- Wrap each command with a small `_handle_folio_errors` decorator that
  converts `FolioError` into `typer.Exit(1)` with a stderr message, so the
  CLI never prints a Python traceback on a known failure.
- Default output is JSON. `count` prints a single integer (matching the
  scenario in the design overview §23.3) so shell pipelines can `test
  "$output" = "N"`.
- Drive smoke coverage via `scripts/smoke-cli.sh` so the gate works without
  any pytest plugin and is easy to read at review time.
- Keep `make verify` as the single repository gate. The new `cli-smoke`
  target runs after `python-test`.

## Permanent Fix

- `make verify` now runs `python-test` plus `cli-smoke`. Removing the CLI,
  the smoke script, or the test fails the harness gate via the expanded
  required-files list in `scripts/harness_check.py`.
- The smoke script mirrors the §23.3 scenario from the design overview
  (validate, count, upsert, count, query, list, delete, count) so future
  changes that break shell composability fail the gate.

## Next Check

`FOLIO-H-005` should record ADRs for the Phase 0 design choices already
encoded in the SDK and CLI: Pydantic v2 contract validation, ODCS subset,
JSONL records, DuckDB SELECT-only query layer, RFC 8785 cache-key
canonicalization (deferred to Phase 1 implementation but conceptually
Phase 0), and cache/runtime placement outside the sheet.
