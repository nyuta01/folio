# Agent Progress

Last updated: 2026-05-10

## Current State

- Repository contains the Folio product design document, the lightweight
  AI-first harness baseline, and the first product code.
- Canonical design lives at `docs/design-docs/overview.md`; root
  `design-doc.md` is only a compatibility pointer.
- ADRs 0001 through 0008 are accepted and indexed under
  `docs/design-docs/adrs/`. They cover the docs hierarchy (0001), the
  Python reference implementation (0002), the ODCS subset for
  `contract.yaml` (0003), JSONL records (0004), DuckDB SELECT-only
  queries (0005), the single-writer `.lock` (0006), fnmatch-based
  `x-editable-by` matching (0007), and the rule that caches and the
  runtime live outside the sheet (0008).
- `folio` Python package is scaffolded under `src/folio/`. `load_contract`
  validates `contract.yaml` against the Phase 0 invariants in §6 of the
  design overview (1 sheet = 1 model, single primary key, ODCS subset of
  `logicalType`, derived inputs reachable, no extra property attributes).
- `folio.open_sheet(path, actor=None)` exposes the six Phase 0 operations
  on a `Sheet` object: `get_contract`, `query` (DuckDB SELECT-only),
  `list_records` (with pagination + field projection), `get_record`,
  `upsert_records`, and `delete_records`. Writes acquire `.lock` with a
  30-second timeout via `filelock` and use atomic temp file + rename
  writes; `editable_by` patterns are matched with `fnmatch`.
- `folio` CLI is wired as a Typer app at `src/folio/cli.py` and registered
  as a project script (`folio = folio.cli:main`). It exposes `validate`,
  `query`, `list`, `count`, `upsert`, and `delete` over the SDK, defaults
  to JSON output, and converts every `FolioError` into a non-zero exit
  with a clean stderr message.
- Phase 1 parsing surface lives at `src/folio/derivation.py`:
  Pydantic v2 `AIDerivation` / `ImportDerivation` models with a `kind`
  discriminator, `MaterializationConfig` defaults, prompt vs
  prompt_ref XOR, output / output_schema correspondence enforcement,
  value_field vs value_fields XOR, and `load_derivation` /
  `load_derivations` / `detect_cycles` / `topological_sort`.
  `src/folio/_import_kind.py` loads CSV / JSONL / JSON sources from
  inside the sheet directory and applies single- or multi-value
  mappings per record.
- `src/folio/_cache.py` computes the RFC 8785 `input_hash` (`sha256:`
  prefix), exposes `sha256_hex` / `sha256_file`, and persists cache
  entries under the platformdirs-resolved
  `<user-cache>/folio/<sheet-id>/cache/` with a two-character shard
  prefix.
- `src/folio/_provenance.py` provides append-only `provenance.jsonl`
  helpers (`append_provenance`, `read_provenance`,
  `latest_provenance`, `field_history`, `is_stale`) per §9 of the
  design overview.
- `make verify` runs harness shape (`harness-check`), drift detection
  (`drift-check`), docs validation (`validate-docs`), 127 pytest cases
  (`python-test`) including atomic-write rollback, concurrent-writer
  serialization, and the Phase 1 derivation / import-kind / cache /
  provenance suites, plus a deterministic CLI smoke (`cli-smoke`)
  that walks the §23.3 scenario from the design overview.
- GitHub Actions installs dependencies via `uv sync --frozen` and runs the
  same `make verify` gate on pull requests and pushes to `main`.

## Next Action

Phase 1 is partially landed (`FOLIO-H-009` done). Continue in
dependency order:

- `FOLIO-H-010`: `input_hash` (RFC 8785 via the `rfc8785` package),
  the cache root at `<user-cache>/folio/<sheet-id>/cache/`, and the
  `provenance.jsonl` append + latest-wins read + history helpers.
- `FOLIO-H-011`: `ai` kind via the `anthropic` SDK with a
  deterministic stub mode (so `make verify` stays offline) and
  `cost_usd` capture.
- `FOLIO-H-012`: CLI verbs (`materialize`, `status`, `provenance`)
  on top of the SDK, plus a deterministic
  `scripts/smoke-materialize.sh` walking the §23.3 scenario through
  the stub.

`FOLIO-H-006` and `FOLIO-H-007` remain standing tasks and should be
acted on the moment a concrete drift signal appears.

## Open Notes

- Phase-specific smokes (CLI smoke, MCP smoke, Viewer smoke) should land
  alongside the product code that needs them, not before.
- Add or update an ADR when future changes alter architecture, persistence,
  protocol, security posture, or harness policy.
- A sheet must remain `tar`-portable: caches, venvs, and audit logs live
  outside the sheet directory. The repo-level `.venv` managed by `uv` is
  outside any sample sheet and is fine.
- Use `FOLIO-H-001` as the harness baseline anchor in `feature-list.json`,
  and `FOLIO-H-002` as the Phase 0 SDK scaffold anchor.
