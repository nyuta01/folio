# Agent Progress

Last updated: 2026-05-10

## Current State

- Repository contains the Folio product design document, the lightweight
  AI-first harness baseline, and the first product code.
- Canonical design lives at `docs/design-docs/overview.md`; root
  `design-doc.md` is only a compatibility pointer.
- ADR-0001 records the design-doc and ADR location convention.
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
- `make verify` runs harness shape (`harness-check`), drift detection
  (`drift-check`), docs validation (`validate-docs`), 62 pytest cases
  (`python-test`) including atomic-write rollback and concurrent-writer
  serialization, and a deterministic CLI smoke (`cli-smoke`) that walks
  the §23.3 scenario from the design overview.
- GitHub Actions installs dependencies via `uv sync --frozen` and runs the
  same `make verify` gate on pull requests and pushes to `main`.

## Next Action

Start one P1 backlog task:

- `FOLIO-H-005`: Record ADRs for the Phase 0 design choices already
  encoded in the SDK and CLI (Python reference implementation, ODCS subset
  for `contract.yaml`, JSONL records, DuckDB SELECT-only query layer,
  filelock for `.lock`, fnmatch for `x-editable-by`, RFC 8785 cache-key
  canonicalization, cache/runtime placement outside the sheet).

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
