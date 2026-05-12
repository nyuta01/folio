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
| Harness PDCA | 4 | `make verify` runs `harness-check`, `drift-check`, `validate-docs`, `python-test`, and offline smokes; GitHub Actions runs the same gate on pull requests and pushes to `main` after `uv sync --frozen`; PyPI release provenance and Desktop agent PATH hardening are now drift-checked | Semantic design drift checks beyond ADR and high-impact security anchors are still shallow | `FOLIO-H-006` |
| Sheet Spec | 5 | Design overview defines `contract.yaml`, `records.jsonl`, derivations, provenance, cache-key, operations, and the Viewer end-to-end with ODCS subset alignment; `make verify` exercises every Phase 0–5 spec surface (parsing, querying, write semantics, derivations, materialize loop, cache, provenance, CLI verbs, MCP tools, TOON, extension kinds, datapackage export, Viewer REST + CSRF) through pytest plus the CLI / materialize / scripts / MCP / extension-kinds / Viewer smokes | Phase 5 V4–V6 (materialize dashboard, history, SSE) is spec-only | `FOLIO-H-025` |
| Phase 0 SDK | 4 | `folio.open_sheet` exposes `get_contract`, `query` (DuckDB SELECT-only), `list_records` with pagination, `get_record`, `upsert_records`, and `delete_records` with `.lock` (30s timeout via filelock), atomic temp+rename writes, primaryKey/required validation, and fnmatch-based `editable_by` enforcement; pytest covers 35 cases including atomic-write rollback and concurrent-writer serialization | No CLI surface or smoke yet | `FOLIO-H-004` |
| Phase 0 CLI | 4 | `folio` CLI exposes `validate`, `query`, `list`, `count`, `upsert`, and `delete` via Typer; registered as a project script through `pyproject.toml`; covered by 16 `CliRunner` cases plus `scripts/smoke-cli.sh` that runs the §23.3 scenario end-to-end behind `make verify` | TOON output, `--format` switching, and the `materialize`/`status`/`provenance`/`serve` verbs are not implemented yet (Phase 1+) | `FOLIO-H-005` |
| Design Docs & ADRs | 5 | Canonical design docs live under `docs/design-docs/`; nine indexed ADRs cover the docs hierarchy, every Phase 0 design choice encoded in code, and the Phase 1 AI client Protocol + deterministic stub (ADR-0009); `make validate-docs` enforces sequential numbering, indexing, required sections, and a confirmation path for accepted ADRs | Semantic ADR-to-code drift checks beyond the current anchors are still shallow | `FOLIO-H-006` |
| Release Automation | 4 | `release-python.yml` rebuilds and smoke-tests from the release tag on Release publication, and PyPI OIDC publishing downloads only artifacts uploaded by the same workflow run; `make drift-check` rejects mutable GitHub Release asset downloads and publish-job release-tag shell interpolation | GitHub Actions behavior still needs end-to-end confirmation on the next real release | `FOLIO-H-028` |
| Desktop Agent Execution | 4 | `apps/desktop/src/main/agents.ts` resolves chat agent binaries from the host PATH before spawning with the sheet cwd and no longer prepends sheet-derived `.venv/bin`; `make drift-check` rejects future direct PATH mutation in that file | Needs end-to-end desktop runtime confirmation on packaged builds across OSes | `FOLIO-H-029` |
| Desktop Agent IPC | 4 | `agents:run` ignores renderer-provided cwd and derives the spawn directory from Electron main-process `currentSheet`; preload narrows the run payload; the renderer bridge type omits cwd; `make drift-check` rejects future cwd re-exposure | Origin/sender hardening for all Desktop IPC is still shallow beyond the main-window preload contract | `FOLIO-H-030` |
| Phase 5 Viewer | 5 | `src/folio_viewer/` ships a FastAPI backend (`folio-viewer` + `folio serve` alias) covering all of §19.3 V0–V6: contract / records / query / status / materialize / provenance routes, CSRF cookie + header on every mutating verb, `FolioError` mapped to a typed JSON envelope, an in-process `EventBus` whose `materialize.start` / `materialize.end` / `materialize.error` frames stream out over `/events` (SSE with 15-second keepalives); the Vite + React + TanStack Table scaffold under `viewer/` ships V0–V3 plus `Dashboard.tsx` (V4), `History.tsx` (V5), and `useEventStream.ts` (V6); pytest covers the API surface + the EventBus + the `folio serve` alias, and `scripts/smoke-viewer.sh` boots `uvicorn`, opens an SSE consumer, triggers materialize, and asserts the lifecycle frames arrive | Playwright frontend smoke is opt-in (Node toolchain is intentionally not wired into `make verify`) | — |

## Current Assessment

Phases 0 / 1 / 2 / 3 / 4 / 5 are all feature-complete and
ADR-anchored. The repository now ships:

- The Phase 0 SDK + CLI (contract, query, list, get, upsert, delete).
- The Phase 1 materialize loop with cache + provenance + ai/import
  kinds (offline-capable through `StubAIClient`).
- Phase 2 reusable scripts (`Sheet.run_script` + `folio script
  run`) and a typed README frontmatter (`Sheet.metadata`).
- Phase 3 MCP server (`folio-mcp` exposing nine tools through
  FastMCP, offline-tested via the in-process Client harness) and a
  thin TOON encoder for `list_records`.
- Phase 4 extension kinds (`sql`, `http`, `python`, `cross_sheet`)
  and Frictionless `datapackage.json` export.
- Phase 5 Viewer V0–V6: FastAPI backend (`folio-viewer` +
  `folio serve` alias) with CSRF, every V0–V6 REST + SSE route,
  and a Vite + React + TanStack Table scaffold under `viewer/`
  with `Dashboard.tsx`, `History.tsx`, and a `useEventStream`
  hook. Playwright is scaffolded as opt-in.

Drift-check enforces five ADR invariants mechanically: anthropic
import location (ADR-0009), duckdb / filelock retention
(ADR-0005 / ADR-0006), fixture sheets free of cache / runtime
/ venv state (ADR-0008), and Phase 5's viewer-only fastapi /
uvicorn imports. It also enforces the release security invariant that
PyPI publishing uses same-run build artifacts instead of mutable GitHub
Release assets, and the Desktop security invariant that chat agents must not
mutate PATH from sheet-controlled locations. It also enforces Desktop agent IPC
cwd confinement to the main-process `currentSheet`. `make verify` runs the full
pytest suite plus six offline smokes (`cli`, `materialize`, `scripts`, `mcp`,
`extension-kinds`, `viewer`). The viewer smoke now exercises SSE end-to-end
against a live `uvicorn` instance.

The only remaining tasks are the standing self-improvement
loops (`FOLIO-H-006`, `FOLIO-H-007`).

## Review Cadence

Update this document after every completed P0/P1 task and whenever an agent
failure produces a permanent fix.
