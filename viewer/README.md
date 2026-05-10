# folio-viewer (frontend)

Vite + React + TanStack Table scaffold for the Phase 5 Viewer (V0–V3).
The Python backend (`folio-viewer`) serves the build output from
`viewer/dist/` as static files, so the **same origin** hosts both the
API and the UI in production.

## Local development

```bash
# Terminal A — backend
uv run folio-viewer serve <sheet> --port 3000 --actor agent:human

# Terminal B — frontend (proxies /api → 127.0.0.1:3000)
cd viewer
npm install
npm run dev
```

Then open <http://127.0.0.1:5173>. The Vite dev server proxies `/api`
calls to the backend so CSRF cookies stay first-party.

## Production build

```bash
cd viewer
npm install
npm run build      # writes viewer/dist/
```

Re-run `folio-viewer serve <sheet>` and it will auto-detect
`viewer/dist/` (or pass `--static-dir <path>` explicitly).

## Stages implemented (V0–V6)

| Stage | Implementation |
|---|---|
| V0 | Records table via TanStack Table (`App.tsx`). |
| V1 | Type chips and description tooltips on each column header. |
| V2 | Inline `<input>` editor on `x-editable-by` fields, persisted via `POST /api/records` with the CSRF token. |
| V3 | Provenance hover (cell `title`) and a colored badge per non-`human` source. |
| V4 | `Dashboard.tsx`: per-target `ai_count` / `import_count` / `human_count` / `none_count`, last run, and a "Materialize all" button. |
| V5 | `History.tsx`: append-only provenance chain shown when a non-editable cell is clicked from the records grid. |
| V6 | `useEventStream.ts`: subscribes to `/events` (SSE) and surfaces a "running…" banner on the dashboard during a materialize run. |

## Playwright (opt-in, not in CI)

```bash
cd viewer
npm install
npx playwright install --with-deps chromium
# Backend on :3000, Vite dev on :5173 (proxies /api)
uv run folio serve <sheet> --port 3000 --actor agent:human &
npm run test:e2e
```

## CI note

The Node toolchain is **not** wired into `make verify`. Backend tests +
`scripts/smoke-viewer.sh` (which now includes the SSE round-trip)
cover the API surface deterministically.
