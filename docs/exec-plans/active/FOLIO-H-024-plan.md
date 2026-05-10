# FOLIO-H-024 Plan: Phase 5 Viewer V0–V3

## Goal

Land the local-only Folio Viewer through stage V3 — read-only
records grid, type chips from the contract, edit affordance for
`x-editable-by` fields, and provenance hover with derivation
badges. Backend is FastAPI and imports the SDK directly (§19.1).

## Scope

- `src/folio_viewer/__init__.py` exposing `build_app(...)` and
  `ViewerSettings`.
- `src/folio_viewer/server.py`:
  - `build_app(*, sheet_path, default_actor=None, ai_client=None,
    static_dir=None) -> FastAPI`.
  - REST routes per §19.4:
    - `GET  /api/contract`
    - `GET  /api/records?fields=&limit=&cursor=`
    - `GET  /api/records/{id}?fields=`
    - `POST /api/records` (upsert; CSRF token required)
    - `DELETE /api/records?ids=` (CSRF token required)
    - `POST /api/query` (`{sql, params?}`)
    - `GET  /api/status?targets=`
    - `POST /api/materialize` (`{targets?, record_ids?, force?,
      actor?}`; CSRF token required) — driven by an injected
      `AIClient` so tests stay offline (V3 wires the response;
      dashboard polish lives in `FOLIO-H-025`).
    - `GET  /api/provenance?record_id=&field=&history=`
  - Bind to `127.0.0.1` only via the CLI; the app itself is
    transport-agnostic.
  - CSRF: token issued on the first GET (sets a `folio_csrf`
    cookie + a `GET /api/csrf` echo route). Mutating verbs
    (`POST` / `DELETE`) require an `X-CSRF-Token` header that
    matches the cookie.
  - `FolioError` is mapped to a JSON error envelope
    (`{error: {type, message}}`) with appropriate 4xx / 5xx
    status. Pydantic validation errors map to 400.
  - Static-file serving: when `static_dir` exists, mount it at
    `/` so the React build is served by the same origin as the
    API. The `/api/...` routes always take precedence over the
    catch-all.
- `src/folio_viewer/cli.py` registers `folio-viewer` (Typer):
  `folio-viewer <sheet> [--port 3000] [--host 127.0.0.1]
  [--actor agent:human]`. The `folio serve` alias lands in
  `FOLIO-H-025` once the CLI surface is stable.
- `viewer/` Vite + React + TanStack Table scaffold:
  - `viewer/package.json` (React 18, TanStack Table v8, Vite v5).
  - `viewer/vite.config.ts`, `viewer/tsconfig.json`,
    `viewer/index.html`.
  - `viewer/src/main.tsx`, `viewer/src/App.tsx`,
    `viewer/src/api.ts`.
  - V0 records grid; V1 type chips and descriptions on column
    headers; V2 inline editor for `x-editable-by` fields wired to
    `POST /api/records`; V3 provenance hover and a `kind:`
    badge per cell when latest provenance is non-`human`.
  - The frontend is **not built in CI** (no Node toolchain).
    The backend smoke covers the API surface; the Playwright
    frontend smoke is `FOLIO-H-025`.
- `tests/test_viewer.py` covers each REST route's success and one
  representative error path (CSRF rejection, contract not found,
  query non-SELECT, etc.).
- `scripts/_viewer_smoke.py` (Python helper) and
  `scripts/smoke-viewer.sh` boot the FastAPI app via `uvicorn`
  on a random port, hit `/api/contract`, `/api/records`,
  `POST /api/records`, `POST /api/query`, and
  `POST /api/materialize` (against a `StubAIClient`), and tear
  the server down.
- `pyproject.toml` adds `fastapi` and `uvicorn[standard]` as
  runtime deps and registers the `folio-viewer` script.
- `Makefile` gains `viewer-smoke` and includes it in `verify`.
- `scripts/harness_check.py` requires the new files.
- `scripts/harness_drift.py`: `fastapi` and `uvicorn` may only
  be imported from `src/folio_viewer/`.
- `docs/QUALITY_SCORE.md` and `AGENT_PROGRESS.md` updated.

## Out of scope (deferred to FOLIO-H-025)

- Materialize dashboard with per-target counts.
- History view (per record × field).
- SSE event stream.
- Playwright frontend smoke.
- `folio serve` CLI alias.
- Authentication / multi-user.

## Evidence

- `make verify` passes locally and in CI: harness-check,
  drift-check, validate-docs, pytest, and all six smokes
  (cli, materialize, scripts, mcp, extension-kinds, viewer).
- `scripts/smoke-viewer.sh` round-trips the API on every run.

## Observation

Phases 0–4 are feature-complete and offline-verified. The Viewer
is the only remaining product backlog. Splitting it at V3 keeps
each PR narrow enough to review and lets the materialize
dashboard stay paired with its UX (V4–V6) in `FOLIO-H-025`.

## Decision

- Backend imports the SDK directly (no extra protocol layer)
  per §19.1.
- CSRF is enforced by a header that must equal the cookie value;
  no cryptographic signing in V3 because the bind is `127.0.0.1`
  only and the threat model is browser CSRF, not a
  network-attached attacker.
- The materialize endpoint exists in V3 because V2 wiring needs
  to call it from the eventual dashboard, but the dashboard UX
  is `FOLIO-H-025`. Tests inject `StubAIClient` so the route
  stays offline.
- Frontend toolchain (Node + Vite + Playwright) is **not** wired
  into CI. CI keeps the uv-only verify gate; the Playwright
  smoke lands in `FOLIO-H-025` alongside a guard that skips it
  when Node is absent.

## Permanent Fix

- `make verify` runs the new pytest cases and `viewer-smoke`.
- `scripts/harness_check.py` requires `src/folio_viewer/`,
  `tests/test_viewer.py`, and the smoke files.
- `scripts/harness_drift.py` pins `fastapi` / `uvicorn` imports
  to `src/folio_viewer/` so the Viewer cannot leak into the
  SDK by accident.

## Next Check

`FOLIO-H-025` adds the V4–V6 surfaces (materialize dashboard,
history view, SSE) and the Playwright smoke. The CSRF
implementation here will be reused unchanged. If V4 needs more
expressive error envelopes, this plan's invariants are stable
enough that the change can be additive.
