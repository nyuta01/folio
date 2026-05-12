# Quality Score

Last updated: 2026-05-12

Scores use a 1-5 scale:

- 1: missing or unsafe
- 2: scaffolded but not yet reliable
- 3: usable with known gaps
- 4: solid and routinely verified
- 5: excellent, mechanically enforced, and resilient to agent drift

| Domain | Score | Evidence | Weak Spot | Next Task |
|---|---:|---|---|---|
| Harness PDCA | 4 | `make verify` runs `harness-check`, `drift-check`, `validate-docs`, `python-test`, and offline smokes; GitHub Actions runs the same gate on pull requests and pushes to `main` after `uv sync --frozen`; PyPI release provenance, Desktop agent boundaries, retired-MCP invariants, contract writer temp-file safety, query sandbox shape, and cross_sheet source containment are now drift-checked | Semantic design drift checks beyond ADR and high-impact security anchors are still shallow | `FOLIO-H-006` |
| Sheet Spec | 5 | Design overview defines `contract.yaml`, `records.jsonl`, derivations, provenance, cache-key, operations, and the Viewer end-to-end with ODCS subset alignment; `make verify` exercises every Phase 0–5 spec surface (parsing, querying, write semantics, derivations, materialize loop, cache, provenance, CLI verbs, TOON, extension kinds, datapackage export, Viewer REST + CSRF) through pytest plus the CLI / materialize / scripts / extension-kinds / Viewer smokes; cross_sheet resolver tests cover absolute path rejection, parent-directory containment, symlink escape rejection, and records-only directory rejection | Phase 5 V4–V6 (materialize dashboard, history, SSE) is spec-only | `FOLIO-H-025` |
| Phase 0 SDK | 5 | `folio.open_sheet` exposes `get_contract`, `query` (single-statement DuckDB SELECT-only plus external-access sandboxing), `list_records` with pagination, `get_record`, `upsert_records`, and `delete_records` with `.lock` (30s timeout via filelock), atomic temp+rename writes using exclusive random same-directory temp files for `records.jsonl` and `contract.yaml`, primaryKey/required validation, and fnmatch-based `editable_by` enforcement; pytest covers the operation surface, atomic-write rollback, concurrent-writer serialization, `read_text` file exfiltration blocking, stacked-statement rejection, and contract temp-file symlink regression | Query safety still depends on DuckDB honoring `enable_external_access=false`; keep the focused regressions in the full gate | `FOLIO-H-034` |
| Phase 0 CLI | 4 | `folio` CLI exposes `validate`, `query`, `list`, `count`, `upsert`, and `delete` via Typer; registered as a project script through `pyproject.toml`; covered by 16 `CliRunner` cases plus `scripts/smoke-cli.sh` that runs the §23.3 scenario end-to-end behind `make verify` | TOON output, `--format` switching, and the `materialize`/`status`/`provenance`/`serve` verbs are not implemented yet (Phase 1+) | `FOLIO-H-005` |
| Design Docs & ADRs | 5 | Canonical design docs live under `docs/design-docs/`; nine indexed ADRs cover the docs hierarchy, every Phase 0 design choice encoded in code, and the Phase 1 AI client Protocol + deterministic stub (ADR-0009); `make validate-docs` enforces sequential numbering, indexing, required sections, and a confirmation path for accepted ADRs | Semantic ADR-to-code drift checks beyond the current anchors are still shallow | `FOLIO-H-006` |
| Release Automation | 4 | `release-python.yml` rebuilds and smoke-tests from the release tag on Release publication, and PyPI OIDC publishing downloads only artifacts uploaded by the same workflow run; `make drift-check` rejects mutable GitHub Release asset downloads and publish-job release-tag shell interpolation | GitHub Actions behavior still needs end-to-end confirmation on the next real release | `FOLIO-H-028` |
| Desktop Agent Execution | 4 | `apps/desktop/src/main/agents.ts` resolves chat agent binaries from the host PATH before spawning with the sheet cwd and no longer prepends sheet-derived `.venv/bin`; `make drift-check` rejects future direct PATH mutation in that file | Needs end-to-end desktop runtime confirmation on packaged builds across OSes | `FOLIO-H-029` |
| Desktop Agent IPC | 4 | `agents:run` ignores renderer-provided cwd and derives the spawn directory from Electron main-process `currentSheet`; preload narrows the run payload; the renderer bridge type omits cwd; `make drift-check` rejects future cwd re-exposure | Origin/sender hardening for all Desktop IPC is still shallow beyond the main-window preload contract | `FOLIO-H-030` |
| Retired MCP Surface | 4 | `FOLIO-H-031` removes `folio-mcp`, `src/folio_mcp`, FastMCP runtime dependency, MCP docs, MCP tests, and `mcp-smoke`; `make drift-check` rejects reintroducing the package, docs, dependency, console script, or smoke target | Historical docs and changelog entries still mention the removed surface as history | `FOLIO-H-031` |
| Phase 5 Viewer | 5 | `src/folio_viewer/` ships a FastAPI backend (`folio-viewer` + `folio serve` alias) covering all of §19.3 V0–V6: contract / records / query / status / materialize / provenance routes, CSRF cookie + header on every mutating verb, `FolioError` mapped to a typed JSON envelope, an in-process `EventBus` whose `materialize.start` / `materialize.end` / `materialize.error` frames stream out over `/events` (SSE with 15-second keepalives); the Vite + React + TanStack Table scaffold under `viewer/` ships V0–V3 plus `Dashboard.tsx` (V4), `History.tsx` (V5), and `useEventStream.ts` (V6); pytest covers the API surface + the EventBus + the `folio serve` alias, including a `/api/query` regression that blocks DuckDB file-reading table functions, and `scripts/smoke-viewer.sh` boots `uvicorn`, opens an SSE consumer, triggers materialize, and asserts the lifecycle frames arrive | Playwright frontend smoke is opt-in (Node toolchain is intentionally not wired into `make verify`) | — |

## Current Assessment

Phases 0 / 1 / 2 / 3 / 4 / 5 are all feature-complete and
ADR-anchored. The repository now ships:

- The Phase 0 SDK + CLI (contract, query, list, get, upsert, delete), with
  DuckDB caller SQL sandboxed from arbitrary local file reads.
- The Phase 1 materialize loop with cache + provenance + ai/import
  kinds (offline-capable through `StubAIClient`).
- Phase 2 reusable scripts (`Sheet.run_script` + `folio script
  run`) and a typed README frontmatter (`Sheet.metadata`).
- Phase 3 TOON encoder for `list_records`. The former MCP server surface
  has been retired; agents use the CLI and integrations use the SDK.
- Phase 4 extension kinds (`sql`, `http`, `python`, `cross_sheet`)
  and Frictionless `datapackage.json` export. `cross_sheet` is
  constrained to relative sibling-workspace paths and validates the
  foreign directory as a Folio sheet before reading records.
- Phase 5 Viewer V0–V6: FastAPI backend (`folio-viewer` +
  `folio serve` alias) with CSRF, every V0–V6 REST + SSE route,
  and a Vite + React + TanStack Table scaffold under `viewer/`
  with `Dashboard.tsx`, `History.tsx`, and a `useEventStream`
  hook. Playwright is scaffolded as opt-in.

Aardvark's DuckDB file-read finding is fixed in `FOLIO-H-032`: caller SQL now
runs with DuckDB external access disabled after Folio preloads `records.jsonl`
into a temporary in-memory table. The regression test creates an outside secret
and asserts `read_text` is rejected.

Aardvark's contract temp-file symlink finding is fixed in `FOLIO-H-033`:
`write_contract()` now uses an exclusive random same-directory temp file,
fsyncs it, and publishes with `os.replace()`. The regression pre-creates a
malicious `contract.yaml.tmp` symlink and asserts schema edits do not clobber
the target.

`FOLIO-H-034` adds the Viewer-specific query follow-up: `/api/query` now has an
HTTP regression for DuckDB file-reading functions, stacked statements are
rejected at the SDK query guard, and drift-check pins the query sandbox shape.

`FOLIO-H-035` fixes the `cross_sheet` path-containment gap: foreign sheet
sources must be relative, remain inside the calling sheet's parent directory
after symlink resolution, and include a valid `contract.yaml` before Folio reads
their `records.jsonl`.

Drift-check enforces five ADR invariants mechanically: anthropic
import location (ADR-0009), duckdb / filelock retention
(ADR-0005 / ADR-0006), fixture sheets free of cache / runtime
/ venv state (ADR-0008), and Phase 5's viewer-only fastapi /
uvicorn imports. It also enforces the release security invariant that
PyPI publishing uses same-run build artifacts instead of mutable GitHub
Release assets, and the Desktop security invariant that chat agents must not
mutate PATH from sheet-controlled locations. It also enforces Desktop agent IPC
cwd confinement to the main-process `currentSheet`, and rejects reintroducing
the retired MCP package, docs, dependency, console script, or smoke target. It
also rejects predictable contract temp names and direct `Path.write_text` sinks
in `write_contract()`, plus the DuckDB query sandbox ingredients and Viewer
HTTP regression. It also rejects removal of the `cross_sheet` source
containment checks and resolver regressions.
`make verify` runs the full pytest suite plus five offline smokes (`cli`,
`materialize`, `scripts`, `extension-kinds`, `viewer`). The viewer smoke now
exercises SSE end-to-end against a live `uvicorn` instance.

The only remaining tasks are the standing self-improvement
loops (`FOLIO-H-006`, `FOLIO-H-007`).

## Review Cadence

Update this document after every completed P0/P1 task and whenever an agent
failure produces a permanent fix.
