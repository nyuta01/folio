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

## Stages implemented (V0–V3)

| Stage | Implementation |
|---|---|
| V0 | Records table via TanStack Table (`App.tsx`). |
| V1 | Type chips and description tooltips on each column header. |
| V2 | Inline `<input>` editor on `x-editable-by` fields, persisted via `POST /api/records` with the CSRF token. |
| V3 | Provenance hover (cell `title`) and a colored badge per non-`human` source. |

## Out of scope (Phase 5 V4–V6 lives in `FOLIO-H-025`)

- Materialize dashboard.
- History view.
- SSE event stream.
- Playwright frontend smoke.

## CI note

The Node toolchain is **not** wired into `make verify`. Backend tests +
`scripts/smoke-viewer.sh` cover the API surface. The Playwright smoke
that boots the dev server lands with `FOLIO-H-025`.
