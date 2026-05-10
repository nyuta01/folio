# FOLIO-H-025 Plan: Phase 5 Viewer V4–V6

## Goal

Land the rest of the Viewer (V4–V6): materialize dashboard, history
view (per record × field), one-way SSE event stream for agent
activity, the Playwright frontend smoke, and the `folio serve`
shortcut alias over `folio-viewer`.

## Scope

- `src/folio_viewer/_events.py`:
  - `EventBus` — small in-process pub/sub. Subscribers receive an
    `asyncio.Queue[dict]`; publishers emit dicts that the SSE
    endpoint serializes as `data: <json>\n\n` frames. The bus is
    bounded (drops oldest on overflow) so a slow client cannot
    pin memory.
  - `materialize_event(...)` factory that builds the
    canonical event payload (`{kind, ts, ...}`).
- `src/folio_viewer/server.py`:
  - `GET /events` — `EventSourceResponse`-like Starlette
    `StreamingResponse` with `text/event-stream`,
    `Cache-Control: no-cache`, `X-Accel-Buffering: no`. Sends a
    keepalive comment every 15s.
  - The materialize route publishes `materialize.start` and
    `materialize.end` events around `Sheet.materialize`. Failures
    publish `materialize.error`.
  - Settings gain `event_bus` (constructed by `build_app` if not
    injected; tests inject one to count events).
- `src/folio/cli.py`: new `serve` sub-command that re-uses
  `folio_viewer.cli.serve` so users can run `folio serve <sheet>`
  per §17 of the design overview. Implementation lazy-imports
  `folio_viewer` so missing fastapi/uvicorn (theoretical, the
  deps are required) does not break the Phase 0 CLI.
- Frontend (`viewer/src/`):
  - `Dashboard.tsx`: per-target counts (ai / import / human /
    none), last run timestamp, "Materialize all" button (calls
    `POST /api/materialize`).
  - `History.tsx`: opens on a record × field click, shows the
    full append-only `provenance.jsonl` chain via
    `GET /api/provenance?history=true`.
  - `useEventStream.ts`: hook that subscribes to `/events` via
    `EventSource`, exposes the latest event so the dashboard
    can flash a "running…" indicator.
  - Toggle between "Records", "Dashboard", "History" via tab
    nav.
- Tests:
  - `tests/test_viewer_events.py`: hits `/events` via the
    Starlette `TestClient` (which supports
    `stream=True`), confirms `materialize.start` /
    `materialize.end` arrive in order around a `POST
    /api/materialize` call. History route returns a list when
    `history=true`. The `serve` CLI alias delegates to
    `folio_viewer.cli` (covered with monkeypatch).
- Smoke:
  - Extend `scripts/_viewer_smoke.py` to read the SSE stream
    during a materialize round-trip and assert the lifecycle
    frames arrive (one extra socket).
- Playwright (not in CI):
  - `viewer/playwright.config.ts`,
    `viewer/tests/grid.spec.ts` — boots `npm run dev`, polls
    until ready, asserts the `data-testid="records-table"`
    grid is visible and the type chip text is rendered. The
    test runner is intentionally absent from `make verify`;
    document the run command in `viewer/README.md`.
- Harness wiring:
  - `scripts/harness_check.py` requires the new files.
  - `feature-list.json`, `AGENT_PROGRESS.md`, and
    `docs/QUALITY_SCORE.md` updated.

## Out of scope

- Authentication / multi-user (Phase 7).
- Building / running Playwright in CI (kept opt-in to avoid
  pulling Node into the verify gate).
- Real-time collaborative editing.

## Evidence

- `make verify` passes locally and in CI: harness-check, drift,
  validate-docs, pytest, six smokes including the new SSE path.
- `folio serve <sheet>` boots the same UI as `folio-viewer
  serve`.

## Observation

V0–V3 shipped under `FOLIO-H-024` last cycle and the backend has
all the routes V4 and V5 need. The remaining work is glue: a tiny
event bus, the SSE endpoint, three React views, and the alias on
the existing CLI.

## Decision

- The event bus is in-process and per-app; multi-process
  coordination is out of scope for Phase 5. A future move to
  Redis pub/sub or Postgres LISTEN/NOTIFY can replace
  `EventBus` without changing the wire format.
- SSE (not WebSockets) per §19.1: the design overview already
  named SSE as the one-way push transport.
- `folio serve` is implemented in `folio.cli` so the alias is
  visible in `folio --help`. The actual binding lives in
  `folio_viewer.cli` to keep the SDK CLI free of fastapi /
  uvicorn imports — drift-check still passes.
- Playwright stays out of CI to keep the verify gate uv-only.
  The opt-in command is documented in `viewer/README.md`.

## Permanent Fix

- `make verify` runs the new SSE pytest cases and the extended
  smoke.
- `scripts/harness_check.py` requires the new files.
- `scripts/harness_drift.py` keeps the fastapi / uvicorn anchor
  from `FOLIO-H-024` — `folio.cli` lazy-imports
  `folio_viewer.cli`, so the import only happens when `folio
  serve` is invoked.

## Next Check

After V4–V6 land, the only standing tasks are `FOLIO-H-006` and
`FOLIO-H-007` (self-PDCA + permanent-fix loops). The next
concrete product backlog will come from real usage of the
Viewer rather than the original §19 stages.
