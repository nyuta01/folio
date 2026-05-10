# Agent Progress

Last updated: 2026-05-10

## Current State

- Repository contains the Folio product design document, the lightweight
  AI-first harness baseline, and the first product code.
- Canonical design lives at `docs/design-docs/overview.md`; root
  `design-doc.md` is only a compatibility pointer.
- ADRs 0001 through 0009 are accepted and indexed under
  `docs/design-docs/adrs/`. They cover the docs hierarchy (0001), the
  Python reference implementation (0002), the ODCS subset for
  `contract.yaml` (0003), JSONL records (0004), DuckDB SELECT-only
  queries (0005), the single-writer `.lock` (0006), fnmatch-based
  `x-editable-by` matching (0007), the rule that caches and the
  runtime live outside the sheet (0008), and the AI client Protocol +
  deterministic stub (0009).
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
- `src/folio/_ai_kind.py` exposes `materialize_ai(derivation, inputs,
  *, client, prompt_body=None)` over an `AIClient` Protocol.
  `AnthropicClientAdapter` is the only module that imports
  `anthropic`; tests and offline smokes use `StubAIClient`. Cost is
  computed from a small per-model `PRICE_TABLE_USD`; unknown models
  yield `cost_usd=None` rather than inventing numbers (ADR-0009).
- `Sheet.materialize`, `Sheet.materialization_status`, and
  `Sheet.provenance` are wired on top of the building blocks. The
  materialize loop iterates derivation files in topological order,
  processes every target produced by each file together (so
  multi-target ai derivations cost one API call), short-circuits via
  the cache, honors `respect_human_override` and stale `input_hash`
  checks, persists `records.jsonl` atomically, and appends
  provenance only after the records write succeeds. Failures are
  reported as `{record_id, field, error, error_type}` entries on
  the §10.6 envelope rather than raised.
- `folio` CLI now exposes `materialize`, `status`, and `provenance`
  verbs alongside the Phase 0 verbs.
- Phase 2 (`scripts/` + README frontmatter) is implemented:
  `src/folio/scripts.py` discovers and executes `*.py` / `*.sh`
  scripts (sheet path as `argv[1]`, optional venv created on first
  use under the user-cache runtime), `Sheet.run_script` and
  `folio script run / list` cover the CLI surface, and
  `src/folio/readme.py` exposes a Pydantic v2 `Frontmatter`
  (purpose / default_actor / tags / links / agent_skills) that
  `folio validate [--strict]` surfaces.
- Phase 3 (MCP + TOON) is implemented: `folio-mcp` ships as a
  sibling Python package whose FastMCP server exposes the nine SDK
  operations as MCP tools (with when-to-use docstrings, sheet-path
  resolution against `--root`, AIClient injection for materialize),
  and `src/folio/_toon.py` adds a thin TOON encoder plumbed through
  `Sheet.list_records(format="json"|"toon")` and `folio list
  --format`.
- Phase 4 (extension kinds + datapackage.json) is implemented:
  `src/folio/kinds/` houses `SQLDerivation` (DuckDB SELECT-only
  expression with parameter passthrough), `HTTPDerivation`
  (templated URL/body, response_path/response_schema dot-path,
  `HTTPTransport` Protocol with `HTTPXTransport` adapter and
  `StubHTTPTransport` for offline tests), `PythonDerivation`
  (subprocess execution via `Sheet.run_script`), and
  `CrossSheetDerivation` (sibling-sheet match by primary key,
  foreign records hash folded into `input_hash`).
  `src/folio/datapackage.py` + `folio export datapackage` map the
  contract to a Frictionless v1 descriptor.
- ADR-to-code drift checks (`scripts/harness_drift.py::
  validate_adr_anchored_invariants`) pin ADR-0005 / ADR-0006 /
  ADR-0008 / ADR-0009 against silent regressions: anthropic only
  imports in `_ai_kind.py`, duckdb / filelock must remain in
  `src/folio/`, sample fixtures cannot bundle env state.
- `make verify` runs harness shape (`harness-check`), drift
  detection (`drift-check`), docs validation (`validate-docs`),
  259 pytest cases (`python-test`) covering Phase 0 / 1 / 2 / 3 / 4,
  plus five smokes: `cli-smoke`, `materialize-smoke`,
  `scripts-smoke`, `mcp-smoke`, `extension-kinds-smoke`. All run
  offline through `StubAIClient` / `StubHTTPTransport` / mocked
  filesystems.
- GitHub Actions installs dependencies via `uv sync --frozen` and
  runs the same gate on pull requests and pushes to `main`.

## Next Action

Phase 5 (Viewer) is the only remaining product backlog:

- `FOLIO-H-024`: V0–V3. FastAPI backend, REST routes mapped to the
  SDK, React + Vite + TanStack Table / Virtual frontend, type
  chips, provenance hover, derivation badges, edit affordance for
  `x-editable-by` fields, CSRF token plumbing, and the backend
  smoke.
- `FOLIO-H-025`: V4–V6. Materialize dashboard (driven by an
  injected `StubAIClient`), history view, SSE event stream,
  Playwright frontend smoke, and the `folio serve` CLI alias.

`FOLIO-H-006` and `FOLIO-H-007` remain standing tasks; act on them
the moment a concrete drift signal or repeated failure appears.

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
